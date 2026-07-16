"""The MELT data model (Metrics, Events, Logs, Traces) across the 5 layers
of a full-stack observability platform: user_experience, application,
infrastructure, network, data_ai.

This is the vendor-neutral shape OpenTelemetry (OTel) standardizes on —
capture telemetry in this shape once, and it can be exported to any
backend that speaks OTLP (see exporters.py). That's the actual point of
this capstone: instrument once, avoid vendor lock-in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Layer(str, Enum):
    USER_EXPERIENCE = "user_experience"
    APPLICATION = "application"
    INFRASTRUCTURE = "infrastructure"
    NETWORK = "network"
    DATA_AI = "data_ai"


@dataclass
class Metric:
    name: str
    value: float
    timestamp: float
    layer: Layer
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class Event:
    name: str
    timestamp: float
    layer: Layer
    attributes: Dict[str, str] = field(default_factory=dict)


@dataclass
class LogRecord:
    message: str
    timestamp: float
    layer: Layer
    severity: str = "INFO"
    attributes: Dict[str, str] = field(default_factory=dict)


@dataclass
class Span:
    """One hop in a distributed trace. `parent_span_id=None` marks a root span."""

    trace_id: str
    span_id: str
    name: str
    service: str
    start_ts: float
    duration_ms: float
    layer: Layer
    parent_span_id: Optional[str] = None
    attributes: Dict[str, str] = field(default_factory=dict)


@dataclass
class TelemetryBatch:
    metrics: List[Metric] = field(default_factory=list)
    events: List[Event] = field(default_factory=list)
    logs: List[LogRecord] = field(default_factory=list)
    spans: List[Span] = field(default_factory=list)

    def extend(self, other: "TelemetryBatch") -> None:
        self.metrics.extend(other.metrics)
        self.events.extend(other.events)
        self.logs.extend(other.logs)
        self.spans.extend(other.spans)
