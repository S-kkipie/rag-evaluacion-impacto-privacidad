#!/usr/bin/env bash
# Regenera las métricas desde eval/resultados y compila informe + diapositivas.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run python scripts/generar_metricas.py > /dev/null
cd docs/informe
pdflatex -interaction=nonstopmode -halt-on-error informe.tex > /dev/null
bibtex informe > /dev/null
pdflatex -interaction=nonstopmode -halt-on-error informe.tex > /dev/null
pdflatex -interaction=nonstopmode -halt-on-error informe.tex > /dev/null
cd ../diapos
pdflatex -interaction=nonstopmode -halt-on-error diapos.tex > /dev/null
pdflatex -interaction=nonstopmode -halt-on-error diapos.tex > /dev/null
echo "OK: docs/informe/informe.pdf, docs/diapos/diapos.pdf"
