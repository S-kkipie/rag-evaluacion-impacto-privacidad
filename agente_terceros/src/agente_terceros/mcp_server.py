"""Servidor MCP del Agente de Terceros (bus MCP del PIMS multiagente).

Expone list_processors, check_dpa_status y evaluate_vendor para que el
orquestador u otros agentes (p. ej. el de Incidentes) los invoquen por JSON-RPC.
Uso: uv run agente-terceros mcp   (transporte stdio)
"""

from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from .agente import Agente


def crear_servidor(agente: Agente) -> MCPServer:
    mcp = MCPServer("pims-terceros")

    @mcp.tool()
    def list_processors() -> str:
        """Lista los encargados/terceros con el estado de su DPA y su nivel de riesgo."""
        return json.dumps(agente.list_processors(), ensure_ascii=False)

    @mcp.tool()
    def check_dpa_status(proveedor_id: int) -> str:
        """Estado del DPA de un proveedor: vigente, por_vencer, vencido, pendiente_aprobacion o sin_dpa."""
        return json.dumps(agente.check_dpa_status(proveedor_id), ensure_ascii=False)

    @mcp.tool()
    def evaluate_vendor(proveedor_id: int) -> str:
        """Evaluación de riesgo (probabilidad × impacto) de un proveedor, con factores y recomendaciones."""
        return json.dumps(agente.evaluate_vendor(proveedor_id), ensure_ascii=False)

    @mcp.tool()
    def processors_in_breach(termino: str) -> str:
        """Encargados que tratan una categoría de datos o sistema afectado por una brecha."""
        return json.dumps(agente.encargados_implicados(termino), ensure_ascii=False)

    return mcp
