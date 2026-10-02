from datetime import date

import pytest

from agente_terceros.db import Repositorio

PROV = {
    "nombre": "NubeSegura SAC",
    "ruc": "20123456789",
    "pais": "Perú",
    "servicio": "Hosting del ERP",
    "contacto": "dpo@nubesegura.pe",
    "categorias_datos": ["identificación", "salud"],
    "sistemas": ["ERP", "Planillas"],
    "datos_sensibles": True,
    "volumen": "medio",
    "transferencia_internacional": False,
    "pais_adecuado": True,
    "certificaciones": ["ISO 27001"],
    "incidentes_12m": 0,
}


@pytest.fixture
def repo(tmp_path):
    return Repositorio(tmp_path / "t.db")


def test_crear_y_obtener_proveedor_conserva_listas(repo):
    pid = repo.crear_proveedor(PROV)
    p = repo.proveedor(pid)
    assert p["nombre"] == "NubeSegura SAC"
    assert p["categorias_datos"] == ["identificación", "salud"]
    assert p["datos_sensibles"] is True


def test_dpa_nuevo_queda_pendiente_de_aprobacion_legal(repo):
    pid = repo.crear_proveedor(PROV)
    did = repo.registrar_dpa(pid, "dpa.pdf", "2026-01-01", "2027-01-01", 85.0, {"items": []})
    assert repo.dpa(did)["estado"] == "pendiente_aprobacion"
    assert repo.dpa_vigente(pid) is None
    (pend,) = repo.pendientes()
    assert pend["tipo"] == "dpa" and pend["ref_id"] == did


def test_aprobar_dpa_lo_deja_vigente_y_registra_auditoria(repo):
    pid = repo.crear_proveedor(PROV)
    did = repo.registrar_dpa(pid, "dpa.pdf", "2026-01-01", "2027-01-01", 85.0, {})
    (pend,) = repo.pendientes()
    repo.resolver_aprobacion(pend["id"], aprobado=True, revisor="Asesoría Legal", comentario="ok")
    assert repo.dpa_vigente(pid)["id"] == did
    assert repo.pendientes() == []
    acciones = [h["accion"] for h in repo.historial()]
    assert "aprobacion_aprobada" in acciones and "dpa_registrado" in acciones


def test_rechazar_aprobacion_resuelta_dos_veces_falla(repo):
    pid = repo.crear_proveedor(PROV)
    repo.registrar_dpa(pid, "dpa.pdf", "2026-01-01", "2027-01-01", 40.0, {})
    (pend,) = repo.pendientes()
    repo.resolver_aprobacion(pend["id"], aprobado=False, revisor="Legal", comentario="faltan cláusulas")
    with pytest.raises(ValueError):
        repo.resolver_aprobacion(pend["id"], aprobado=True, revisor="Legal", comentario="")


def test_subencargado_nuevo_requiere_aprobacion(repo):
    pid = repo.crear_proveedor(PROV)
    sid = repo.agregar_subencargado(pid, "AWS", "EE. UU.", "Almacenamiento")
    assert repo.subencargados(pid)[0]["estado"] == "pendiente"
    (pend,) = repo.pendientes()
    repo.resolver_aprobacion(pend["id"], aprobado=True, revisor="Legal", comentario="")
    assert repo.subencargados(pid)[0] == {**repo.subencargados(pid)[0], "id": sid, "estado": "aprobado"}


def test_alertas_incluyen_dpas_por_vencer_y_vencidos(repo):
    a = repo.crear_proveedor(PROV)
    b = repo.crear_proveedor({**PROV, "nombre": "B"})
    c = repo.crear_proveedor({**PROV, "nombre": "C"})
    for pid, vence in ((a, "2026-11-01"), (b, "2026-09-01"), (c, "2028-01-01")):
        repo.registrar_dpa(pid, "x.pdf", "2025-01-01", vence, 90.0, {})
    for pend in repo.pendientes():
        repo.resolver_aprobacion(pend["id"], True, "Legal", "")
    alertas = repo.alertas_vencimiento(date(2026, 10, 2), dias=60)
    assert {(x["proveedor"], x["tipo"]) for x in alertas} == {
        ("NubeSegura SAC", "por_vencer"),
        ("B", "vencido"),
    }


def test_encargados_implicados_por_categoria_o_sistema(repo):
    repo.crear_proveedor(PROV)
    repo.crear_proveedor({**PROV, "nombre": "Mailer", "categorias_datos": ["contacto"], "sistemas": ["CRM"]})
    assert [p["nombre"] for p in repo.encargados_implicados("salud")] == ["NubeSegura SAC"]
    assert [p["nombre"] for p in repo.encargados_implicados("crm")] == ["Mailer"]
