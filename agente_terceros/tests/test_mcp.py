import asyncio
import json

from agente_terceros.agente import Agente
from agente_terceros.db import Repositorio
from agente_terceros.mcp_server import crear_servidor
from agente_terceros.vectores import IndiceVectorial
from tests.test_agente import PROV, llm_falso


def _servidor(tmp_path, embed):
    agente = Agente(Repositorio(tmp_path / "m.db"), IndiceVectorial(embed), embed, llm_falso)
    pid = agente.repo.crear_proveedor(PROV)
    return crear_servidor(agente), pid


def _json(resultado):
    return json.loads(resultado.content[0].text)


def test_servidor_expone_las_tres_herramientas(tmp_path, embed):
    srv, _ = _servidor(tmp_path, embed)
    nombres = {t.name for t in asyncio.run(srv.list_tools())}
    assert {"list_processors", "check_dpa_status", "evaluate_vendor"} <= nombres


def test_herramientas_devuelven_datos_del_agente(tmp_path, embed):
    srv, pid = _servidor(tmp_path, embed)
    estado = _json(asyncio.run(srv.call_tool("check_dpa_status", {"proveedor_id": pid})))
    assert estado["estado"] == "sin_dpa"
    riesgo = _json(asyncio.run(srv.call_tool("evaluate_vendor", {"proveedor_id": pid})))
    assert riesgo["nivel"] in {"bajo", "medio", "alto", "crítico"}
