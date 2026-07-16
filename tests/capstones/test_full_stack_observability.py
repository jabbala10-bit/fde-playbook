"""Contract tests for Capstone 4 (Full-Stack Observability). Fully local —
the simulator is synthetic/offline, and vendor exports default to dry_run
so no test ever makes a network call."""

from __future__ import annotations

import json

import pytest

from capstones.full_stack_observability.anomaly import detect_anomalies
from capstones.full_stack_observability.collector import Collector
from capstones.full_stack_observability.correlation import (
    correlate_with_business_metric,
    pearson_correlation,
)
from capstones.full_stack_observability.exporters import (
    VENDOR_CONFIGS,
    LocalJSONExporter,
    OTLPHTTPExporter,
    batch_to_otlp_json,
)
from capstones.full_stack_observability.simulate import INCIDENT_START_TICK, simulate
from capstones.full_stack_observability.telemetry import Layer
from capstones.full_stack_observability.topology import build_topology, critical_path


@pytest.fixture
def collector() -> Collector:
    c = Collector()
    c.ingest(simulate(seed=42))
    return c


def test_pearson_correlation_perfect_and_none():
    assert pearson_correlation([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)
    assert pearson_correlation([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)
    assert pearson_correlation([1, 1, 1], [1, 2, 3]) == 0.0  # zero variance guard


def test_simulate_produces_all_five_layers(collector):
    for layer in Layer:
        has_metric = bool(collector.metrics(layer=layer))
        has_span = any(s.layer == layer for s in collector.spans())
        assert has_metric or has_span, f"no telemetry emitted for layer {layer}"


def test_topology_reflects_service_dependencies(collector):
    graph = build_topology(collector.spans())
    assert graph["checkout-service"] == {"inventory-service", "payment-service"}
    assert graph["inventory-service"] == {"inventory-db"}


def test_critical_path_orders_by_duration(collector):
    trace_id = collector.trace_ids()[0]
    path = critical_path(collector.spans(), trace_id)
    durations = [d for _, d in path]
    assert durations == sorted(durations, reverse=True)


def test_root_cause_metric_correlates_strongly_with_business_metric(collector):
    """The injected root cause (inventory_db_query_ms) must dominate the
    ranking — this is the core claim the capstone's diagnosis exercise
    depends on."""
    results = {name: corr for name, _, corr in correlate_with_business_metric(collector)}
    assert results["inventory_db_query_ms"] > 0.7


def test_infra_and_network_layers_are_ruled_out(collector):
    """Infrastructure and network metrics must NOT correlate with the
    business impact — that's the "ruling out" half of the exercise."""
    results = {name: corr for name, _, corr in correlate_with_business_metric(collector)}
    assert abs(results["checkout_pod_cpu_pct"]) < 0.3
    assert abs(results["dns_resolution_ms"]) < 0.3


def test_anomaly_detection_flags_the_injected_incident(collector):
    metrics = collector.metrics(layer=Layer.DATA_AI, name="inventory_db_query_ms")
    anomalies = detect_anomalies(metrics)
    incident_ts = INCIDENT_START_TICK * 60
    assert any(a.timestamp == incident_ts for a in anomalies)
    incident_anomaly = next(a for a in anomalies if a.timestamp == incident_ts)
    assert incident_anomaly.z_score > 10  # an unmistakable spike, not a borderline one


def test_local_exporter_writes_valid_json(collector, tmp_path):
    path = tmp_path / "export.json"
    LocalJSONExporter(str(path)).export(collector.batch())
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "resourceMetrics" in data
    assert len(data["resourceMetrics"]) == len(collector.metrics())


def test_batch_to_otlp_json_round_trips_counts(collector):
    payload = batch_to_otlp_json(collector.batch())
    assert len(payload["resourceSpans"]) == len(collector.spans())
    assert len(payload["resourceEvents"]) == len(collector.events())


@pytest.mark.parametrize("vendor", sorted(VENDOR_CONFIGS))
def test_otlp_exporter_builds_a_request_for_every_vendor(vendor, collector):
    """'For all providers': the same generic exporter must produce a valid
    endpoint + auth header for each of the 5 vendors named in the brief."""
    kwargs = {"environment_id": "abc12345"} if vendor == "dynatrace" else {}
    exporter = OTLPHTTPExporter(vendor, api_key="TESTKEY", **kwargs)
    request = exporter.build_request(collector.batch())
    assert request["endpoint"].startswith("https://")
    assert "TESTKEY" in next(iter(request["headers"].values())) or any(
        "TESTKEY" in v for v in request["headers"].values()
    )


def test_otlp_exporter_dry_run_never_sends(collector):
    exporter = OTLPHTTPExporter("new_relic", api_key="TESTKEY", dry_run=True)
    assert exporter.export(collector.batch()) is None


def test_otlp_exporter_missing_required_kwarg_raises_clear_error(collector):
    exporter = OTLPHTTPExporter("dynatrace", api_key="TESTKEY")  # no environment_id
    with pytest.raises(ValueError, match="environment_id"):
        exporter.build_request(collector.batch())


def test_unknown_vendor_rejected():
    with pytest.raises(ValueError):
        OTLPHTTPExporter("not_a_real_vendor")
