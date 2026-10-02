"""Escenario de demostración: cuatro encargados ficticios de una universidad."""

from __future__ import annotations

from datetime import date, timedelta

from .agente import Agente
from .config import ROOT

EJEMPLOS = ROOT / "data" / "ejemplos"

PROVEEDORES = [
    {
        "nombre": "NubeSegura S.A.C.", "ruc": "20123456789", "pais": "Perú",
        "servicio": "Alojamiento y operación del ERP de planillas",
        "contacto": "dpo@nubesegura.pe",
        "categorias_datos": ["identificación", "económicos", "salud"],
        "sistemas": ["ERP", "Planillas"],
        "datos_sensibles": True, "volumen": "medio",
        "transferencia_internacional": True, "pais_adecuado": True,
        "certificaciones": ["ISO 27001", "ISO 27701"], "incidentes_12m": 0,
    },
    {
        "nombre": "MailRápido LLC", "ruc": "", "pais": "EE. UU.",
        "servicio": "Envío de boletines a postulantes",
        "contacto": "legal@mailrapido.com",
        "categorias_datos": ["identificación", "contacto"],
        "sistemas": ["CRM de admisión"],
        "datos_sensibles": False, "volumen": "alto",
        "transferencia_internacional": True, "pais_adecuado": False,
        "certificaciones": [], "incidentes_12m": 1,
    },
    {
        "nombre": "PagoFácil Perú S.A.", "ruc": "20555111222", "pais": "Perú",
        "servicio": "Pasarela de pagos de pensiones",
        "contacto": "cumplimiento@pagofacil.pe",
        "categorias_datos": ["identificación", "económicos"],
        "sistemas": ["Tesorería", "Portal del estudiante"],
        "datos_sensibles": False, "volumen": "alto",
        "transferencia_internacional": False, "pais_adecuado": True,
        "certificaciones": ["ISO 27001", "PCI DSS"], "incidentes_12m": 0,
    },
    {
        "nombre": "LabClínico Arequipa E.I.R.L.", "ruc": "20601234567", "pais": "Perú",
        "servicio": "Exámenes médicos ocupacionales",
        "contacto": "gerencia@labclinico.pe",
        "categorias_datos": ["identificación", "salud"],
        "sistemas": ["Salud ocupacional"],
        "datos_sensibles": True, "volumen": "medio",
        "transferencia_internacional": False, "pais_adecuado": True,
        "certificaciones": [], "incidentes_12m": 2,
    },
]


def sembrar_demo(agente: Agente, hoy: date | None = None) -> bool:
    """Carga el escenario si la base está vacía. Revisa dos DPAs con el LLM real."""
    hoy = hoy or date.today()
    repo = agente.repo
    if repo.proveedores():
        return False
    nube, mail, pago, _lab = (repo.crear_proveedor(p, actor="demo") for p in PROVEEDORES)

    # 1) DPA completo, revisado por el agente y aprobado por Legal.
    agente.revisar_y_registrar(
        nube, (EJEMPLOS / "dpa_nubesegura_completo.txt").read_text(encoding="utf-8"),
        "dpa_nubesegura_completo.txt", "2026-01-15", "2028-01-14",
    )
    repo.resolver_aprobacion(repo.pendientes()[-1]["id"], True, "Asesoría Legal", "Conforme.")
    repo.agregar_subencargado(nube, "Amazon Web Services", "Brasil", "Respaldos cifrados")
    repo.resolver_aprobacion(repo.pendientes()[-1]["id"], True, "Asesoría Legal",
                             "Autorizado en la cláusula octava del DPA.")

    # 2) Contrato deficiente: queda pendiente de la decisión de Legal (HITL).
    agente.revisar_y_registrar(
        mail, (EJEMPLOS / "dpa_mailrapido_deficiente.txt").read_text(encoding="utf-8"),
        "dpa_mailrapido_deficiente.txt", "2025-12-01", "2026-11-30",
    )
    repo.agregar_subencargado(mail, "Mixpanel Inc.", "EE. UU.", "Analítica de aperturas")

    # 3) DPA vigente firmado antes del agente, próximo a vencer.
    repo.registrar_dpa(pago, "dpa_pagofacil_2024.pdf", "2024-11-01",
                       (hoy + timedelta(days=25)).isoformat(), 78.0,
                       {"resumen": "Registrado sin revisión automática (contrato previo).",
                        "resultados": []}, actor="demo")
    repo.resolver_aprobacion(repo.pendientes()[-1]["id"], True, "Asesoría Legal",
                             "Contrato vigente heredado.")
    # 4) LabClínico trata datos de salud sin DPA: el agente lo marca como crítico.
    return True
