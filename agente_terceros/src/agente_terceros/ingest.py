"""Ingesta: PDF/TXT -> texto limpio -> fragmentos con metadatos (página, artículo)."""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from .config import Fuente

# Encabezados: "Artículo 35.", "Art. 5", "Article 35", "Cláusula 7", "CLÁUSULA OCTAVA".
RE_ARTICULO = re.compile(
    r"(?m)^\s*(?:Art[íi]culo|Article|Art\.)\s+([0-9IVXLC]+(?:\.[0-9]+)?)(?:\s*[º°]|\b)"
)
RE_CLAUSULA = re.compile(r"(?mi)^\s*cl[áa]usula\s+([0-9]+|[a-záéíóú]+)\b")


@dataclass
class Fragmento:
    texto: str
    meta: dict


def limpiar(texto: str) -> str:
    """Normaliza artefactos típicos de extracción PDF."""
    texto = texto.replace("\xad", "").replace("ﬁ", "fi").replace("ﬂ", "fl")
    texto = re.sub(r"(\w)fi (?=[a-záéíóúñ])", r"\1fi", texto)  # "confi anza" (El Peruano)
    texto = re.sub(r"(\w)-\n(\w)", r"\1\2", texto)
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r" *\n *", "\n", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def leer_documento(ruta: Path) -> tuple[str, list[int]]:
    """Devuelve el texto completo y el offset inicial de cada página (TXT = 1 página)."""
    if ruta.suffix.lower() != ".pdf":
        return limpiar(ruta.read_text(encoding="utf-8", errors="ignore")), [0]
    partes, offsets, pos = [], [], 0
    for pagina in PdfReader(ruta).pages:
        texto = limpiar(pagina.extract_text() or "") + "\n\n"
        offsets.append(pos)
        partes.append(texto)
        pos += len(texto)
    return "".join(partes), offsets


def _encabezados(texto: str) -> tuple[list[int], list[str]]:
    hallados = [(m.start(), m.group(1)) for m in RE_ARTICULO.finditer(texto)]
    hallados += [(m.start(), f"Cláusula {m.group(1)}") for m in RE_CLAUSULA.finditer(texto)]
    hallados.sort()
    return [p for p, _ in hallados], [e for _, e in hallados]


def _trozos(texto: str, tamano: int, solape: int) -> list[tuple[int, str]]:
    """Corta en párrafos (o palabras si un párrafo excede el tamaño) y empaqueta."""
    unidades: list[tuple[int, str]] = []
    for m in re.finditer(r"[^\n]+(?:\n(?!\n)[^\n]+)*", texto):
        if len(m.group()) <= tamano:
            unidades.append((m.start(), m.group()))
            continue
        for w in re.finditer(r"\S+", m.group()):
            unidades.append((m.start() + w.start(), w.group()))

    trozos: list[tuple[int, str]] = []
    grupo: list[tuple[int, str]] = []
    for unidad in unidades:
        largo = sum(len(u) + 1 for _, u in grupo)
        if grupo and largo + len(unidad[1]) > tamano:
            trozos.append((grupo[0][0], " ".join(u for _, u in grupo)))
            cola: list[tuple[int, str]] = []
            for previa in reversed(grupo):  # solape: últimas unidades que caben
                if sum(len(u) + 1 for _, u in cola) + len(previa[1]) > solape:
                    break
                cola.insert(0, previa)
            grupo = cola
        grupo.append(unidad)
    if grupo:
        trozos.append((grupo[0][0], " ".join(u for _, u in grupo)))
    return [(p, t[:tamano]) for p, t in trozos]


def fragmentar(
    texto: str, offsets: list[int], fuente: Fuente, tamano: int = 1000, solape: int = 150
) -> list[Fragmento]:
    pos_enc, enc = _encabezados(texto)
    frags = []
    for inicio, trozo in _trozos(texto, tamano, solape):
        fin = inicio + len(trozo)
        # Encabezado dentro del trozo (el primero) o, si no hay, el último anterior.
        i = bisect.bisect_left(pos_enc, inicio)
        if i < len(pos_enc) and pos_enc[i] < fin:
            articulo = enc[i]
        else:
            articulo = enc[i - 1] if i > 0 else ""
        frags.append(
            Fragmento(
                trozo,
                {
                    "fuente": fuente.sigla,
                    "titulo": fuente.titulo,
                    "jurisdiccion": fuente.jurisdiccion,
                    "pagina": bisect.bisect_right(offsets, inicio),
                    "articulo": articulo,
                },
            )
        )
    return frags
