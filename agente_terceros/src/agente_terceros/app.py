"""Servidor Flask: API REST del Agente de Terceros + interfaz web (HTML/CSS/JS puro)."""

from __future__ import annotations

import io
from dataclasses import asdict
from datetime import date
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory
from pypdf import PdfReader

from .agente import Agente
from .checklist import CLAUSULAS, CONTROLES
from .ingest import limpiar
from .riesgo import VOLUMEN_IMPACTO

STATIC = Path(__file__).parent / "static"


def _error(mensaje: str, codigo: int = 400):
    return jsonify({"error": mensaje}), codigo


def extraer_texto(nombre: str, contenido: bytes) -> str:
    if nombre.lower().endswith(".pdf"):
        paginas = PdfReader(io.BytesIO(contenido)).pages
        return limpiar("\n\n".join(p.extract_text() or "" for p in paginas))
    return limpiar(contenido.decode("utf-8", errors="ignore"))


def _fecha_valida(valor: str | None) -> bool:
    try:
        date.fromisoformat(valor or "")
        return True
    except ValueError:
        return False


def create_app(agente: Agente) -> Flask:
    app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
    repo = agente.repo

    def _proveedor_o_404(pid: int) -> dict:
        p = repo.proveedor(pid)
        if p is None:
            abort(404)
        return p

    @app.errorhandler(404)
    def _no_encontrado(_):
        return _error("No encontrado", 404)

    @app.get("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    # -- panel y catálogo ----------------------------------------------------
    @app.get("/api/panel")
    def panel():
        return jsonify(agente.panel())

    @app.get("/api/checklist")
    def checklist():
        return jsonify({
            "clausulas": [asdict(c) for c in CLAUSULAS],
            "controles": [asdict(c) for c in CONTROLES],
        })

    # -- proveedores ---------------------------------------------------------
    @app.get("/api/proveedores")
    def proveedores():
        return jsonify(agente.list_processors())

    @app.post("/api/proveedores")
    def crear_proveedor():
        datos = request.get_json(silent=True) or {}
        if not str(datos.get("nombre", "")).strip():
            return _error("El nombre del proveedor es obligatorio")
        if datos.get("volumen", "bajo") not in VOLUMEN_IMPACTO:
            return _error("volumen debe ser bajo, medio o alto")
        datos["nombre"] = datos["nombre"].strip()
        datos["incidentes_12m"] = int(datos.get("incidentes_12m") or 0)
        pid = repo.crear_proveedor(datos, actor=datos.pop("actor", "usuario"))
        return jsonify({"id": pid}), 201

    @app.get("/api/proveedores/<int:pid>")
    def proveedor(pid: int):
        p = _proveedor_o_404(pid)
        return jsonify({
            **p,
            "dpa": agente.check_dpa_status(pid),
            "riesgo": agente.evaluate_vendor(pid),
            "dpas": repo.dpas(pid),
            "subencargados": repo.subencargados(pid),
        })

    @app.post("/api/proveedores/<int:pid>/subencargados")
    def agregar_subencargado(pid: int):
        _proveedor_o_404(pid)
        d = request.get_json(silent=True) or {}
        if not str(d.get("nombre", "")).strip():
            return _error("El nombre del subencargado es obligatorio")
        sid = repo.agregar_subencargado(pid, d["nombre"].strip(), d.get("pais", ""), d.get("servicio", ""))
        return jsonify({"id": sid, "estado": "pendiente"}), 201

    @app.post("/api/proveedores/<int:pid>/dpa")
    def subir_dpa(pid: int):
        _proveedor_o_404(pid)
        archivo = request.files.get("archivo")
        firma, vence = request.form.get("fecha_firma"), request.form.get("fecha_vencimiento")
        if archivo is None or not archivo.filename:
            return _error("Adjunta el contrato (PDF o TXT)")
        if not (_fecha_valida(firma) and _fecha_valida(vence)):
            return _error("Indica fecha de firma y de vencimiento (AAAA-MM-DD)")
        texto = extraer_texto(archivo.filename, archivo.read())
        if not texto:
            return _error("No se pudo extraer texto del archivo (¿PDF escaneado?)")
        try:
            res = agente.revisar_y_registrar(pid, texto, archivo.filename, firma, vence)
        except ValueError as e:
            return _error(str(e))
        return jsonify(res), 201

    # -- aprobaciones (HITL) -------------------------------------------------
    @app.get("/api/aprobaciones")
    def aprobaciones():
        return jsonify(repo.pendientes())

    @app.post("/api/aprobaciones/<int:aid>")
    def resolver(aid: int):
        d = request.get_json(silent=True) or {}
        revisor = str(d.get("revisor", "")).strip()
        if not revisor:
            return _error("Indica quién aprueba (revisor)")
        try:
            repo.resolver_aprobacion(aid, bool(d.get("aprobado")), revisor, d.get("comentario", ""))
        except ValueError as e:
            return _error(str(e), 409)
        return jsonify({"ok": True})

    @app.get("/api/historial")
    def historial():
        return jsonify(repo.historial(200))

    # -- consulta normativa y brecha ------------------------------------------
    @app.post("/api/consulta")
    def consulta():
        d = request.get_json(silent=True) or {}
        pregunta = str(d.get("pregunta", "")).strip()
        if not pregunta:
            return _error("Escribe una pregunta")
        return jsonify(agente.consultar(pregunta, d.get("jurisdiccion") or None))

    @app.get("/api/brecha")
    def brecha():
        termino = request.args.get("termino", "").strip()
        if not termino:
            return _error("Indica una categoría de datos o sistema afectado")
        return jsonify(agente.encargados_implicados(termino))

    # -- herramientas del bus MCP, también por HTTP -----------------------------
    @app.get("/api/tools/list_processors")
    def tool_list():
        return jsonify(agente.list_processors())

    @app.get("/api/tools/check_dpa_status/<int:pid>")
    def tool_check(pid: int):
        _proveedor_o_404(pid)
        return jsonify(agente.check_dpa_status(pid))

    @app.get("/api/tools/evaluate_vendor/<int:pid>")
    def tool_eval(pid: int):
        _proveedor_o_404(pid)
        return jsonify(agente.evaluate_vendor(pid))

    return app


def crear_agente_real() -> Agente:
    """Agente con índice FAISS persistido, embeddings Ollama y Gemini."""
    from .config import get_config
    from .db import Repositorio
    from .revisor import llm_gemini
    from .vectores import IndiceVectorial, construir_indice, embedder_ollama

    cfg = get_config()
    embed = embedder_ollama(cfg)
    if (cfg.index_dir / "normativa.faiss").exists():
        normativa = IndiceVectorial.cargar(cfg.index_dir, embed)
    else:
        normativa = construir_indice(cfg, embed)
    return Agente(
        Repositorio(cfg.db_path), normativa, embed,
        llm=llm_gemini(cfg), llm_texto=llm_gemini(cfg, json_salida=False), cfg=cfg,
    )
