"""Topology mapping: derive the service dependency graph purely from trace
spans' parent/child relationships — the "automatically discovers and
visualizes dependencies" capability described in the platform vendors'
marketing, implemented for real from data already being collected."""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from .telemetry import Span


def build_topology(spans: List[Span]) -> Dict[str, Set[str]]:
    """Returns {service_name: {downstream_service_names}} — a service calls
    another service if a child span's service differs from its parent
    span's service."""
    by_id = {s.span_id: s for s in spans}
    graph: Dict[str, Set[str]] = {}

    for span in spans:
        graph.setdefault(span.service, set())
        if span.parent_span_id and span.parent_span_id in by_id:
            parent = by_id[span.parent_span_id]
            if parent.service != span.service:
                graph.setdefault(parent.service, set()).add(span.service)

    return graph


def critical_path(spans: List[Span], trace_id: str) -> List[Tuple[str, float]]:
    """For one trace, returns [(service, duration_ms)] ordered by which
    span took the most time — the first entry is where most of the
    request's latency actually went."""
    trace_spans = [s for s in spans if s.trace_id == trace_id]
    ordered = sorted(trace_spans, key=lambda s: s.duration_ms, reverse=True)
    return [(s.service, s.duration_ms) for s in ordered]
