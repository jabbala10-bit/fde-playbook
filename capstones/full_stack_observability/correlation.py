"""Correlates technical layer metrics with the business-impact metric
(cart_abandonment_rate) — the "Business Metric Correlation" capability
described in the platform vendor brief, implemented on real (synthetic)
telemetry rather than taken on faith."""

from __future__ import annotations

import statistics
from typing import Dict, List, Tuple

from .collector import Collector
from .telemetry import Layer

CANDIDATE_METRICS = [
    ("inventory_db_query_ms", Layer.DATA_AI),
    ("cache_hit_rate", Layer.DATA_AI),
    ("checkout_pod_cpu_pct", Layer.INFRASTRUCTURE),
    ("dns_resolution_ms", Layer.NETWORK),
]

BUSINESS_METRIC = ("cart_abandonment_rate", Layer.USER_EXPERIENCE)


def _series_by_timestamp(collector: Collector, name: str, layer: Layer) -> Dict[float, float]:
    return {m.timestamp: m.value for m in collector.metrics(layer=layer, name=name)}


def pearson_correlation(xs: List[float], ys: List[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    mean_x, mean_y = statistics.mean(xs), statistics.mean(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    denom = (var_x * var_y) ** 0.5
    return cov / denom if denom else 0.0


def correlate_with_business_metric(collector: Collector) -> List[Tuple[str, Layer, float]]:
    """Returns [(metric_name, layer, correlation)] for every candidate
    metric against cart_abandonment_rate, aligned by timestamp."""
    business_name, business_layer = BUSINESS_METRIC
    business_series = _series_by_timestamp(collector, business_name, business_layer)

    results = []
    for name, layer in CANDIDATE_METRICS:
        series = _series_by_timestamp(collector, name, layer)
        shared_ts = sorted(set(series) & set(business_series))
        xs = [series[t] for t in shared_ts]
        ys = [business_series[t] for t in shared_ts]
        results.append((name, layer, pearson_correlation(xs, ys)))
    return results


def rank_root_cause_candidates(collector: Collector) -> List[Tuple[str, Layer, float]]:
    """CAPSTONE EXERCISE — this currently returns candidates in
    declaration order, not ranked. A real root-cause ranking should sort
    by absolute correlation descending, so the most likely cause surfaces
    first and the layers that are actually clean (near-zero correlation)
    are visibly ruled out, not just omitted. Implement that; cli.py's
    `diagnose` narrative reads this list's order directly."""
    return correlate_with_business_metric(collector)
