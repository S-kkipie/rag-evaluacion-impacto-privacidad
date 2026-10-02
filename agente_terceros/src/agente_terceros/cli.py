"""CLI: agente-terceros ingest | demo | web | mcp."""

import argparse
import sys


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="agente-terceros", description="Agente de Terceros (DPAs) — PIMS ISO/IEC 27701")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest", help="Construye el índice FAISS desde data/raw (Ollama nomic-embed-text)")
    sub.add_parser("demo", help="Carga el escenario de demostración (revisa 2 DPAs con Gemini)")
    web = sub.add_parser("web", help="Levanta la interfaz web Flask")
    web.add_argument("--port", type=int, default=5000)
    sub.add_parser("mcp", help="Servidor MCP por stdio (list_processors, check_dpa_status, evaluate_vendor)")
    args = p.parse_args(argv)

    if args.cmd == "ingest":
        from .config import get_config
        from .vectores import construir_indice, embedder_ollama

        cfg = get_config()
        idx = construir_indice(cfg, embedder_ollama(cfg))
        print(f"Índice listo: {len(idx)} fragmentos en {cfg.index_dir}")
        return

    from .app import crear_agente_real

    agente = crear_agente_real()
    if args.cmd == "demo":
        from .demo import sembrar_demo

        print("Escenario cargado." if sembrar_demo(agente) else "La base ya tiene datos; no se cargó nada.")
    elif args.cmd == "web":
        from .app import create_app

        create_app(agente).run(port=args.port, debug=False)
    elif args.cmd == "mcp":
        from .mcp_server import crear_servidor

        crear_servidor(agente).run("stdio")


if __name__ == "__main__":
    main(sys.argv[1:])
