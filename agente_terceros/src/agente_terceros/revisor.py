"""Revisión de un contrato de encargo (DPA) contra las cláusulas mínimas exigibles.

Flujo: fragmentos normativos por cláusula (RAG sobre FAISS) + texto del contrato
-> una sola llamada al LLM con salida JSON -> validación (ids, estados, evidencia
literal) -> porcentaje de cumplimiento ponderado.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Callable

from .checklist import CLAUSULAS, Clausula
from .config import Config, Fuente, get_config
from .ingest import Fragmento, fragmentar, limpiar
from .vectores import Embedder, IndiceVectorial

LLM = Callable[[str], str]

VALOR = {"cumple": 1.0, "parcial": 0.5, "falta": 0.0}
MAX_CONTRATO_COMPLETO = 30_000  # caracteres; por encima se envían solo fragmentos relevantes

PROMPT = """Eres un auditor de protección de datos personales. Revisa el CONTRATO DE ENCARGO \
(DPA) entre un responsable y un encargado del tratamiento y determina, para cada CLÁUSULA \
MÍNIMA, si el contrato la contempla.

Reglas:
1. Usa SOLO el texto del CONTRATO para decidir el estado; los FRAGMENTOS NORMATIVOS son el \
fundamento legal.
2. estado: "cumple" (la cláusula está completa), "parcial" (aparece pero incompleta o ambigua) \
o "falta" (no aparece).
3. evidencia: copia LITERAL la frase del contrato que lo demuestra (máx. 300 caracteres); \
cadena vacía si falta.
4. fundamento: lista con los números [n] de los fragmentos normativos que sustentan el requisito.
5. recomendacion: qué añadir o corregir en el contrato (vacía si cumple). En el Perú rigen la \
Ley 29733 (LPDP) y su Reglamento (RLPDP); el RGPD, las directrices del CEPD y las cláusulas tipo \
de la UE son referencia de buenas prácticas.
6. No inventes artículos ni plazos.

Responde SOLO con JSON con esta forma:
{{"resumen": "2-3 frases", "clausulas": [{{"id": "...", "estado": "...", "evidencia": "...", \
"fundamento": [1, 2], "recomendacion": "..."}}]}}

CLÁUSULAS MÍNIMAS:
{clausulas}

FRAGMENTOS NORMATIVOS:
{fragmentos}

CONTRATO:
{contrato}
"""


@dataclass
class ResultadoClausula:
    id: str
    titulo: str
    peso: int
    rgpd: str
    peru: str
    iso: tuple[str, ...]
    estado: str
    evidencia: str
    evidencia_verificada: bool
    fundamento: list[int]
    recomendacion: str


@dataclass
class RevisionDPA:
    cumplimiento: float
    resumen: str
    resultados: list[ResultadoClausula]
    fuentes: dict[int, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["fuentes"] = {str(k): v for k, v in self.fuentes.items()}
        return d


def etiqueta(meta: dict) -> str:
    art = meta.get("articulo") or ""
    if art.startswith("Cláusula"):
        ref = f", {art.lower()}"
    elif art:
        ref = f", art. {art}"
    else:
        ref = ""
    return f"{meta['fuente']}{ref}, p. {meta['pagina']}"


def parsear_json(texto: str) -> dict:
    texto = texto.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", texto, re.S)
    if m:
        texto = m.group(1)
    inicio, fin = texto.find("{"), texto.rfind("}")
    return json.loads(texto[inicio:fin + 1])


def _normal(s: str) -> str:
    s = re.sub(r"[\"'“”«»‘’]", "", s.lower())
    return re.sub(r"\s+", " ", s).strip(" .;:,…")


def evidencia_en_contrato(evidencia: str, contrato_normal: str) -> bool:
    """Acepta la evidencia si cada frase citada (≥ 20 car.) aparece literal en el contrato.

    El modelo a veces une frases de cláusulas distintas o abrevia con "..."; se
    verifica frase a frase para tolerar eso sin aceptar texto inventado.
    """
    tramos = [_normal(t) for t in re.split(r"\.\.\.|…|\[\.\.\.\]|(?<=[.;:])\s+", evidencia)]
    largos = [t for t in tramos if len(t) >= 20]
    return bool(largos) and all(t in contrato_normal for t in largos)


def _recuperar_normativa(
    normativa: IndiceVectorial, c: Clausula, cfg: Config
) -> list[Fragmento]:
    # Siempre al menos dos fragmentos peruanos: son la norma aplicable al caso.
    peru = normativa.buscar(c.consulta, k=2, filtro={"jurisdiccion": "Perú"})
    general = normativa.buscar(c.consulta, k=cfg.top_k)
    vistos, frags = set(), []
    for f, _ in peru + general:
        if id(f) not in vistos:
            vistos.add(id(f))
            frags.append(f)
    return frags


def _texto_contrato(contrato: str, embed: Embedder, cfg: Config) -> str:
    if len(contrato) <= MAX_CONTRATO_COMPLETO:
        return contrato
    idx = IndiceVectorial(embed)
    idx.agregar(fragmentar(contrato, [0], Fuente("", "Contrato", "DPA", "—"), 800, 100))
    partes = []
    for c in CLAUSULAS:
        for f, _ in idx.buscar(c.criterio, k=cfg.top_k_contrato):
            if f.texto not in partes:
                partes.append(f.texto)
    return "\n[...]\n".join(partes)


def revisar_dpa(
    contrato: str, normativa: IndiceVectorial, embed: Embedder, llm: LLM, cfg: Config | None = None
) -> RevisionDPA:
    cfg = cfg or get_config()
    contrato = limpiar(contrato)
    if not contrato:
        raise ValueError("El contrato está vacío o no se pudo extraer su texto")

    # Numeración global de fragmentos normativos, compartida por todas las cláusulas.
    numeros: dict[int, int] = {}
    fuentes: dict[int, dict] = {}
    bloques_clausulas = []
    for c in CLAUSULAS:
        refs = []
        for f in _recuperar_normativa(normativa, c, cfg):
            if id(f) not in numeros:
                n = len(numeros) + 1
                numeros[id(f)] = n
                fuentes[n] = {"etiqueta": etiqueta(f.meta), "titulo": f.meta.get("titulo", ""),
                              "jurisdiccion": f.meta["jurisdiccion"], "texto": f.texto}
            refs.append(numeros[id(f)])
        bloques_clausulas.append(
            f"- id: {c.id} | {c.titulo}\n  Criterio: {c.criterio}\n"
            f"  Base: RGPD {c.rgpd}; Perú {c.peru}; ISO/IEC 27701 {', '.join(c.iso)}\n"
            f"  Fragmentos sugeridos: {', '.join(f'[{n}]' for n in refs)}"
        )
    bloque_frags = "\n\n".join(
        f"[{n}] ({d['etiqueta']} — {d['jurisdiccion']})\n{d['texto']}" for n, d in fuentes.items()
    )
    prompt = PROMPT.format(
        clausulas="\n".join(bloques_clausulas),
        fragmentos=bloque_frags,
        contrato=_texto_contrato(contrato, embed, cfg),
    )
    datos = parsear_json(llm(prompt))

    por_id = {d.get("id"): d for d in datos.get("clausulas", []) if isinstance(d, dict)}
    contrato_normal = _normal(contrato)
    resultados = []
    for c in CLAUSULAS:
        d = por_id.get(c.id, {})
        estado = str(d.get("estado", "")).strip().lower()
        recomendacion = str(d.get("recomendacion") or "")
        if estado not in VALOR:
            estado = "falta"
            recomendacion = recomendacion or "El modelo no evaluó esta cláusula: revisar manualmente."
        evidencia = str(d.get("evidencia") or "").strip()
        verificada = bool(evidencia) and evidencia_en_contrato(evidencia, contrato_normal)
        if estado == "cumple" and not verificada:
            # Sin cita literal comprobable no se acepta como cumplida.
            estado = "parcial"
            recomendacion = recomendacion or "Verificar manualmente: la evidencia citada no aparece en el contrato."
        fundamento = [n for n in d.get("fundamento", []) if isinstance(n, int) and n in fuentes]
        resultados.append(ResultadoClausula(
            c.id, c.titulo, c.peso, c.rgpd, c.peru, c.iso, estado, evidencia, verificada,
            fundamento, recomendacion,
        ))

    total = sum(r.peso for r in resultados)
    cumplimiento = sum(r.peso * VALOR[r.estado] for r in resultados) / total * 100
    return RevisionDPA(cumplimiento, str(datos.get("resumen", "")), resultados, fuentes)


def llm_gemini(cfg: Config, json_salida: bool = True) -> LLM:
    import logging

    from google import genai
    from google.genai import types

    # Aviso ruidoso e irrelevante del SDK sobre "automatic function calling".
    logging.getLogger("google_genai.models").setLevel(logging.ERROR)

    if not cfg.api_key:
        raise RuntimeError("Falta GOOGLE_API_KEY en .env")
    cliente = genai.Client(api_key=cfg.api_key)

    def llamar(prompt: str) -> str:
        r = cliente.models.generate_content(
            model=cfg.llm_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=cfg.temperature,
                response_mime_type="application/json" if json_salida else "text/plain",
            ),
        )
        return r.text

    return llamar
