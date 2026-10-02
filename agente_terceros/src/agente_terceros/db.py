"""Repositorio SQLite: proveedores, DPAs, subencargados, aprobaciones (HITL) y auditoría.

El esquema usa tipos portables para migrarlo a PostgreSQL sin cambios de fondo
(TEXT para JSON -> JSONB, INTEGER PRIMARY KEY -> SERIAL/UUID).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS proveedores (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    ruc TEXT,
    pais TEXT,
    servicio TEXT,
    contacto TEXT,
    categorias_datos TEXT NOT NULL DEFAULT '[]',
    sistemas TEXT NOT NULL DEFAULT '[]',
    datos_sensibles INTEGER NOT NULL DEFAULT 0,
    volumen TEXT NOT NULL DEFAULT 'bajo',
    transferencia_internacional INTEGER NOT NULL DEFAULT 0,
    pais_adecuado INTEGER NOT NULL DEFAULT 1,
    certificaciones TEXT NOT NULL DEFAULT '[]',
    incidentes_12m INTEGER NOT NULL DEFAULT 0,
    creado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dpas (
    id INTEGER PRIMARY KEY,
    proveedor_id INTEGER NOT NULL REFERENCES proveedores(id),
    archivo TEXT,
    fecha_firma TEXT,
    fecha_vencimiento TEXT,
    estado TEXT NOT NULL,  -- pendiente_aprobacion | vigente | rechazado
    cumplimiento REAL,
    revision TEXT NOT NULL DEFAULT '{}',
    creado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS subencargados (
    id INTEGER PRIMARY KEY,
    proveedor_id INTEGER NOT NULL REFERENCES proveedores(id),
    nombre TEXT NOT NULL,
    pais TEXT,
    servicio TEXT,
    estado TEXT NOT NULL,  -- pendiente | aprobado | rechazado
    creado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS aprobaciones (
    id INTEGER PRIMARY KEY,
    tipo TEXT NOT NULL,  -- dpa | subencargado
    ref_id INTEGER NOT NULL,
    proveedor_id INTEGER NOT NULL,
    descripcion TEXT,
    estado TEXT NOT NULL DEFAULT 'pendiente',
    solicitado TEXT NOT NULL,
    resuelto TEXT,
    revisor TEXT,
    comentario TEXT
);
CREATE TABLE IF NOT EXISTS auditoria (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    accion TEXT NOT NULL,
    detalle TEXT
);
"""

LISTAS = ("categorias_datos", "sistemas", "certificaciones")
BOOLEANOS = ("datos_sensibles", "transferencia_internacional", "pais_adecuado")
CAMPOS_PROVEEDOR = (
    "nombre", "ruc", "pais", "servicio", "contacto", *LISTAS, *BOOLEANOS, "volumen", "incidentes_12m",
)


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Repositorio:
    def __init__(self, ruta: Path):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(ruta, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(ESQUEMA)

    # -- utilidades ---------------------------------------------------------
    def _log(self, actor: str, accion: str, detalle: str) -> None:
        self.con.execute(
            "INSERT INTO auditoria (ts, actor, accion, detalle) VALUES (?, ?, ?, ?)",
            (_ahora(), actor, accion, detalle),
        )

    @staticmethod
    def _proveedor(fila: sqlite3.Row) -> dict:
        p = dict(fila)
        for c in LISTAS:
            p[c] = json.loads(p[c])
        for c in BOOLEANOS:
            p[c] = bool(p[c])
        return p

    @staticmethod
    def _dpa(fila: sqlite3.Row | None) -> dict | None:
        if fila is None:
            return None
        d = dict(fila)
        d["revision"] = json.loads(d["revision"])
        return d

    # -- proveedores --------------------------------------------------------
    def crear_proveedor(self, datos: dict, actor: str = "agente_terceros") -> int:
        valores = {c: datos.get(c) for c in CAMPOS_PROVEEDOR if c in datos}
        for c in LISTAS:
            valores[c] = json.dumps(list(datos.get(c, [])), ensure_ascii=False)
        for c in BOOLEANOS:
            if c in valores:
                valores[c] = int(bool(valores[c]))
        valores["creado"] = _ahora()
        cols = ", ".join(valores)
        cur = self.con.execute(
            f"INSERT INTO proveedores ({cols}) VALUES ({', '.join('?' * len(valores))})",
            tuple(valores.values()),
        )
        self._log(actor, "proveedor_creado", datos["nombre"])
        self.con.commit()
        return cur.lastrowid

    def proveedor(self, pid: int) -> dict | None:
        fila = self.con.execute("SELECT * FROM proveedores WHERE id = ?", (pid,)).fetchone()
        return self._proveedor(fila) if fila else None

    def proveedores(self) -> list[dict]:
        filas = self.con.execute("SELECT * FROM proveedores ORDER BY nombre").fetchall()
        return [self._proveedor(f) for f in filas]

    def encargados_implicados(self, termino: str) -> list[dict]:
        """Proveedores que tratan una categoría de datos o un sistema (flujo de brecha)."""
        t = termino.strip().lower()
        return [
            p for p in self.proveedores()
            if any(t in x.lower() for x in p["categorias_datos"] + p["sistemas"])
        ]

    # -- DPAs ---------------------------------------------------------------
    def registrar_dpa(
        self, pid: int, archivo: str, fecha_firma: str, fecha_vencimiento: str,
        cumplimiento: float | None, revision: dict, actor: str = "agente_terceros",
    ) -> int:
        cur = self.con.execute(
            "INSERT INTO dpas (proveedor_id, archivo, fecha_firma, fecha_vencimiento, estado,"
            " cumplimiento, revision, creado) VALUES (?, ?, ?, ?, 'pendiente_aprobacion', ?, ?, ?)",
            (pid, archivo, fecha_firma, fecha_vencimiento, cumplimiento,
             json.dumps(revision, ensure_ascii=False), _ahora()),
        )
        did = cur.lastrowid
        nombre = self.proveedor(pid)["nombre"]
        self._solicitar("dpa", did, pid, f"Nuevo DPA de {nombre} ({archivo})")
        pct = "sin revisión" if cumplimiento is None else f"{cumplimiento:.1f}%"
        self._log(actor, "dpa_registrado", f"{nombre}: {archivo}, cumplimiento {pct}")
        self.con.commit()
        return did

    def dpa(self, did: int) -> dict | None:
        return self._dpa(self.con.execute("SELECT * FROM dpas WHERE id = ?", (did,)).fetchone())

    def dpas(self, pid: int) -> list[dict]:
        filas = self.con.execute(
            "SELECT * FROM dpas WHERE proveedor_id = ? ORDER BY id DESC", (pid,)
        ).fetchall()
        return [self._dpa(f) for f in filas]

    def dpa_vigente(self, pid: int) -> dict | None:
        return self._dpa(self.con.execute(
            "SELECT * FROM dpas WHERE proveedor_id = ? AND estado = 'vigente' ORDER BY id DESC",
            (pid,),
        ).fetchone())

    def alertas_vencimiento(self, hoy: date, dias: int) -> list[dict]:
        filas = self.con.execute(
            "SELECT d.id, d.fecha_vencimiento, p.nombre AS proveedor, p.id AS proveedor_id"
            " FROM dpas d JOIN proveedores p ON p.id = d.proveedor_id WHERE d.estado = 'vigente'"
        ).fetchall()
        alertas = []
        for f in filas:
            restantes = (date.fromisoformat(f["fecha_vencimiento"]) - hoy).days
            if restantes <= dias:
                tipo = "vencido" if restantes < 0 else "por_vencer"
                alertas.append({**dict(f), "dias_restantes": restantes, "tipo": tipo})
        return sorted(alertas, key=lambda a: a["dias_restantes"])

    # -- subencargados ------------------------------------------------------
    def agregar_subencargado(
        self, pid: int, nombre: str, pais: str, servicio: str, actor: str = "agente_terceros"
    ) -> int:
        cur = self.con.execute(
            "INSERT INTO subencargados (proveedor_id, nombre, pais, servicio, estado, creado)"
            " VALUES (?, ?, ?, ?, 'pendiente', ?)",
            (pid, nombre, pais, servicio, _ahora()),
        )
        sid = cur.lastrowid
        prov = self.proveedor(pid)["nombre"]
        self._solicitar("subencargado", sid, pid, f"{prov} propone subencargado {nombre} ({pais})")
        self._log(actor, "subencargado_propuesto", f"{prov} -> {nombre} ({pais})")
        self.con.commit()
        return sid

    def subencargados(self, pid: int) -> list[dict]:
        filas = self.con.execute(
            "SELECT * FROM subencargados WHERE proveedor_id = ? ORDER BY id", (pid,)
        ).fetchall()
        return [dict(f) for f in filas]

    # -- aprobaciones (human-in-the-loop) ------------------------------------
    def _solicitar(self, tipo: str, ref_id: int, pid: int, descripcion: str) -> None:
        self.con.execute(
            "INSERT INTO aprobaciones (tipo, ref_id, proveedor_id, descripcion, solicitado)"
            " VALUES (?, ?, ?, ?, ?)",
            (tipo, ref_id, pid, descripcion, _ahora()),
        )

    def pendientes(self) -> list[dict]:
        filas = self.con.execute(
            "SELECT * FROM aprobaciones WHERE estado = 'pendiente' ORDER BY id"
        ).fetchall()
        return [dict(f) for f in filas]

    def resolver_aprobacion(self, aid: int, aprobado: bool, revisor: str, comentario: str) -> None:
        fila = self.con.execute("SELECT * FROM aprobaciones WHERE id = ?", (aid,)).fetchone()
        if fila is None or fila["estado"] != "pendiente":
            raise ValueError(f"La aprobación {aid} no existe o ya fue resuelta")
        estado = "aprobado" if aprobado else "rechazado"
        self.con.execute(
            "UPDATE aprobaciones SET estado = ?, resuelto = ?, revisor = ?, comentario = ?"
            " WHERE id = ?",
            (estado, _ahora(), revisor, comentario, aid),
        )
        if fila["tipo"] == "dpa":
            self.con.execute(
                "UPDATE dpas SET estado = ? WHERE id = ?",
                ("vigente" if aprobado else "rechazado", fila["ref_id"]),
            )
        else:
            self.con.execute(
                "UPDATE subencargados SET estado = ? WHERE id = ?", (estado, fila["ref_id"])
            )
        self._log(revisor, f"aprobacion_{'aprobada' if aprobado else 'rechazada'}",
                  f"{fila['descripcion']}. {comentario}".strip())
        self.con.commit()

    def historial(self, limite: int = 100) -> list[dict]:
        filas = self.con.execute(
            "SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (limite,)
        ).fetchall()
        return [dict(f) for f in filas]
