"""Configuración central del RAG: rutas, modelos, parámetros y corpus."""

from dataclasses import dataclass, field
from pathlib import Path
import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Fuente:
    """Documento normativo o metodológico del corpus."""

    archivo: str
    titulo: str
    sigla: str
    jurisdiccion: str
    tipo: str  # "norma" | "guia" | "marco"
    url: str


CORPUS: tuple[Fuente, ...] = (
    Fuente(
        "ley_29733_peru.pdf",
        "Ley N.º 29733, Ley de Protección de Datos Personales",
        "LPDP",
        "Perú",
        "norma",
        "https://www.minjus.gob.pe/wp-content/uploads/2013/04/LEY-29733.pdf",
    ),
    Fuente(
        "ds_016_2024_jus_reglamento.pdf",
        "D.S. N.º 016-2024-JUS, Reglamento de la Ley N.º 29733",
        "RLPDP",
        "Perú",
        "norma",
        "https://www.gob.pe/institucion/anpd/normas-legales/6554453-n-016-2024-jus",
    ),
    Fuente(
        "rgpd_2016_679_es.pdf",
        "Reglamento (UE) 2016/679 — Reglamento General de Protección de Datos",
        "RGPD",
        "Unión Europea",
        "norma",
        "https://www.boe.es/doue/2016/119/L00001-00088.pdf",
    ),
    Fuente(
        "edpb_wp248_dpia_es.pdf",
        "WP248 rev.01 — Directrices sobre la evaluación de impacto relativa a la protección de datos",
        "WP248",
        "Unión Europea",
        "guia",
        "https://ec.europa.eu/newsroom/article29/items/611236",
    ),
    Fuente(
        "aepd_gestion_riesgo_eipd.pdf",
        "AEPD — Gestión del riesgo y evaluación de impacto en tratamientos de datos personales",
        "AEPD",
        "España",
        "guia",
        "https://www.aepd.es/guias/gestion-riesgo-y-evaluacion-impacto-en-tratamientos-datos-personales.pdf",
    ),
    Fuente(
        "nist_privacy_framework_v1.pdf",
        "NIST Privacy Framework v1.0",
        "NIST-PF",
        "EE. UU.",
        "marco",
        "https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.01162020.pdf",
    ),
)


@dataclass(frozen=True)
class Config:
    raw_dir: Path = ROOT / "data" / "raw"
    chroma_dir: Path = ROOT / "data" / "chroma"
    coleccion: str = "pia_normativa"

    embedding_model: str = os.getenv("PIA_EMBEDDING_MODEL", "models/gemini-embedding-001")
    embedding_dim: int = int(os.getenv("PIA_EMBEDDING_DIM", "768"))
    llm_model: str = os.getenv("PIA_LLM_MODEL", "gemini-2.5-flash")
    temperature: float = 0.1

    chunk_size: int = 1200
    chunk_overlap: int = 200
    top_k: int = 6
    fetch_k: int = 24  # candidatos previos al re-ranking MMR
    mmr_lambda: float = 0.6

    # Límites del free tier de Gemini: lotes pequeños con pausa entre ellos.
    embed_batch: int = 50
    embed_pause_s: float = 2.0

    api_key: str | None = field(
        default_factory=lambda: os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    )


def get_config() -> Config:
    return Config()
