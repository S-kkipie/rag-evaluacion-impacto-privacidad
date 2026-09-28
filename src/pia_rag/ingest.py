"""Ingesta: PDF -> texto limpio -> fragmentos con metadatos -> embeddings -> Chroma."""

from __future__ import annotations

import bisect
import re
import shutil
import time
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from .config import CORPUS, Config, Fuente

# Encabezados de artículo en español ("Artículo 35.", "Art. 5") e inglés ("Article 35").
RE_ARTICULO = re.compile(
    r"(?m)^\s*(?:Art[íi]culo|Article|Art\.)\s+([0-9IVXLC]+(?:\.[0-9]+)?)(?:\s*[º°]|\b)"
)

# Considerandos del RGPD: párrafos numerados "(91) Lo anterior debe aplicarse...".
RE_CONSIDERANDO = re.compile(r"(?m)^\((\d{1,3})\)\s+[A-ZÁÉÍÓÚ]")

SEPARADORES = [
    "\nTÍTULO ",
    "\nCAPÍTULO ",
    "\nArtículo ",
    "\nArticle ",
    "\n\n",
    "\n",
    ". ",
    " ",
    "",
]


def limpiar(texto: str) -> str:
    """Normaliza artefactos típicos de extracción PDF."""
    texto = texto.replace("­", "").replace("ﬁ", "fi").replace("ﬂ", "fl")
    # "modifi catoria", "confi anza": ligadura separada por espacio en El Peruano.
    texto = re.sub(r"(\w)fi (?=[a-záéíóúñ])", r"\1fi", texto)
    texto = re.sub(r"(\w)-\n(\w)", r"\1\2", texto)  # palabras cortadas con guion
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r" *\n *", "\n", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def leer_pdf(ruta: Path) -> tuple[str, list[int]]:
    """Devuelve el texto completo y el offset inicial de cada página."""
    partes, offsets, pos = [], [], 0
    for pagina in PdfReader(ruta).pages:
        texto = limpiar(pagina.extract_text() or "") + "\n\n"
        offsets.append(pos)
        partes.append(texto)
        pos += len(texto)
    return "".join(partes), offsets


def articulo_para(texto: str, inicio: int, fin: int) -> str | None:
    """Artículo al que pertenece un fragmento: el primero que abre dentro de él,
    o en su defecto el último encabezado anterior."""
    dentro = RE_ARTICULO.search(texto, inicio, fin)
    if dentro:
        return dentro.group(1)
    previos = list(RE_ARTICULO.finditer(texto, max(0, inicio - 20000), inicio))
    return previos[-1].group(1) if previos else None


def indice_considerandos(texto: str, hasta: int) -> list[tuple[int, str]]:
    """Posiciones de los considerandos en orden estricto (1, 2, 3...). Exigir la
    secuencia descarta las notas al pie "(1) DO C 229..." que usan el mismo formato."""
    indice, siguiente = [], 1
    for m in RE_CONSIDERANDO.finditer(texto, 0, hasta):
        if int(m.group(1)) == siguiente:
            indice.append((m.start(), m.group(1)))
            siguiente += 1
    return indice


def considerando_para(indice: list[tuple[int, str]], inicio: int, fin: int) -> str | None:
    """Primer considerando que abre dentro del fragmento o, si no hay, el anterior."""
    pos = bisect.bisect_left(indice, (inicio, ""))
    if pos < len(indice) and indice[pos][0] < fin:
        return indice[pos][1]
    return indice[pos - 1][1] if pos > 0 else None


def fragmentar(fuente: Fuente, texto: str, offsets: list[int], cfg: Config) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
        separators=SEPARADORES,
        add_start_index=True,
    )
    docs = splitter.create_documents([texto])
    primer_articulo = RE_ARTICULO.search(texto)
    inicio_articulado = primer_articulo.start() if primer_articulo else None
    considerandos = indice_considerandos(texto, inicio_articulado or 0)
    salida = []
    for i, d in enumerate(docs):
        inicio = d.metadata["start_index"]
        fin = inicio + len(d.page_content)
        meta = {
            "fuente": fuente.sigla,
            "titulo": fuente.titulo,
            "jurisdiccion": fuente.jurisdiccion,
            "tipo": fuente.tipo,
            "archivo": fuente.archivo,
            "pagina": bisect.bisect_right(offsets, inicio),  # 1-indexada
            "chunk": i,
        }
        # Solo las normas tienen articulado; en guías y marcos "Article 29" es ruido
        # (p. ej. "Article 29 Working Party"). Antes del articulado van los considerandos.
        if fuente.tipo == "norma":
            if inicio_articulado is not None and fin <= inicio_articulado:
                ref = considerando_para(considerandos, inicio, fin)
                if ref:
                    meta["considerando"] = ref
            else:
                ref = articulo_para(texto, inicio, fin)
                if ref:
                    meta["articulo"] = ref
        salida.append(Document(page_content=d.page_content, metadata=meta))
    return salida


def cargar_corpus(cfg: Config) -> list[Document]:
    docs: list[Document] = []
    for fuente in CORPUS:
        ruta = cfg.raw_dir / fuente.archivo
        if not ruta.exists():
            print(f"[aviso] falta {ruta.name}, se omite")
            continue
        texto, offsets = leer_pdf(ruta)
        frag = fragmentar(fuente, texto, offsets, cfg)
        print(f"  {fuente.sigla:8} {len(offsets):4} págs -> {len(frag):4} fragmentos")
        docs.extend(frag)
    return docs


def embeddings(cfg: Config, task_type: str):
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(
        model=cfg.embedding_model,
        google_api_key=cfg.api_key,
        task_type=task_type,
        output_dimensionality=cfg.embedding_dim,
    )


def indexar(cfg: Config, reiniciar: bool = True) -> int:
    """Construye el índice vectorial persistente. Devuelve nº de fragmentos."""
    from langchain_chroma import Chroma

    if not cfg.api_key:
        raise SystemExit("Falta GOOGLE_API_KEY (ver .env.example)")
    if reiniciar and cfg.chroma_dir.exists():
        shutil.rmtree(cfg.chroma_dir)

    print("Cargando y fragmentando corpus...")
    docs = cargar_corpus(cfg)

    store = Chroma(
        collection_name=cfg.coleccion,
        embedding_function=embeddings(cfg, "RETRIEVAL_DOCUMENT"),
        persist_directory=str(cfg.chroma_dir),
        collection_metadata={"hnsw:space": "cosine"},
    )
    print(f"Generando embeddings de {len(docs)} fragmentos ({cfg.embedding_model})...")
    for i in range(0, len(docs), cfg.embed_batch):
        lote = docs[i : i + cfg.embed_batch]
        ids = [f"{d.metadata['fuente']}-{d.metadata['chunk']}" for d in lote]
        for intento in range(6):
            try:
                store.add_documents(lote, ids=ids)
                break
            except Exception as e:  # 429 / errores transitorios del free tier
                espera = 15 * (intento + 1)
                print(f"  lote {i}: {type(e).__name__}, reintento en {espera}s")
                time.sleep(espera)
        else:
            raise RuntimeError(f"No se pudo indexar el lote {i}")
        print(f"  {min(i + cfg.embed_batch, len(docs))}/{len(docs)}")
        time.sleep(cfg.embed_pause_s)
    return len(docs)
