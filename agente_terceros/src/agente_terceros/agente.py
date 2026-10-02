"""Agente de Terceros (DPAs) del PIMS multiagente ISO/IEC 27701:2025.

Controles: A.1.2.7 (contratos con encargados), A.2.5.7 (divulgación de
subcontratistas), A.2.5.8 (contratación de subencargados).
Herramientas expuestas al bus MCP: list_processors, check_dpa_status, evaluate_vendor.
Puerta HITL: todo DPA nuevo y todo cambio de subencargado queda pendiente de
aprobación legal antes de surtir efecto.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import date

from .config import Config, get_config
from .db import Repositorio
from .revisor import LLM, etiqueta, revisar_dpa
from .riesgo import PerfilProveedor, evaluar_proveedor
from .vectores import Embedder, IndiceVectorial

PROMPT_CONSULTA = """Eres un asistente experto en protección de datos que apoya al Agente de \
Terceros de un PIMS (ISO/IEC 27701). Responde SOLO con la información de los FRAGMENTOS y cita \
cada afirmación con su número entre corchetes, p. ej. [2]. Si los fragmentos no bastan, dilo. \
En el Perú rigen la Ley 29733 (LPDP) y su Reglamento (RLPDP); el RGPD, el CEPD y las cláusulas \
tipo de la UE son referencia comparada. Responde en español con una respuesta completa de \
3 a 8 viñetas o párrafos breves, en frases completas redactadas por ti (no copies fragmentos \
truncados). Incluye el contexto relevante (quién debe hacer qué, ante quién y en qué plazo) y \
termina con una línea "Base normativa:" que liste las referencias usadas.

FRAGMENTOS:
{fragmentos}

PREGUNTA: {pregunta}"""


class Agente:
    def __init__(
        self,
        repo: Repositorio,
        normativa: IndiceVectorial,
        embed: Embedder,
        llm: LLM,
        llm_texto: LLM | None = None,
        cfg: Config | None = None,
    ):
        self.repo = repo
        self.normativa = normativa
        self.embed = embed
        self.llm = llm  # salida JSON (revisión de contratos)
        self.llm_texto = llm_texto or llm  # salida libre (consultas)
        self.cfg = cfg or get_config()

    # -- herramientas MCP ---------------------------------------------------
    def check_dpa_status(self, pid: int, hoy: date | None = None) -> dict:
        hoy = hoy or date.today()
        dpas = self.repo.dpas(pid)
        vigente = self.repo.dpa_vigente(pid)
        if vigente:
            dias = (date.fromisoformat(vigente["fecha_vencimiento"]) - hoy).days
            estado = "vencido" if dias < 0 else "por_vencer" if dias <= self.cfg.dias_alerta else "vigente"
            return {
                "estado": estado, "dpa_id": vigente["id"], "dias_restantes": dias,
                "fecha_vencimiento": vigente["fecha_vencimiento"],
                "cumplimiento": vigente["cumplimiento"],
                "pendiente_nuevo": dpas[0]["estado"] == "pendiente_aprobacion",
            }
        if dpas:
            d = dpas[0]
            return {"estado": d["estado"], "dpa_id": d["id"], "dias_restantes": None,
                    "fecha_vencimiento": d["fecha_vencimiento"], "cumplimiento": d["cumplimiento"],
                    "pendiente_nuevo": d["estado"] == "pendiente_aprobacion"}
        return {"estado": "sin_dpa", "dpa_id": None, "dias_restantes": None,
                "fecha_vencimiento": None, "cumplimiento": None, "pendiente_nuevo": False}

    def evaluate_vendor(self, pid: int, hoy: date | None = None) -> dict:
        p = self.repo.proveedor(pid)
        if p is None:
            raise KeyError(f"Proveedor {pid} no existe")
        estado = self.check_dpa_status(pid, hoy)
        perfil = PerfilProveedor(
            datos_sensibles=p["datos_sensibles"],
            volumen=p["volumen"],
            transferencia_internacional=p["transferencia_internacional"],
            pais_adecuado=p["pais_adecuado"],
            certificaciones=tuple(p["certificaciones"]),
            usa_subencargados=any(s["estado"] != "rechazado" for s in self.repo.subencargados(pid)),
            incidentes_12m=p["incidentes_12m"],
            cumplimiento_dpa=estado["cumplimiento"] if estado["estado"] != "rechazado" else None,
            dpa_vigente=estado["estado"] in ("vigente", "por_vencer"),
        )
        return asdict(evaluar_proveedor(perfil))

    def list_processors(self, hoy: date | None = None) -> list[dict]:
        return [
            {**p, "dpa": self.check_dpa_status(p["id"], hoy), "riesgo": self.evaluate_vendor(p["id"], hoy)}
            for p in self.repo.proveedores()
        ]

    # -- revisión de contratos ----------------------------------------------
    def revisar_y_registrar(
        self, pid: int, texto: str, archivo: str, fecha_firma: str, fecha_vencimiento: str
    ) -> dict:
        revision = revisar_dpa(texto, self.normativa, self.embed, self.llm, self.cfg).to_dict()
        did = self.repo.registrar_dpa(
            pid, archivo, fecha_firma, fecha_vencimiento, revision["cumplimiento"], revision
        )
        return {"dpa_id": did, "revision": revision}

    # -- flujo de brecha (colaboración con el Agente de Incidentes) ------------
    def encargados_implicados(self, termino: str, hoy: date | None = None) -> list[dict]:
        res = []
        for p in self.repo.encargados_implicados(termino):
            estado = self.check_dpa_status(p["id"], hoy)
            clausula, evidencia = "sin_revision", ""
            if estado["dpa_id"]:
                revision = self.repo.dpa(estado["dpa_id"])["revision"]
                for r in revision.get("resultados", []):
                    if r["id"] == "notificacion_brechas":
                        clausula, evidencia = r["estado"], r["evidencia"]
            res.append({
                "id": p["id"], "nombre": p["nombre"], "contacto": p["contacto"],
                "categorias_datos": p["categorias_datos"], "sistemas": p["sistemas"],
                "dpa": estado, "clausula_notificacion": clausula, "evidencia": evidencia,
                "subencargados": [s for s in self.repo.subencargados(p["id"]) if s["estado"] == "aprobado"],
            })
        return res

    # -- consulta normativa (RAG) --------------------------------------------
    def consultar(self, pregunta: str, jurisdiccion: str | None = None, k: int = 6) -> dict:
        filtro = {"jurisdiccion": jurisdiccion} if jurisdiccion else None
        frags = [f for f, _ in self.normativa.buscar(pregunta, k=k, filtro=filtro)]
        fuentes = [
            {"n": i, "etiqueta": etiqueta(f.meta), "titulo": f.meta.get("titulo", ""), "texto": f.texto}
            for i, f in enumerate(frags, 1)
        ]
        contexto = "\n\n".join(f"[{s['n']}] ({s['etiqueta']})\n{s['texto']}" for s in fuentes)
        respuesta = self.llm_texto(PROMPT_CONSULTA.format(fragmentos=contexto, pregunta=pregunta))
        return {"respuesta": respuesta, "fuentes": fuentes}

    # -- panel del DPO -------------------------------------------------------
    def panel(self, hoy: date | None = None) -> dict:
        hoy = hoy or date.today()
        proveedores = self.list_processors(hoy)
        return {
            "total_proveedores": len(proveedores),
            "por_nivel": dict(Counter(p["riesgo"]["nivel"] for p in proveedores)),
            "sin_dpa": sum(p["dpa"]["estado"] == "sin_dpa" for p in proveedores),
            "alertas": self.repo.alertas_vencimiento(hoy, self.cfg.dias_alerta),
            "pendientes": self.repo.pendientes(),
            "historial": self.repo.historial(15),
        }
