import json

import pytest

from agente_terceros.checklist import CLAUSULAS
from agente_terceros.ingest import Fragmento
from agente_terceros.revisor import parsear_json, revisar_dpa
from agente_terceros.vectores import IndiceVectorial

CONTRATO = """CONTRATO DE ENCARGO DE TRATAMIENTO

Cláusula primera. Objeto. El encargado tratará los datos de los trabajadores durante la vigencia del servicio de planillas.

Cláusula segunda. Instrucciones. El encargado tratará los datos únicamente siguiendo instrucciones documentadas del responsable.

Cláusula tercera. Brechas. El encargado notificará al responsable cualquier incidente de seguridad en un plazo de 24 horas.
"""


@pytest.fixture
def normativa(embed):
    idx = IndiceVectorial(embed)
    idx.agregar([
        Fragmento("Artículo 28. El encargado tratará los datos siguiendo instrucciones documentadas",
                  {"fuente": "RGPD", "jurisdiccion": "Unión Europea", "pagina": 49, "articulo": "28", "titulo": "RGPD"}),
        Fragmento("Artículo 36. El encargado debe informar de forma inmediata el incidente de seguridad",
                  {"fuente": "RLPDP", "jurisdiccion": "Perú", "pagina": 22, "articulo": "36", "titulo": "RLPDP"}),
    ])
    return idx


class LLMFalso:
    def __init__(self, respuesta: dict | str):
        self.respuesta = respuesta
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        r = self.respuesta
        return r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)


def _respuesta(**estados):
    return {
        "resumen": "Contrato incompleto.",
        "clausulas": [
            {
                "id": cid,
                "estado": est,
                "evidencia": ev,
                "fundamento": [1],
                "recomendacion": "Añadir la cláusula.",
            }
            for cid, (est, ev) in estados.items()
        ],
    }


def test_cumplimiento_es_ponderado_por_peso(normativa, embed):
    llm = LLMFalso(_respuesta(
        instrucciones=("cumple", "únicamente siguiendo instrucciones documentadas del responsable"),
        notificacion_brechas=("parcial", "notificará al responsable cualquier incidente"),
    ))
    rev = revisar_dpa(CONTRATO, normativa, embed, llm)
    total = sum(c.peso for c in CLAUSULAS)
    assert rev.cumplimiento == pytest.approx((3 * 1 + 3 * 0.5) / total * 100)
    estados = {r.id: r.estado for r in rev.resultados}
    assert estados["instrucciones"] == "cumple"
    assert estados["seguridad"] == "falta"  # el modelo no la evaluó


def test_prompt_incluye_criterios_contrato_y_fragmentos_numerados(normativa, embed):
    llm = LLMFalso(_respuesta())
    revisar_dpa(CONTRATO, normativa, embed, llm)
    (prompt,) = llm.prompts
    assert "subencargados" in prompt and "instrucciones documentadas" in prompt
    assert "[1]" in prompt and "RLPDP, art. 36" in prompt
    assert "Cláusula tercera" in prompt


def test_evidencia_inventada_queda_marcada_como_no_verificada(normativa, embed):
    llm = LLMFalso(_respuesta(
        instrucciones=("cumple", "siguiendo instrucciones documentadas del responsable"),
        seguridad=("cumple", "el encargado aplicará cifrado AES-256 a todos los datos"),
    ))
    res = {r.id: r for r in revisar_dpa(CONTRATO, normativa, embed, llm).resultados}
    assert res["instrucciones"].evidencia_verificada is True
    assert res["seguridad"].evidencia_verificada is False
    # Un "cumple" sin evidencia real en el contrato no puede contar como cumplido.
    assert res["seguridad"].estado == "parcial"


def test_fundamentos_se_traducen_a_etiquetas_de_fuente(normativa, embed):
    llm = LLMFalso(_respuesta(instrucciones=("cumple", "")))
    rev = revisar_dpa(CONTRATO, normativa, embed, llm)
    r = next(r for r in rev.resultados if r.id == "instrucciones")
    assert r.fundamento and all(n in rev.fuentes for n in r.fundamento)
    assert rev.fuentes[r.fundamento[0]]["etiqueta"].startswith(("RGPD", "RLPDP"))


def test_estado_desconocido_e_ids_ajenos_se_ignoran(normativa, embed):
    resp = _respuesta(instrucciones=("excelente", ""))
    resp["clausulas"].append({"id": "inventada", "estado": "cumple"})
    rev = revisar_dpa(CONTRATO, normativa, embed, LLMFalso(resp))
    assert {r.id for r in rev.resultados} == {c.id for c in CLAUSULAS}
    assert next(r for r in rev.resultados if r.id == "instrucciones").estado == "falta"


def test_parsear_json_tolera_bloque_markdown():
    assert parsear_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_contrato_vacio_es_rechazado(normativa, embed):
    with pytest.raises(ValueError):
        revisar_dpa("   ", normativa, embed, LLMFalso(_respuesta()))


def test_evidencia_que_une_frases_literales_de_varias_clausulas_es_verificada():
    from agente_terceros.revisor import _normal, evidencia_en_contrato

    c = _normal(CONTRATO)
    unida = ("El encargado tratará los datos de los trabajadores durante la vigencia del servicio "
             "de planillas. El encargado notificará al responsable cualquier incidente de seguridad")
    assert evidencia_en_contrato(unida, c)
    mezcla = unida + ". El encargado cifrará todo con AES-256 y lo auditará cada mes"
    assert not evidencia_en_contrato(mezcla, c)
