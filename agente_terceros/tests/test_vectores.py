from agente_terceros.ingest import Fragmento
from agente_terceros.vectores import IndiceVectorial


def _frag(texto, fuente="RGPD", jur="Unión Europea"):
    return Fragmento(texto, {"fuente": fuente, "jurisdiccion": jur, "pagina": 1, "articulo": ""})


FRAGS = [
    _frag("el encargado notificará las violaciones de seguridad sin dilación"),
    _frag("subencargado autorización previa por escrito del responsable"),
    _frag("supresión de los datos al finalizar el servicio", "RLPDP", "Perú"),
]


def test_buscar_devuelve_el_fragmento_mas_parecido(embed):
    idx = IndiceVectorial(embed)
    idx.agregar(FRAGS)
    (frag, score), *_ = idx.buscar("autorización previa del subencargado", k=2)
    assert "subencargado" in frag.texto
    assert 0 < score <= 1.0001


def test_buscar_filtra_por_jurisdiccion(embed):
    idx = IndiceVectorial(embed)
    idx.agregar(FRAGS)
    res = idx.buscar("violaciones de seguridad", k=3, filtro={"jurisdiccion": "Perú"})
    assert [f.meta["fuente"] for f, _ in res] == ["RLPDP"]


def test_indice_vacio_devuelve_lista_vacia(embed):
    assert IndiceVectorial(embed).buscar("x", k=3) == []


def test_guardar_y_cargar_conserva_resultados(embed, tmp_path):
    idx = IndiceVectorial(embed)
    idx.agregar(FRAGS)
    idx.guardar(tmp_path)
    otro = IndiceVectorial.cargar(tmp_path, embed)
    assert len(otro) == 3
    assert otro.buscar("supresión de datos", k=1)[0][0].meta["fuente"] == "RLPDP"


def test_construir_indice_desde_corpus_real(embed, tmp_path):
    from dataclasses import replace

    from agente_terceros.config import CORPUS, get_config
    from agente_terceros.vectores import construir_indice

    cfg = replace(get_config(), index_dir=tmp_path)
    idx = construir_indice(cfg, embed)
    fuentes = {f.meta["fuente"] for f in idx.fragmentos}
    assert fuentes == {f.sigla for f in CORPUS}
    arts = {(f.meta["fuente"], f.meta["articulo"]) for f in idx.fragmentos}
    assert ("RLPDP", "32") in arts and ("RGPD", "28") in arts
    assert (tmp_path / "normativa.faiss").exists()
