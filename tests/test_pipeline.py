from langchain_core.documents import Document

from pia_rag.config import CORPUS, get_config
from pia_rag.evaluacion import es_relevante, metricas
from pia_rag.ingest import articulo_para, fragmentar, limpiar
from pia_rag.rag import etiqueta, formatear_contexto


def doc(fuente, articulo=None, pagina=1):
    meta = {"fuente": fuente, "pagina": pagina, "jurisdiccion": "Perú", "titulo": fuente}
    if articulo:
        meta["articulo"] = articulo
    return Document(page_content="texto", metadata=meta)


def test_limpiar_ligaduras_y_guiones():
    assert limpiar("modifi catoria") == "modificatoria"
    assert limpiar("protec-\nción   de\n\n\n\ndatos") == "protección de\n\ndatos"


def test_articulo_para_detecta_encabezado_dentro_y_previo():
    texto = "Preámbulo\nArtículo 40. Evaluación de impacto\n40.1 texto largo\nmás texto"
    assert articulo_para(texto, 0, len(texto)) == "40"
    inicio = texto.index("más")
    assert articulo_para(texto, inicio, len(texto)) == "40"
    assert articulo_para("sin encabezados", 0, 15) is None


def test_fragmentar_asigna_pagina_y_articulo():
    cfg = get_config()
    pag1 = "Artículo 1. Objeto\n" + "a " * 700 + "\n\n"
    pag2 = "Artículo 2. Definiciones\n" + "b " * 700
    frags = fragmentar(CORPUS[0], pag1 + pag2, [0, len(pag1)], cfg)
    assert frags[0].metadata["pagina"] == 1 and frags[0].metadata["articulo"] == "1"
    assert frags[-1].metadata["pagina"] == 2 and frags[-1].metadata["articulo"] == "2"
    assert all(len(f.page_content) <= cfg.chunk_size for f in frags)


def test_relevancia_por_fuente_y_articulo():
    esperado = [{"fuente": "RGPD", "articulos": ["35"]}, {"fuente": "WP248"}]
    assert es_relevante(doc("RGPD", "35"), esperado)
    assert not es_relevante(doc("RGPD", "36"), esperado)
    assert es_relevante(doc("WP248"), esperado)
    assert not es_relevante(doc("LPDP", "35"), esperado)


def test_metricas_mrr_y_precision():
    esperado = [{"fuente": "LPDP"}]
    m = metricas([doc("RGPD"), doc("LPDP"), doc("LPDP"), doc("AEPD")], esperado)
    assert m["hit"] and m["rr"] == 0.5 and m["precision"] == 0.5
    assert metricas([doc("RGPD")], esperado)["rr"] == 0.0


def test_etiqueta_y_contexto_numerado():
    d = doc("RLPDP", "40", 24)
    assert etiqueta(d) == "RLPDP, art. 40, p. 24"
    assert formatear_contexto([d, doc("NIST-PF")]).startswith("[1] (RLPDP, art. 40, p. 24")


def test_considerandos_en_secuencia_ignoran_notas_al_pie():
    from pia_rag.ingest import considerando_para, indice_considerandos

    texto = "(1) La protección...\n(1) DO C 229.\n(2) El tratamiento...\n(3) La Directiva...\nArtículo 1\n"
    indice = indice_considerandos(texto, texto.index("Artículo"))
    assert [n for _, n in indice] == ["1", "2", "3"]
    assert considerando_para(indice, texto.index("(2)"), texto.index("(3)")) == "2"


def test_relevancia_por_considerando_y_etiqueta():
    d = Document(page_content="x", metadata={"fuente": "RGPD", "considerando": "91", "pagina": 17,
                                             "jurisdiccion": "Unión Europea"})
    assert es_relevante(d, [{"fuente": "RGPD", "articulos": ["35"], "considerandos": ["91"]}])
    assert not es_relevante(d, [{"fuente": "RGPD", "articulos": ["35"]}])
    assert etiqueta(d) == "RGPD, cons. 91, p. 17"


def test_guias_no_tienen_articulado():
    frags = fragmentar(CORPUS[3], "ARTICLE 29 DATA PROTECTION WORKING PARTY\ntexto", [0], get_config())
    assert "articulo" not in frags[0].metadata
