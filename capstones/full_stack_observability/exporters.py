"""OTLP export: capture telemetry once, ship it to any vendor that speaks
OTLP. All 5 platforms named in the source brief — Datadog, Dynatrace, New
Relic, Splunk, Grafana Cloud — ingest OTLP. That's the actual point of
standardizing on OpenTelemetry: instrument once, swap backends by changing
an endpoint and a header, not by re-instrumenting the whole stack.

Endpoints/headers below are illustrative of the pattern each vendor
documents at the time of writing — verify against the vendor's current
OTLP ingestion docs before pointing real traffic at them; ingestion URLs
and auth header names do change.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from .telemetry import TelemetryBatch


def batch_to_otlp_json(batch: TelemetryBatch) -> dict:
    """A simplified OTLP-JSON-shaped envelope. A production exporter would
    use the `opentelemetry-sdk` plus a vendor/OTLP exporter package for
    exact wire-format compliance (protobuf, resource/scope nesting); this
    captures the same underlying data model for teaching, and is exactly
    what the local/dry-run paths need."""
    return {
        "resourceMetrics": [
            {"name": m.name, "value": m.value, "timestamp": m.timestamp, "layer": m.layer.value, "tags": m.tags}
            for m in batch.metrics
        ],
        "resourceEvents": [
            {"name": e.name, "timestamp": e.timestamp, "layer": e.layer.value, "attributes": e.attributes}
            for e in batch.events
        ],
        "resourceLogs": [
            {"message": l.message, "timestamp": l.timestamp, "layer": l.layer.value, "severity": l.severity}
            for l in batch.logs
        ],
        "resourceSpans": [
            {
                "trace_id": s.trace_id,
                "span_id": s.span_id,
                "name": s.name,
                "service": s.service,
                "start_ts": s.start_ts,
                "duration_ms": s.duration_ms,
                "layer": s.layer.value,
                "parent_span_id": s.parent_span_id,
            }
            for s in batch.spans
        ],
    }


class LocalJSONExporter:
    """Default, offline exporter — writes the OTLP-shaped payload to a
    file. Stands in for "a full-stack observability platform" without
    requiring any vendor account, and is what tests and the default CLI
    path use."""

    def __init__(self, path: str = "telemetry_export.json"):
        self.path = Path(path)

    def export(self, batch: TelemetryBatch) -> Path:
        self.path.write_text(json.dumps(batch_to_otlp_json(batch), indent=2), encoding="utf-8")
        return self.path


@dataclass
class VendorConfig:
    vendor: str
    endpoint_template: str  # may contain {placeholders} filled from endpoint_kwargs
    header_name: str
    header_value_template: str  # e.g. "Api-Token {api_key}"
    notes: str
    default_endpoint_kwargs: Dict[str, str] = field(default_factory=dict)


VENDOR_CONFIGS: Dict[str, VendorConfig] = {
    "datadog": VendorConfig(
        vendor="datadog",
        endpoint_template="https://otlp.{site}/v1/traces",
        header_name="DD-API-KEY",
        header_value_template="{api_key}",
        notes=(
            "site defaults to datadoghq.com (US1); use datadoghq.eu for the EU region. "
            "Agent-based OTLP ingest on localhost:4318 is the more common production path "
            "than sending directly to Datadog's intake."
        ),
        default_endpoint_kwargs={"site": "datadoghq.com"},
    ),
    "dynatrace": VendorConfig(
        vendor="dynatrace",
        endpoint_template="https://{environment_id}.live.dynatrace.com/api/v2/otlp/v1/traces",
        header_name="Authorization",
        header_value_template="Api-Token {api_key}",
        notes="environment_id is the tenant identifier from the Dynatrace environment URL — no safe default, must be supplied.",
    ),
    "new_relic": VendorConfig(
        vendor="new_relic",
        endpoint_template="https://otlp.nr-data.net:4318/v1/traces",
        header_name="api-key",
        header_value_template="{api_key}",
        notes="Use otlp.eu01.nr-data.net for the EU region. api_key is a New Relic ingest license key.",
    ),
    "splunk": VendorConfig(
        vendor="splunk",
        endpoint_template="https://ingest.{realm}.signalfx.com/v2/trace/otlp",
        header_name="X-SF-Token",
        header_value_template="{api_key}",
        notes=(
            "Splunk Observability Cloud, built on the former SignalFx ingest path. "
            "realm is the org's assigned SignalFx realm (e.g. us1)."
        ),
        default_endpoint_kwargs={"realm": "us1"},
    ),
    "grafana_cloud": VendorConfig(
        vendor="grafana_cloud",
        endpoint_template="https://otlp-gateway-{region}.grafana.net/otlp",
        header_name="Authorization",
        header_value_template="Basic {api_key}",
        notes=(
            "api_key is base64(instance_id:api_token). Grafana Cloud fans the same OTLP "
            "payload out to Prometheus (metrics), Loki (logs), and Tempo (traces) behind one gateway."
        ),
        default_endpoint_kwargs={"region": "prod-us-east-0"},
    ),
}


class OTLPHTTPExporter:
    """Generic OTLP-over-HTTP exporter — the same class works for any of
    the 5 vendors above, because they all speak OTLP. `dry_run=True` (the
    default) builds the request and returns it without sending anything,
    so this stays offline-safe in tests and casual use; set
    `dry_run=False` with a real api_key to actually POST."""

    def __init__(self, vendor: str, api_key: str = "", dry_run: bool = True, **endpoint_kwargs: str):
        if vendor not in VENDOR_CONFIGS:
            raise ValueError(f"Unknown vendor: {vendor!r}. Known: {sorted(VENDOR_CONFIGS)}")
        self.config = VENDOR_CONFIGS[vendor]
        self.api_key = api_key
        self.dry_run = dry_run
        self.endpoint_kwargs = endpoint_kwargs

    def build_request(self, batch: TelemetryBatch) -> Dict[str, object]:
        kwargs = {**self.config.default_endpoint_kwargs, **self.endpoint_kwargs}
        try:
            endpoint = self.config.endpoint_template.format(**kwargs)
        except KeyError as exc:
            raise ValueError(
                f"{self.config.vendor} endpoint template needs {exc}; pass it as a keyword arg, "
                f"e.g. OTLPHTTPExporter({self.config.vendor!r}, api_key=..., "
                f"{str(exc).strip(chr(39))}='...')"
            ) from exc
        headers = {
            self.config.header_name: self.config.header_value_template.format(api_key=self.api_key),
            "Content-Type": "application/json",
        }
        return {"endpoint": endpoint, "headers": headers, "body": batch_to_otlp_json(batch)}

    def export(self, batch: TelemetryBatch) -> Optional[int]:
        request = self.build_request(batch)
        if self.dry_run:
            return None  # nothing sent — call build_request() to see what would be
        payload = json.dumps(request["body"]).encode("utf-8")
        req = urllib.request.Request(
            request["endpoint"], data=payload, headers=request["headers"], method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status
