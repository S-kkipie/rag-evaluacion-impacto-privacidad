# RAG normativo para un Agente de Evaluación de Impacto de Privacidad (EIPD/PIA)

Avance del Trabajo de Investigación Formativa (TIF), curso de **Auditoría de Sistemas**, UNSA.
El TIF completo es un **agente de evaluación de impacto de privacidad**. En este avance se
entrega el componente de **Retrieval-Augmented Generation (RAG)**, que responde preguntas
normativas y metodológicas sobre la EIPD, siempre con citas a la fuente, el artículo y la página.

| Entregable | Ubicación |
|---|---|
| Código del RAG | `src/pia_rag/`, `app.py` |
| Evaluación | `eval/` (preguntas y resultados) |
| Informe (formato IEEE) | `docs/informe/informe.pdf` |
| Diapositivas | `docs/diapos/diapos.pdf` |
| **RSU**: diapositivas sobre la Ley 29733 y el D.S. 016-2024-JUS | `rsu/diapos_rsu.pdf` |
| **Agente de Terceros (DPAs)** del PIMS multiagente: Flask + FAISS + embeddings locales | `agente_terceros/` (ver su README) |

## Arquitectura

```
PDFs normativos ──► extracción + limpieza ──► fragmentación consciente de artículos
   (data/raw)          (pypdf)                 (1200 car., solape 200, metadatos:
                                                fuente, artículo, página, jurisdicción)
                                                         │
                                                         ▼
Pregunta ──► embedding de consulta ──► ChromaDB (coseno) ──► MMR (k=6 de 24)
                gemini-embedding-001 (768 d)                     │
                                                                 ▼
                           Respuesta con citas [n] ◄── gemini-2.5-flash + prompt
                                                        fundamentado (solo contexto)
```

## Corpus

| Sigla | Documento | Jurisdicción |
|---|---|---|
| LPDP | Ley N.º 29733, Ley de Protección de Datos Personales | Perú |
| RLPDP | D.S. N.º 016-2024-JUS, Reglamento de la Ley 29733 | Perú |
| RGPD | Reglamento (UE) 2016/679 | Unión Europea |
| WP248 | Directrices del GT29 sobre la EIPD (rev. 01) | Unión Europea |
| AEPD | Gestión del riesgo y evaluación de impacto en tratamientos de datos personales | España |
| NIST-PF | NIST Privacy Framework v1.0 | EE. UU. |

## Uso

```bash
uv sync                                   # instala las dependencias (Python 3.12)
cp .env.example .env                      # coloca tu GOOGLE_API_KEY
uv run pia-rag ingest                     # construye el índice en data/chroma
uv run pia-rag ask "¿Es obligatoria la EIPD en el Perú?"
uv run pia-rag ask "¿Qué es un dato sensible?" -j Perú
uv run pia-rag eval --generar             # métricas + respuestas en eval/resultados/
uv run streamlit run app.py               # interfaz web de demostración
uv run pytest                             # pruebas unitarias (no necesitan API)
./scripts/compilar_docs.sh                # métricas -> LaTeX -> informe.pdf y diapos.pdf
```

## Resultados (16 preguntas, k = 6)

| Estrategia | Hit@6 | MRR | P@6 | Fuentes distintas |
|---|---|---|---|---|
| Similitud | 1.000 | 1.000 | 0.729 | 1.94 |
| MMR (λ = 0.6) | 1.000 | 1.000 | 0.625 | 2.19 |

Las 16 respuestas generadas incluyen citas (latencia media: 8.1 s). El detalle está en `eval/resultados/`.
Estas métricas llegan al techo después de refinar la anotación: la primera iteración obtuvo Hit@6 = 0.938 y MRR = 0.818 (ver la sección de limitaciones del informe).


## Hoja de ruta (unidad 3: el agente completo)

1. Un cuestionario guiado que describa el tratamiento: datos, finalidad, volumen, tecnologías y transferencias.
2. Un tamizaje que decida si hace falta una EIPD, usando los criterios de WP248, el art. 35 del RGPD y el art. 40 del RLPDP.
3. La identificación y valoración de riesgos (probabilidad × impacto), con el RAG como herramienta.
4. La propuesta de medidas y un informe EIPD generado automáticamente, con trazabilidad normativa.
