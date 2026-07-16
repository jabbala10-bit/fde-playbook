"""In-memory telemetry collector — the local, offline stand-in for a
platform like Datadog/Dynatrace/New Relic/Splunk/Grafana Cloud. Stores
MELT data queryable by layer, which is what topology.py, correlation.py,
and anomaly.py all read from.
"""

from __future__ import annotations

from typing import List

from .telemetry import Event, Layer, LogRecord, Metric, Span, TelemetryBatch


class Collector:
    def __init__(self) -> None:
        self._batch = TelemetryBatch()

    def ingest(self, batch: TelemetryBatch) -> None:
        self._batch.extend(batch)

    def batch(self) -> TelemetryBatch:
        return self._batch

    def metrics(self, layer: Layer | None = None, name: str | None = None) -> List[Metric]:
        return [
            m
            for m in self._batch.metrics
            if (layer is None or m.layer == layer) and (name is None or m.name == name)
        ]

    def events(self, layer: Layer | None = None, name: str | None = None) -> List[Event]:
        return [
            e
            for e in self._batch.events
            if (layer is None or e.layer == layer) and (name is None or e.name == name)
        ]

    def logs(self, layer: Layer | None = None, severity: str | None = None) -> List[LogRecord]:
        return [
            l
            for l in self._batch.logs
            if (layer is None or l.layer == layer) and (severity is None or l.severity == severity)
        ]

    def spans(self, trace_id: str | None = None) -> List[Span]:
        return [s for s in self._batch.spans if trace_id is None or s.trace_id == trace_id]

    def trace_ids(self) -> List[str]:
        seen: List[str] = []
        for s in self._batch.spans:
            if s.trace_id not in seen:
                seen.append(s.trace_id)
        return seen
