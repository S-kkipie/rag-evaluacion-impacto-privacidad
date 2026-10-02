import io

import pytest

from agente_terceros.agente import Agente
from agente_terceros.app import create_app
from agente_terceros.db import Repositorio
from agente_terceros.vectores import IndiceVectorial
from tests.test_agente import PROV, llm_falso


@pytest.fixture
def client(tmp_path, embed):
    agente = Agente(Repositorio(tmp_path / "w.db"), IndiceVectorial(embed), embed, llm_falso)
    app = create_app(agente)
    app.config["TESTING"] = True
    return app.test_client()


def _crear(client, **extra):
    r = client.post("/api/proveedores", json={**PROV, **extra})
    assert r.status_code == 201
    return r.get_json()["id"]


def test_index_sirve_la_interfaz(client):
    r = client.get("/")
    assert r.status_code == 200 and b"Agente de Terceros" in r.data


def test_crear_y_listar_proveedores(client):
    _crear(client)
    (p,) = client.get("/api/proveedores").get_json()
    assert p["nombre"] == "NubeSegura SAC" and p["dpa"]["estado"] == "sin_dpa"


def test_crear_proveedor_sin_nombre_da_400(client):
    r = client.post("/api/proveedores", json={**PROV, "nombre": " "})
    assert r.status_code == 400 and "nombre" in r.get_json()["error"]


def test_proveedor_inexistente_da_404(client):
    assert client.get("/api/proveedores/99").status_code == 404


def test_subir_dpa_txt_crea_aprobacion_pendiente(client):
    pid = _crear(client)
    r = client.post(
        f"/api/proveedores/{pid}/dpa",
        data={"archivo": (io.BytesIO("Contrato de encargo.".encode()), "dpa.txt"),
              "fecha_firma": "2026-01-01", "fecha_vencimiento": "2027-01-01"},
        content_type="multipart/form-data",
    )
    assert r.status_code == 201
    assert r.get_json()["revision"]["cumplimiento"] == 0
    (pend,) = client.get("/api/aprobaciones").get_json()
    r = client.post(f"/api/aprobaciones/{pend['id']}",
                    json={"aprobado": True, "revisor": "Legal", "comentario": "ok"})
    assert r.status_code == 200
    assert client.get(f"/api/tools/check_dpa_status/{pid}").get_json()["estado"] == "vigente"


def test_subir_dpa_sin_fechas_da_400(client):
    pid = _crear(client)
    r = client.post(f"/api/proveedores/{pid}/dpa",
                    data={"archivo": (io.BytesIO(b"x"), "dpa.txt")},
                    content_type="multipart/form-data")
    assert r.status_code == 400


def test_resolver_aprobacion_ya_resuelta_da_409(client):
    pid = _crear(client)
    client.post(f"/api/proveedores/{pid}/subencargados",
                json={"nombre": "AWS", "pais": "EE. UU.", "servicio": "backup"})
    (pend,) = client.get("/api/aprobaciones").get_json()
    body = {"aprobado": False, "revisor": "Legal", "comentario": "no"}
    assert client.post(f"/api/aprobaciones/{pend['id']}", json=body).status_code == 200
    assert client.post(f"/api/aprobaciones/{pend['id']}", json=body).status_code == 409


def test_herramientas_mcp_por_http(client):
    pid = _crear(client)
    assert len(client.get("/api/tools/list_processors").get_json()) == 1
    ev = client.get(f"/api/tools/evaluate_vendor/{pid}").get_json()
    assert ev["nivel"] in {"bajo", "medio", "alto", "crítico"}


def test_brecha_y_consulta_y_panel(client):
    _crear(client)
    assert client.get("/api/brecha?termino=salud").get_json()[0]["nombre"] == "NubeSegura SAC"
    r = client.post("/api/consulta", json={"pregunta": "¿Qué es un encargado?"})
    assert "respuesta" in r.get_json()
    assert client.post("/api/consulta", json={"pregunta": ""}).status_code == 400
    assert client.get("/api/panel").get_json()["total_proveedores"] == 1


def test_checklist_expone_clausulas_y_controles(client):
    d = client.get("/api/checklist").get_json()
    assert len(d["clausulas"]) >= 10 and "A.2.5.8" in {c["ref"] for c in d["controles"]}
