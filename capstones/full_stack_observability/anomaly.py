"""Statistical baselining + anomaly detection — the "AI-Driven Alerting"
capability described in the platform vendor brief (calculate baseline
behavior, flag true deviations instead of rigid thresholds), implemented
honestly as a rolling z-score model rather than left as a black box."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import List

from .telemetry import Layer, Metric


@dataclass
class Anomaly:
    metric_name: str
    layer: Layer
    timestamp: float
    value: float
    baseline_mean: float
    baseline_stdev: float
    z_score: float


def detect_anomalies(
    metrics: List[Metric], baseline_window: int = 10, z_threshold: float = 3.0
) -> List[Anomaly]:
    """Rolling baseline: for each point, compute mean/stdev over the
    preceding `baseline_window` points — not the whole series, so an
    incident partway through isn't diluted into its own baseline — and
    flag anything beyond z_threshold standard deviations from it."""
    ordered = sorted(metrics, key=lambda m: m.timestamp)
    anomalies: List[Anomaly] = []

    for i, point in enumerate(ordered):
        window = ordered[max(0, i - baseline_window) : i]
        if len(window) < baseline_window:
            continue  # not enough history yet to baseline against
        values = [w.value for w in window]
        mean = statistics.mean(values)
        stdev = statistics.pstdev(values) or 1e-9
        z = (point.value - mean) / stdev
        if abs(z) >= z_threshold:
            anomalies.append(
                Anomaly(point.name, point.layer, point.timestamp, point.value, mean, stdev, z)
            )

    return anomalies
