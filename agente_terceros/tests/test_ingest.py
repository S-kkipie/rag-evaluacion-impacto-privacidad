from agente_terceros.config import CORPUS, Fuente
from agente_terceros.ingest import fragmentar, leer_documento, limpiar

FUENTE = Fuente("x.pdf", "Ley de prueba", "LP", "Perú")


def _texto_paginado(paginas: list[str]) -> tuple[str, list[int]]:
    offsets, pos = [], 0
    for p in paginas:
        offsets.append(pos)
        pos += len(p)
    return "".join(paginas), offsets


def test_limpiar_une_palabras_cortadas_y_espacios():
    assert limpiar("trata-\nmiento   de  datos\n\n\n\nfin") == "tratamiento de datos\n\nfin"


def test_fragmento_hereda_pagina_segun_offset():
    texto, offsets = _texto_paginado(["A" * 50 + "\n\n", "Artículo 31. Encargo\nB" * 3])
    frags = fragmentar(texto, offsets, FUENTE, tamano=60, solape=0)
    assert frags[0].meta["pagina"] == 1
    assert frags[-1].meta["pagina"] == 2


def test_fragmento_detecta_articulo():
    texto, offsets = _texto_paginado(
        ["Artículo 30. Prestación de servicios\nEl encargado no puede transferir.\n\n"
         "Artículo 31. Códigos de conducta\nTexto del 31.\n\n"]
    )
    frags = fragmentar(texto, offsets, FUENTE, tamano=60, solape=0)
    assert [f.meta["articulo"] for f in frags] == ["30", "31"]


def test_fragmento_detecta_clausula_contractual():
    texto, offsets = _texto_paginado(["Cláusula 7\nObligaciones de las partes\n\nTexto largo."])
    frags = fragmentar(texto, offsets, FUENTE, tamano=200, solape=0)
    assert frags[0].meta["articulo"] == "Cláusula 7"


def test_fragmentos_respetan_tamano_y_llevan_fuente():
    texto, offsets = _texto_paginado(["palabra " * 400])
    frags = fragmentar(texto, offsets, FUENTE, tamano=300, solape=50)
    assert len(frags) > 5
    assert all(len(f.texto) <= 300 for f in frags)
    assert frags[0].meta["fuente"] == "LP" and frags[0].meta["jurisdiccion"] == "Perú"


def test_leer_documento_txt_devuelve_una_pagina(tmp_path):
    ruta = tmp_path / "dpa.txt"
    ruta.write_text("Contrato de encargo\n\nCláusula primera", encoding="utf-8")
    texto, offsets = leer_documento(ruta)
    assert "Cláusula primera" in texto and offsets == [0]


def test_corpus_incluye_fuentes_de_encargo():
    siglas = {f.sigla for f in CORPUS}
    assert {"LPDP", "RLPDP", "RGPD", "EDPB-07/2020", "CCT-2021/915"} <= siglas
    assert all(f.ruta.exists() for f in CORPUS)
