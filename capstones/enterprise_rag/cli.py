"""CLI: python -m capstones.enterprise_rag ingest|ask|eval [--provider local|live]"""

from __future__ import annotations

import argparse
import json

from .eval import answer_question, build_index, run_eval


def main() -> None:
    parser = argparse.ArgumentParser(prog="enterprise-rag")
    parser.add_argument("--provider", choices=["local", "live"], default="local")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ingest", help="Build the index and report chunk counts")

    ask = sub.add_parser("ask", help="Ask a question against a matter")
    ask.add_argument("question")
    ask.add_argument("--matter", required=True)
    ask.add_argument("--k", type=int, default=5)

    sub.add_parser("eval", help="Run the golden-set evaluation")

    args = parser.parse_args()

    if args.command == "ingest":
        store, _, _ = build_index(args.provider)
        print(f"Indexed {len(store)} chunks.")
    elif args.command == "ask":
        store, embedder, generator = build_index(args.provider)
        result = answer_question(args.question, args.matter, store, embedder, generator, k=args.k)
        print(json.dumps(result, indent=2))
    elif args.command == "eval":
        report = run_eval(args.provider)
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
