"""Evaluación del RAG: métricas de recuperación (Hit@k, MRR, P@k) y, opcionalmente,
generación de respuestas para revisión manual."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from langchain_core.documents import Document

from .config import ROOT, get_config

PREGUNTAS = ROOT / "eval" / "preguntas.jsonl"
SALIDA = ROOT / "eval" / "resultados"
# Citas "[2]" o agrupadas "[1, 2]".
RE_CITA = re.compile(r"\[\d+(?:\s*,\s*\d+)*\]")


def es_relevante(doc: Document, esperado: list[dict]) -> bool:
    m = doc.metadata
    for e in esperado:
        if m["fuente"] != e["fuente"]:
            continue
        if "articulos" not in e and "considerandos" not in e:
            return True
        if m.get("articulo") in e.get("articulos", []):
            return True
        if m.get("considerando") in e.get("considerandos", []):
            return True
    return False


def metricas(docs: list[Document], esperado: list[dict]) -> dict:
    rel = [es_relevante(d, esperado) for d in docs]
    primero = next((i for i, r in enumerate(rel, 1) if r), None)
    return {
        "hit": primero is not None,
        "rr": 1 / primero if primero else 0.0,
        "precision": sum(rel) / len(rel) if rel else 0.0,
    }


def _buscar(estrategia: str, pregunta: str, cfg):
    from .rag import _store, recuperar

    if estrategia == "mmr":
        return recuperar(pregunta, cfg)
    return _store(cfg).similarity_search(pregunta, k=cfg.top_k)


def evaluar(generar: bool = False) -> dict:
    cfg = get_config()
    items = [json.loads(l) for l in PREGUNTAS.read_text(encoding="utf-8").splitlines() if l.strip()]
    SALIDA.mkdir(parents=True, exist_ok=True)

    resumen: dict[str, dict] = {}
    detalle: list[dict] = []
    for estrategia in ("similitud", "mmr"):
        filas = []
        for it in items:
            t0 = time.perf_counter()
            docs = _buscar(estrategia, it["pregunta"], cfg)
            lat = time.perf_counter() - t0
            m = metricas(docs, it["esperado"])
            filas.append(m | {"latencia_s": lat})
            detalle.append(
                {
                    "estrategia": estrategia,
                    "id": it["id"],
                    **m,
                    "fuentes": [
                        f"{d.metadata['fuente']}:{d.metadata.get('articulo') or 'c' + d.metadata.get('considerando', '-')}"
                        for d in docs
                    ],
                }
            )
        n = len(filas)
        resumen[estrategia] = {
            f"hit@{cfg.top_k}": sum(f["hit"] for f in filas) / n,
            "mrr": sum(f["rr"] for f in filas) / n,
            f"p@{cfg.top_k}": sum(f["precision"] for f in filas) / n,
            "fuentes_distintas_prom": sum(len({s.split(":")[0] for s in d["fuentes"]}) for d in detalle if d["estrategia"] == estrategia) / n,
            "latencia_prom_s": sum(f["latencia_s"] for f in filas) / n,
        }

    print(f"\nRecuperación sobre {len(items)} preguntas (k={cfg.top_k}):")
    for est, r in resumen.items():
        print(f"  {est:10} " + "  ".join(f"{k}={v:.3f}" for k, v in r.items()))

    (SALIDA / "recuperacion.json").write_text(
        json.dumps({"resumen": resumen, "detalle": detalle}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if generar:
        _generar(items, cfg)
    return resumen


def _generar(items: list[dict], cfg) -> None:
    from .rag import consultar, etiqueta

    lineas = ["# Respuestas generadas por el RAG\n", f"Modelo: `{cfg.llm_model}` · k={cfg.top_k} (MMR)\n"]
    con_cita, latencias = 0, []
    for it in items:
        t0 = time.perf_counter()
        r = consultar(it["pregunta"], cfg)
        latencias.append(time.perf_counter() - t0)
        con_cita += bool(RE_CITA.search(r.respuesta))
        lineas += [
            f"\n## {it['id']}. {it['pregunta']}\n",
            r.respuesta.strip(),
            "\n**Fuentes recuperadas:**\n",
            *[f"- [{i}] {etiqueta(d)}" for i, d in enumerate(r.fuentes, 1)],
        ]
        time.sleep(4)  # margen para el límite de peticiones del free tier
    n = len(items)
    resumen = f"\n---\nRespuestas con citas: {con_cita}/{n} · latencia media: {sum(latencias)/n:.2f} s\n"
    lineas.append(resumen)
    (SALIDA / "respuestas.md").write_text("\n".join(lineas), encoding="utf-8")
    print(resumen.strip())
