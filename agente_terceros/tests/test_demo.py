from datetime import date

from agente_terceros.agente import Agente
from agente_terceros.db import Repositorio
from agente_terceros.demo import sembrar_demo
from agente_terceros.vectores import IndiceVectorial
from tests.test_agente import llm_falso


def test_demo_crea_escenario_completo_una_sola_vez(tmp_path, embed):
    agente = Agente(Repositorio(tmp_path / "d.db"), IndiceVectorial(embed), embed, llm_falso)
    assert sembrar_demo(agente, hoy=date(2026, 10, 2)) is True
    assert sembrar_demo(agente, hoy=date(2026, 10, 2)) is False  # idempotente
    panel = agente.panel(date(2026, 10, 2))
    assert panel["total_proveedores"] == 4
    assert panel["sin_dpa"] == 1
    assert panel["alertas"] and panel["pendientes"]
    assert agente.encargados_implicados("salud", date(2026, 10, 2))
