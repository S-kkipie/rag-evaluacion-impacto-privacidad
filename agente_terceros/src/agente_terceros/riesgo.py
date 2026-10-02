"""Evaluación de riesgo de proveedores (encargados): probabilidad × impacto.

Matriz 4×4 en la línea de la guía AEPD de gestión del riesgo y de la NTP-ISO 31000.
Es determinista a propósito: el auditor debe poder reproducir y explicar el puntaje.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VOLUMEN_IMPACTO = {"bajo": 1, "medio": 2, "alto": 3}  # <1 000, <100 000, ≥100 000 titulares
NIVELES = ((3, "bajo", 24), (6, "medio", 12), (9, "alto", 6), (16, "crítico", 3))
UMBRAL_DPA = 70.0  # % de cumplimiento mínimo aceptable del contrato


@dataclass(frozen=True)
class PerfilProveedor:
    datos_sensibles: bool
    volumen: str  # "bajo" | "medio" | "alto"
    transferencia_internacional: bool
    pais_adecuado: bool
    certificaciones: tuple[str, ...]
    usa_subencargados: bool
    incidentes_12m: int
    cumplimiento_dpa: float | None  # None = sin DPA revisado
    dpa_vigente: bool


@dataclass
class EvaluacionRiesgo:
    probabilidad: int
    impacto: int
    puntaje: int
    nivel: str
    revision_meses: int
    factores: list[str] = field(default_factory=list)
    recomendaciones: list[str] = field(default_factory=list)


def evaluar_proveedor(p: PerfilProveedor) -> EvaluacionRiesgo:
    if p.volumen not in VOLUMEN_IMPACTO:
        raise ValueError(f"volumen inválido: {p.volumen!r}")
    factores, recs = [], []

    impacto = VOLUMEN_IMPACTO[p.volumen]
    factores.append(f"Volumen {p.volumen} de titulares (impacto base {impacto}).")
    if p.datos_sensibles:
        impacto += 1
        factores.append("Trata datos sensibles (+1 impacto).")
        recs.append("Exigir cifrado y control de acceso reforzado para datos sensibles.")

    prob = 1
    if p.transferencia_internacional and not p.pais_adecuado:
        prob += 1
        factores.append("Transferencia internacional a país sin nivel adecuado (+1).")
        recs.append("Formalizar garantías de transferencia (cláusulas tipo) y documentar la base legal.")
    if p.usa_subencargados:
        prob += 1
        factores.append("Usa subencargados (+1).")
        recs.append("Solicitar la lista de subencargados y exigir aviso previo de cambios (A.2.5.7–A.2.5.9).")
    if p.incidentes_12m >= 3:
        prob += 2
        factores.append(f"{p.incidentes_12m} incidentes en 12 meses (+2).")
    elif p.incidentes_12m > 0:
        prob += 1
        factores.append(f"{p.incidentes_12m} incidente(s) en 12 meses (+1).")
    if p.incidentes_12m:
        recs.append("Revisar los informes de incidentes y las acciones correctivas del proveedor.")
    if p.cumplimiento_dpa is None:
        prob += 1
        factores.append("Sin DPA revisado (+1).")
        recs.append("Firmar o revisar el DPA con el agente antes de continuar el encargo.")
    elif p.cumplimiento_dpa < UMBRAL_DPA:
        prob += 1
        factores.append(f"DPA con cumplimiento de {p.cumplimiento_dpa:.0f}% (< {UMBRAL_DPA:.0f}%) (+1).")
        recs.append("Negociar una adenda al DPA que cubra las cláusulas faltantes.")
    if not p.dpa_vigente:
        prob += 1
        factores.append("DPA vencido o inexistente (+1).")
        recs.append("Renovar el DPA: sin contrato vigente el encargo no tiene base (RGPD 28.3, LPDP 30).")
    if "ISO 27701" in p.certificaciones:
        prob -= 1
        factores.append("Certificación ISO/IEC 27701 (−1).")

    prob, impacto = max(1, min(prob, 4)), min(impacto, 4)
    puntaje = prob * impacto
    nivel, meses = next((n, m) for tope, n, m in NIVELES if puntaje <= tope)
    return EvaluacionRiesgo(prob, impacto, puntaje, nivel, meses, factores, recs)
