from agente_terceros.checklist import CLAUSULAS, CONTROLES_ISO, por_id


def test_checklist_cubre_requisitos_minimos_del_art_28_3():
    ids = {c.id for c in CLAUSULAS}
    esperados = {
        "objeto_duracion",
        "instrucciones",
        "confidencialidad",
        "seguridad",
        "subencargados",
        "derechos_titulares",
        "notificacion_brechas",
        "supresion_devolucion",
        "auditorias",
        "transferencias",
    }
    assert esperados <= ids


def test_cada_clausula_tiene_fundamento_normativo_y_control_iso():
    for c in CLAUSULAS:
        assert c.titulo and c.criterio
        assert c.rgpd or c.peru, c.id
        assert c.iso and all(ref in CONTROLES_ISO for ref in c.iso), c.id
        assert 1 <= c.peso <= 3


def test_controles_iso_del_agente_de_terceros_estan_catalogados():
    for ref in ("A.1.2.7", "A.2.5.7", "A.2.5.8"):
        assert ref in CONTROLES_ISO


def test_por_id_devuelve_la_clausula():
    assert por_id("subencargados").titulo.lower().startswith("subencarg")
