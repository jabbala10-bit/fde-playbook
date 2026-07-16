"""CLI: python -m capstones.governance_assessment assess <profile.json> [--format json|markdown]"""

from __future__ import annotations

import argparse
import json

from .assess import assess_system, load_payload, to_markdown


def main() -> None:
    parser = argparse.ArgumentParser(prog="governance-assessment")
    sub = parser.add_subparsers(dest="command", required=True)

    assess = sub.add_parser("assess", help="Run a combined EU AI Act + GDPR assessment")
    assess.add_argument("profile", help="Path to a system profile JSON file")
    assess.add_argument("--format", choices=["json", "markdown"], default="json")

    args = parser.parse_args()

    if args.command == "assess":
        payload = load_payload(args.profile)
        result = assess_system(payload)
        printable = {k: v for k, v in result.items() if not k.startswith("_")}
        if args.format == "markdown":
            print(to_markdown(result))
        else:
            print(json.dumps(printable, indent=2))


if __name__ == "__main__":
    main()
