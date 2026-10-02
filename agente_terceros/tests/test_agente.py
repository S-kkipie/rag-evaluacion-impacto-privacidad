import json
from datetime import date

import pytest

from agente_terceros.agente import Agente
from agente_terceros.checklist import CLAUSULAS
from agente_terceros.db import Repositorio
from agente_terceros.ingest import Fragmento
from agente_terceros.vectores import IndiceVectorial

HOY = date(2026, 10, 2)
PROV = {
    "nombre": "NubeSegura SAC", "pais": "Perú", "servicio": "ERP",
    "categorias_datos": ["salud"], "sistemas": ["ERP"], "datos_sensibles": True,
    "volumen": "medio", "transferencia_internacional": False, "pais_adecuado": True,
    "certificaciones": [], "incidentes_12m": 0,
}


def llm_falso(prompt: str) -> str:
    if "CONTRATO:" in prompt:
        return json.dumps({"resumen": "ok", "clausulas": [
            {"id": c.id, "estado": "falta", "evidencia": "", "fundamento": [], "recomendacion": "x"}
            for c in CLAUSULAS
        ]})
    return "El encargado debe notificar de inmediato [1]."


@pytest.fixture
def agente(tmp_path, embed):
    idx = IndiceVectorial(embed)
    idx.agregar([Fragmento("Artículo 36. El encargado debe informar de forma inmediata el incidente",
                           {"fuente": "RLPDP", "jurisdiccion": "Perú", "pagina": 22,
                            "articulo": "36", "titulo": "Reglamento"})])
    return Agente(Repositorio(tmp_path / "a.db"), idx, embed, llm_falso)


def test_check_dpa_status_sin_dpa(agente):
    pid = agente.repo.crear_proveedor(PROV)
    assert agente.check_dpa_status(pid, HOY)["estado"] == "sin_dpa"


def test_revisar_dpa_lo_registra_pendiente_de_aprobacion(agente):
    pid = agente.repo.crear_proveedor(PROV)
    res = agente.revisar_y_registrar(pid, "Contrato de servicios sin cláusulas.", "c.txt",
                                     "2026-01-01", "2026-11-15")
    assert res["revision"]["cumplimiento"] == 0
    assert agente.check_dpa_status(pid, HOY)["estado"] == "pendiente_aprobacion"
    assert len(agente.repo.pendientes()) == 1


def test_dpa_aprobado_proximo_a_vencer(agente):
    pid = agente.repo.crear_proveedor(PROV)
    agente.revisar_y_registrar(pid, "Contrato.", "c.txt", "2026-01-01", "2026-11-15")
    agente.repo.resolver_aprobacion(agente.repo.pendientes()[0]["id"], True, "Legal", "")
    st = agente.check_dpa_status(pid, HOY)
    assert st["estado"] == "por_vencer" and st["dias_restantes"] == 44


def test_evaluate_vendor_usa_cumplimiento_del_dpa_y_subencargados(agente):
    pid = agente.repo.crear_proveedor(PROV)
    sin = agente.evaluate_vendor(pid, HOY)
    assert any("Sin DPA" in f for f in sin["factores"])
    agente.repo.agregar_subencargado(pid, "AWS", "EE. UU.", "backup")
    con = agente.evaluate_vendor(pid, HOY)
    assert con["probabilidad"] == sin["probabilidad"] + 1


def test_list_processors_resume_estado_y_riesgo(agente):
    agente.repo.crear_proveedor(PROV)
    (p,) = agente.list_processors(HOY)
    assert p["nombre"] == "NubeSegura SAC"
    assert p["dpa"]["estado"] == "sin_dpa" and p["riesgo"]["nivel"] in {"bajo", "medio", "alto", "crítico"}


def test_encargados_implicados_en_brecha_indican_clausula_de_notificacion(agente):
    pid = agente.repo.crear_proveedor(PROV)
    agente.revisar_y_registrar(pid, "Contrato.", "c.txt", "2026-01-01", "2027-01-01")
    (imp,) = agente.encargados_implicados("salud", HOY)
    assert imp["nombre"] == "NubeSegura SAC"
    assert imp["clausula_notificacion"] == "falta"


def test_consultar_normativa_devuelve_respuesta_y_fuentes(agente):
    r = agente.consultar("¿Qué debe hacer el encargado ante un incidente?")
    assert "[1]" in r["respuesta"]
    assert r["fuentes"][0]["etiqueta"] == "RLPDP, art. 36, p. 22"


def test_panel_resume_alertas_y_pendientes(agente):
    pid = agente.repo.crear_proveedor(PROV)
    agente.revisar_y_registrar(pid, "Contrato.", "c.txt", "2025-01-01", "2026-10-20")
    agente.repo.resolver_aprobacion(agente.repo.pendientes()[0]["id"], True, "Legal", "")
    agente.repo.agregar_subencargado(pid, "AWS", "EE. UU.", "backup")
    panel = agente.panel(HOY)
    assert panel["total_proveedores"] == 1
    assert len(panel["alertas"]) == 1 and len(panel["pendientes"]) == 1
