"""Recuperación + generación fundamentada con citas."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from .config import Config, get_config
from .ingest import embeddings

SISTEMA = """Eres un asistente experto en protección de datos personales que apoya \
a auditores en la Evaluación de Impacto relativa a la Protección de Datos (EIPD / PIA).

Reglas:
1. Responde SOLO con la información de los FRAGMENTOS. Si no bastan, dilo \
explícitamente ("El corpus no contiene información suficiente sobre...").
2. Cita cada afirmación con la etiqueta del fragmento entre corchetes, p. ej. [2].
3. Distingue la jurisdicción: en Perú rigen la Ley 29733 (LPDP) y su Reglamento \
D.S. 016-2024-JUS (RLPDP); el RGPD, las directrices WP248, la guía AEPD y el NIST \
Privacy Framework son referencias metodológicas o de derecho comparado.
4. Responde en español, de forma estructurada y concisa (viñetas si ayuda).
5. No inventes números de artículo ni plazos."""

HUMANO = """FRAGMENTOS:
{contexto}

PREGUNTA: {pregunta}"""

# Aviso ruidoso e irrelevante del SDK de Gemini sobre "automatic function calling".
logging.getLogger("google_genai.models").setLevel(logging.ERROR)

PROMPT = ChatPromptTemplate.from_messages([("system", SISTEMA), ("human", HUMANO)])


@dataclass
class Respuesta:
    pregunta: str
    respuesta: str
    fuentes: list[Document]


def etiqueta(doc: Document) -> str:
    m = doc.metadata
    if m.get("articulo"):
        ref = f", art. {m['articulo']}"
    elif m.get("considerando"):
        ref = f", cons. {m['considerando']}"
    else:
        ref = ""
    return f"{m['fuente']}{ref}, p. {m['pagina']}"


def formatear_contexto(docs: list[Document]) -> str:
    return "\n\n".join(
        f"[{i}] ({etiqueta(d)} — {d.metadata['jurisdiccion']})\n{d.page_content}"
        for i, d in enumerate(docs, 1)
    )


@lru_cache(maxsize=1)
def _store(cfg: Config):
    from langchain_chroma import Chroma

    if not cfg.chroma_dir.exists():
        raise SystemExit("No existe el índice. Ejecuta primero: pia-rag ingest")
    return Chroma(
        collection_name=cfg.coleccion,
        embedding_function=embeddings(cfg, "RETRIEVAL_QUERY"),
        persist_directory=str(cfg.chroma_dir),
    )


@lru_cache(maxsize=1)
def _llm(cfg: Config):
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=cfg.llm_model, temperature=cfg.temperature, google_api_key=cfg.api_key
    )


def recuperar(
    pregunta: str, cfg: Config | None = None, jurisdiccion: str | None = None, k: int | None = None
) -> list[Document]:
    """Búsqueda semántica con re-ranking MMR para diversificar fuentes."""
    cfg = cfg or get_config()
    filtro = {"jurisdiccion": jurisdiccion} if jurisdiccion else None
    return _store(cfg).max_marginal_relevance_search(
        pregunta,
        k=k or cfg.top_k,
        fetch_k=cfg.fetch_k,
        lambda_mult=cfg.mmr_lambda,
        filter=filtro,
    )


def consultar(
    pregunta: str, cfg: Config | None = None, jurisdiccion: str | None = None
) -> Respuesta:
    cfg = cfg or get_config()
    docs = recuperar(pregunta, cfg, jurisdiccion)
    mensajes = PROMPT.format_messages(contexto=formatear_contexto(docs), pregunta=pregunta)
    salida = _llm(cfg).invoke(mensajes)
    texto = salida.content if isinstance(salida.content, str) else salida.text
    return Respuesta(pregunta, texto, docs)
