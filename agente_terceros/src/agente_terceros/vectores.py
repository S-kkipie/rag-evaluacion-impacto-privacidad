"""Índice vectorial FAISS (coseno) y embeddings locales con Ollama."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import faiss
import numpy as np
import requests

from .config import Config
from .ingest import Fragmento

# embed(textos, tipo) -> matriz (n, d); tipo = "documento" | "consulta"
Embedder = Callable[[list[str], str], np.ndarray]

# nomic-embed-text distingue documentos y consultas con un prefijo de tarea.
PREFIJOS = {"documento": "search_document: ", "consulta": "search_query: "}


def embedder_ollama(cfg: Config, lote: int = 32) -> Embedder:
    def embed(textos: list[str], tipo: str = "documento") -> np.ndarray:
        vectores = []
        for i in range(0, len(textos), lote):
            r = requests.post(
                f"{cfg.ollama_url}/api/embed",
                json={
                    "model": cfg.embedding_model,
                    "input": [PREFIJOS[tipo] + t for t in textos[i:i + lote]],
                },
                timeout=300,
            )
            r.raise_for_status()
            vectores.extend(r.json()["embeddings"])
        return np.asarray(vectores, dtype="float32")

    return embed


def _normalizar(m: np.ndarray) -> np.ndarray:
    m = np.ascontiguousarray(m, dtype="float32")
    faiss.normalize_L2(m)
    return m


class IndiceVectorial:
    """IndexFlatIP sobre vectores normalizados = similitud coseno exacta."""

    def __init__(self, embed: Embedder):
        self.embed = embed
        self.index: faiss.Index | None = None
        self.fragmentos: list[Fragmento] = []

    def __len__(self) -> int:
        return len(self.fragmentos)

    def agregar(self, fragmentos: list[Fragmento]) -> None:
        if not fragmentos:
            return
        m = _normalizar(self.embed([f.texto for f in fragmentos], "documento"))
        if self.index is None:
            self.index = faiss.IndexFlatIP(m.shape[1])
        self.index.add(m)
        self.fragmentos.extend(fragmentos)

    def buscar(
        self, consulta: str, k: int = 4, filtro: dict | None = None
    ) -> list[tuple[Fragmento, float]]:
        if self.index is None:
            return []
        q = _normalizar(self.embed([consulta], "consulta"))
        # Con filtro se pide más candidatos y se descartan los que no coinciden.
        n = len(self) if filtro else min(k, len(self))
        scores, ids = self.index.search(q, n)
        res = []
        for s, i in zip(scores[0], ids[0]):
            if i < 0:
                continue
            f = self.fragmentos[i]
            if filtro and any(f.meta.get(c) != v for c, v in filtro.items()):
                continue
            res.append((f, float(s)))
            if len(res) == k:
                break
        return res

    def guardar(self, directorio: Path) -> None:
        directorio.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(directorio / "normativa.faiss"))
        datos = [{"texto": f.texto, "meta": f.meta} for f in self.fragmentos]
        (directorio / "fragmentos.json").write_text(
            json.dumps(datos, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def cargar(cls, directorio: Path, embed: Embedder) -> IndiceVectorial:
        idx = cls(embed)
        idx.index = faiss.read_index(str(directorio / "normativa.faiss"))
        datos = json.loads((directorio / "fragmentos.json").read_text(encoding="utf-8"))
        idx.fragmentos = [Fragmento(d["texto"], d["meta"]) for d in datos]
        return idx


def construir_indice(cfg: Config, embed: Embedder) -> IndiceVectorial:
    """Lee el corpus, fragmenta, vectoriza y persiste el índice en cfg.index_dir."""
    from .config import CORPUS
    from .ingest import fragmentar, leer_documento

    idx = IndiceVectorial(embed)
    for fuente in CORPUS:
        texto, offsets = leer_documento(fuente.ruta)
        frags = fragmentar(texto, offsets, fuente, cfg.tamano, cfg.solape)
        idx.agregar(frags)
        print(f"  {fuente.sigla:<14} {len(frags):>4} fragmentos")
    idx.guardar(cfg.index_dir)
    return idx
