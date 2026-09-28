"""CLI: pia-rag ingest | ask | eval."""

import argparse
import sys


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="pia-rag", description="RAG normativo para EIPD/PIA")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ingest", help="Construye el índice vectorial desde data/raw")

    ask = sub.add_parser("ask", help="Consulta al RAG")
    ask.add_argument("pregunta")
    ask.add_argument("-j", "--jurisdiccion", choices=["Perú", "Unión Europea", "España", "EE. UU."])

    ev = sub.add_parser("eval", help="Evalúa recuperación (y opcionalmente respuestas)")
    ev.add_argument("--generar", action="store_true", help="También genera respuestas con el LLM")

    args = p.parse_args(argv)

    if args.cmd == "ingest":
        from .config import get_config
        from .ingest import indexar

        n = indexar(get_config())
        print(f"Índice listo: {n} fragmentos")
    elif args.cmd == "ask":
        from .rag import consultar, etiqueta

        r = consultar(args.pregunta, jurisdiccion=args.jurisdiccion)
        print(r.respuesta)
        print("\nFuentes:")
        for i, d in enumerate(r.fuentes, 1):
            print(f"  [{i}] {etiqueta(d)} — {d.metadata['titulo']}")
    elif args.cmd == "eval":
        from .evaluacion import evaluar

        evaluar(generar=args.generar)


if __name__ == "__main__":
    main(sys.argv[1:])
