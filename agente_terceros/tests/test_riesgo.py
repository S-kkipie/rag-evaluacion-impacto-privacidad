from agente_terceros.riesgo import PerfilProveedor, evaluar_proveedor

SEGURO = PerfilProveedor(
    datos_sensibles=False,
    volumen="bajo",
    transferencia_internacional=False,
    pais_adecuado=True,
    certificaciones=("ISO 27001",),
    usa_subencargados=False,
    incidentes_12m=0,
    cumplimiento_dpa=95.0,
    dpa_vigente=True,
)


def test_proveedor_con_buenas_practicas_es_riesgo_bajo():
    ev = evaluar_proveedor(SEGURO)
    assert (ev.probabilidad, ev.impacto, ev.nivel) == (1, 1, "bajo")
    assert ev.revision_meses == 24


def test_peor_caso_es_critico_y_explica_cada_factor():
    from dataclasses import replace

    p = replace(
        SEGURO,
        datos_sensibles=True,
        volumen="alto",
        transferencia_internacional=True,
        pais_adecuado=False,
        certificaciones=(),
        usa_subencargados=True,
        incidentes_12m=3,
        cumplimiento_dpa=None,
        dpa_vigente=False,
    )
    ev = evaluar_proveedor(p)
    assert ev.nivel == "crítico" and ev.puntaje == 16
    texto = " ".join(ev.factores).lower()
    for palabra in ("sensibles", "transferencia", "subencargados", "incidentes", "dpa"):
        assert palabra in texto
    assert any("dpa" in r.lower() for r in ev.recomendaciones)


def test_certificacion_iso_27701_reduce_probabilidad():
    from dataclasses import replace

    base = replace(SEGURO, usa_subencargados=True, incidentes_12m=1, certificaciones=())
    con = replace(base, certificaciones=("ISO 27701",))
    assert evaluar_proveedor(con).probabilidad == evaluar_proveedor(base).probabilidad - 1


def test_dpa_con_bajo_cumplimiento_sube_probabilidad():
    from dataclasses import replace

    ev = evaluar_proveedor(replace(SEGURO, cumplimiento_dpa=50.0, certificaciones=()))
    assert ev.probabilidad == 2
    assert any("50" in f for f in ev.factores)


def test_volumen_invalido_es_rechazado():
    from dataclasses import replace

    import pytest

    with pytest.raises(ValueError):
        evaluar_proveedor(replace(SEGURO, volumen="enorme"))
