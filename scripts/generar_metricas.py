"""Genera docs/informe/metricas.tex y docs/diapos/metricas.tex a partir de eval/resultados/.

Así las cifras del informe y de las diapositivas salen siempre de la última evaluación.
Uso: uv run python scripts/generar_metricas.py
"""

import json
import re
from pathlib import Path

from pypdf import PdfReader

from pia_rag.config import CORPUS, ROOT, get_config
from pia_rag.ingest import cargar_corpus

RES = ROOT / "eval" / "resultados"


def num(x: float) -> str:
    return f"{x:.3f}".replace(".", "{,}")


def tex_escape(s: str) -> str:
    return (s.replace("\\", "").replace("&", "\\&").replace("%", "\\%").replace("#", "\\#")
             .replace("_", "\\_"))


def main() -> None:
    cfg = get_config()
    rec = json.loads((RES / "recuperacion.json").read_text(encoding="utf-8"))["resumen"]
    sim, mmr = rec["similitud"], rec["mmr"]
    k = cfg.top_k

    docs = cargar_corpus(cfg)
    filas, total_pag = [], 0
    for f in CORPUS:
        pags = len(PdfReader(cfg.raw_dir / f.archivo).pages)
        total_pag += pags
        n = sum(d.metadata["fuente"] == f.sigla for d in docs)
        corto = f.titulo.split("—")[0].split(",")[0].strip()
        filas.append(f"{f.sigla} & {tex_escape(corto)} ({f.jurisdiccion}) & {pags} & {n} \\\\")

    resp = (RES / "respuestas.md").read_text(encoding="utf-8")
    m = re.search(r"Respuestas con citas: (\d+)/(\d+) · latencia media: ([\d.]+) s", resp)
    citas, n_preg, lat_gen = int(m.group(1)), int(m.group(2)), float(m.group(3))

    # Extracto de la respuesta a la pregunta 3 (obligatoriedad en Perú).
    bloque = resp.split("## 3.")[1].split("**Fuentes recuperadas:**")[0]
    cuerpo = bloque.split("\n", 1)[1].strip()
    lineas, ancho = [], 0
    for par in cuerpo.splitlines():
        if par.strip():
            lineas.append(par.strip().replace("*   ", "- ").replace("**", ""))
    ejemplo = "\n".join(lineas[:9])

    if abs(mmr["mrr"] - sim["mrr"]) < 1e-9:
        frase_mrr = "ambas estrategias empatan en MRR"
    else:
        mejor = "MMR" if mmr["mrr"] > sim["mrr"] else "la similitud pura"
        frase_mrr = f"en MRR el mejor resultado lo obtiene {mejor}"
    analisis_rec = (
        f"Ambas estrategias recuperan al menos un fragmento relevante en "
        f"{'todas' if sim[f'hit@{k}'] == 1 and mmr[f'hit@{k}'] == 1 else 'la mayoría de'} las "
        f"preguntas (Hit@{k} de {num(sim[f'hit@{k}'])} con similitud y {num(mmr[f'hit@{k}'])} con MMR). "
        f"MMR eleva la diversidad de fuentes por consulta de {num(sim['fuentes_distintas_prom'])} a "
        f"{num(mmr['fuentes_distintas_prom'])}, lo que aporta contexto comparado; "
        f"{frase_mrr}. "
        f"La menor P@{k} de MMR es esperable: al penalizar la redundancia sustituye fragmentos "
        f"contiguos del mismo artículo por fragmentos de otras fuentes."
    )
    n_insuf = resp.count("no contiene información suficiente")
    analisis_gen = (
        "En la inspección manual (\\texttt{eval/resultados/respuestas.md}), las respuestas "
        "distinguen correctamente el carácter facultativo de la EIPD en el Perú frente a su "
        "obligatoriedad en el RGPD, y no se observaron artículos inventados. "
        f"En {n_insuf} respuestas el modelo advierte de forma explícita que el corpus no cubre "
        "una parte de la pregunta (p. ej., que no existe una lista peruana de criterios de alto "
        "riesgo equivalente a WP248). Es el comportamiento esperado del prompt de fundamentación."
    )

    macros = {
        "NumPreguntas": str(n_preg),
        "NumFragmentos": str(len(docs)),
        "NumPaginas": str(total_pag),
        "HitSim": num(sim[f"hit@{k}"]), "MrrSim": num(sim["mrr"]), "PSim": num(sim[f"p@{k}"]),
        "DivSim": num(sim["fuentes_distintas_prom"]), "LatSim": num(sim["latencia_prom_s"]),
        "HitMMR": num(mmr[f"hit@{k}"]), "MrrMMR": num(mmr["mrr"]), "PMMR": num(mmr[f"p@{k}"]),
        "DivMMR": num(mmr["fuentes_distintas_prom"]), "LatMMR": num(mmr["latencia_prom_s"]),
        "PctCitas": f"{round(100 * citas / n_preg)}\\,\\%",
        "LatGen": f"{lat_gen:.1f}".replace(".", "{,}"),
        "AnalisisRecuperacion": analisis_rec,
        "AnalisisGeneracion": analisis_gen,
        "TablaCorpus": "\n".join(filas),
    }
    salida = "% Generado por scripts/generar_metricas.py — no editar a mano\n"
    salida += "\n".join(f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in macros.items())
    # El ejemplo va en un entorno verbatim: se escribe como archivo aparte.
    (ROOT / "docs" / "informe" / "ejemplo.txt").write_text(ejemplo + "\n", encoding="utf-8")
    for destino in ("informe", "diapos"):
        (ROOT / "docs" / destino / "metricas.tex").write_text(salida + "\n", encoding="utf-8")
    print(salida)


if __name__ == "__main__":
    main()
