"""CLI: python -m capstones.incident_debugging run --seed N [--reveal]"""

from __future__ import annotations

import argparse

from .faults import inject
from .logs import dump_trace


def main() -> None:
    parser = argparse.ArgumentParser(prog="incident-debugging")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Generate an incident trace for a seeded fault")
    run.add_argument("--seed", type=int, required=True)
    run.add_argument("--reveal", action="store_true", help="Print which fault is active (spoils the drill)")

    args = parser.parse_args()

    if args.command == "run":
        fault = inject(args.seed)
        if args.reveal:
            print(f"# active fault: {fault}\n")
        print(dump_trace(fault))


if __name__ == "__main__":
    main()
