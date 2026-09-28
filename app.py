"""Interfaz de demostración: streamlit run app.py"""

import streamlit as st

from pia_rag.config import CORPUS
from pia_rag.rag import consultar, etiqueta

st.set_page_config(page_title="RAG · Evaluación de Impacto de Privacidad", page_icon="🔒", layout="wide")
st.title("🔒 RAG normativo para Evaluación de Impacto de Privacidad")
st.caption("Avance TIF · Auditoría de Sistemas · UNSA — módulo de recuperación del agente EIPD/PIA")

with st.sidebar:
    st.header("Corpus")
    for f in CORPUS:
        st.markdown(f"**{f.sigla}** · {f.jurisdiccion}  \n{f.titulo}")
    jur = st.selectbox("Filtrar jurisdicción", ["Todas", "Perú", "Unión Europea", "España", "EE. UU."])

EJEMPLOS = [
    "¿Es obligatoria la evaluación de impacto de protección de datos personales en el Perú?",
    "¿Qué contenido mínimo debe incluir una evaluación de impacto de protección de datos?",
    "¿Qué criterios indican que un tratamiento entraña un alto riesgo?",
]
ejemplo = st.selectbox("Preguntas de ejemplo", ["—"] + EJEMPLOS)
pregunta = st.text_area("Pregunta", value="" if ejemplo == "—" else ejemplo, height=90)

if st.button("Consultar", type="primary", disabled=not pregunta.strip()):
    with st.spinner("Recuperando fragmentos y generando respuesta..."):
        r = consultar(pregunta, jurisdiccion=None if jur == "Todas" else jur)
    st.subheader("Respuesta")
    st.markdown(r.respuesta)
    st.subheader("Fragmentos recuperados")
    for i, d in enumerate(r.fuentes, 1):
        with st.expander(f"[{i}] {etiqueta(d)} — {d.metadata['titulo']}"):
            st.text(d.page_content)
