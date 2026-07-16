"""CLI: python -m capstones.full_stack_observability <command>

Commands:
  simulate            Generate the incident telemetry and print summary counts
  topology             Print the service dependency graph derived from traces
  diagnose             Run the full pipeline: correlate + detect anomalies + rank root cause
  export --vendor X    Build (dry-run) or send an OTLP export to one of the 5 vendors
"""

from __future__ import annotations

import argparse
import json

from .anomaly import detect_anomalies
from .collector import Collector
from .correlation import rank_root_cause_candidates
from .exporters import VENDOR_CONFIGS, LocalJSONExporter, OTLPHTTPExporter
from .simulate import simulate
from .telemetry import Layer
from .topology import build_topology


def _build_collector(seed: int) -> Collector:
    collector = Collector()
    collector.ingest(simulate(seed=seed))
    return collector


def main() -> None:
    parser = argparse.ArgumentParser(prog="full-stack-observability")
    parser.add_argument("--seed", type=int, default=42)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("simulate", help="Generate telemetry and print summary counts")
    sub.add_parser("topology", help="Print the service dependency graph")
    sub.add_parser("diagnose", help="Run correlation + anomaly detection + root-cause ranking")

    export = sub.add_parser("export", help="Export telemetry (local JSON, or dry-run/live OTLP to a vendor)")
    export.add_argument("--vendor", choices=["local", *sorted(VENDOR_CONFIGS)], default="local")
    export.add_argument("--api-key", default="")
    export.add_argument("--send", action="store_true", help="Actually POST (default is dry-run/local-only)")
    export.add_argument("--path", default="telemetry_export.json")

    args = parser.parse_args()
    collector = _build_collector(args.seed)

    if args.command == "simulate":
        print(json.dumps({
            "metrics": len(collector.metrics()),
            "events": len(collector.events()),
            "logs": len(collector.logs()),
            "spans": len(collector.spans()),
            "trace_count": len(collector.trace_ids()),
        }, indent=2))

    elif args.command == "topology":
        graph = build_topology(collector.spans())
        print(json.dumps({service: sorted(downstream) for service, downstream in graph.items()}, indent=2))

    elif args.command == "diagnose":
        ranked = rank_root_cause_candidates(collector)
        anomalies = detect_anomalies(collector.metrics(layer=Layer.DATA_AI, name="inventory_db_query_ms"))
        print(json.dumps({
            "root_cause_candidates_ranked": [
                {"metric": name, "layer": layer.value, "correlation": round(corr, 3)}
                for name, layer, corr in ranked
            ],
            "anomalies_detected": len(anomalies),
            "first_anomaly_timestamp": anomalies[0].timestamp if anomalies else None,
        }, indent=2))

    elif args.command == "export":
        if args.vendor == "local":
            path = LocalJSONExporter(args.path).export(collector.batch())
            print(f"Wrote {path}")
        else:
            exporter = OTLPHTTPExporter(args.vendor, api_key=args.api_key, dry_run=not args.send)
            request = exporter.build_request(collector.batch())
            if args.send:
                status = exporter.export(collector.batch())
                print(f"Sent to {args.vendor}: HTTP {status}")
            else:
                print(f"DRY RUN — would POST to {args.vendor}:")
                print(json.dumps({"endpoint": request["endpoint"], "headers": request["headers"]}, indent=2))
                print(f"(payload omitted from output: {len(json.dumps(request['body']))} bytes)")


if __name__ == "__main__":
    main()
