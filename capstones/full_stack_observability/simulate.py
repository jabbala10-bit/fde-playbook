"""Simulates a full-stack incident: an e-commerce checkout flow across all
5 layers, with a single root cause (a Data & AI-layer database latency
spike) that cascades up to a business-impact signal (cart abandonment) —
while the Infrastructure and Network layers stay clean throughout.

Diagnosing this correctly means tracing down from the business-impact
signal through the layers *and* explicitly ruling out the layers that
are not the cause — that ruling-out step is as much the skill being
taught here as finding the actual root cause.
"""

from __future__ import annotations

import random
import uuid

from .telemetry import Event, Layer, LogRecord, Metric, Span, TelemetryBatch

TICKS = 60
INCIDENT_START_TICK = 30
SESSIONS_PER_TICK = 20


def simulate(seed: int = 42) -> TelemetryBatch:
    rng = random.Random(seed)
    batch = TelemetryBatch()

    for tick in range(TICKS):
        ts = float(tick * 60)  # one tick = one minute
        incident_active = tick >= INCIDENT_START_TICK

        # --- Data & AI layer: the root cause ---
        db_latency = max(1.0, rng.gauss(20, 4) if not incident_active else rng.gauss(400, 60))
        batch.metrics.append(
            Metric("inventory_db_query_ms", db_latency, ts, Layer.DATA_AI, {"table": "inventory"})
        )
        cache_hit_rate = max(0.0, min(1.0, rng.gauss(0.85, 0.03)))
        batch.metrics.append(Metric("cache_hit_rate", cache_hit_rate, ts, Layer.DATA_AI))

        # --- Infrastructure layer: unaffected (a rule-out signal) ---
        cpu_pct = max(0.0, min(100.0, rng.gauss(35, 5)))
        batch.metrics.append(Metric("checkout_pod_cpu_pct", cpu_pct, ts, Layer.INFRASTRUCTURE))

        # --- Network layer: unaffected (a rule-out signal) ---
        dns_ms = max(0.1, rng.gauss(8, 2))
        batch.metrics.append(Metric("dns_resolution_ms", dns_ms, ts, Layer.NETWORK))

        # --- per-session traces + UX/business signal ---
        abandoned = 0
        for _ in range(SESSIONS_PER_TICK):
            trace_id = str(uuid.uuid4())
            root_id = str(uuid.uuid4())
            inv_id = str(uuid.uuid4())
            pay_id = str(uuid.uuid4())

            db_span_ms = max(1.0, rng.gauss(db_latency, db_latency * 0.1))
            inventory_span_ms = db_span_ms + rng.gauss(5, 1)
            payment_span_ms = max(1.0, rng.gauss(50, 8))  # unaffected by the incident
            root_span_ms = inventory_span_ms + payment_span_ms + rng.gauss(15, 3)

            batch.spans.append(
                Span(trace_id, root_id, "POST /checkout", "checkout-service", ts, root_span_ms, Layer.APPLICATION)
            )
            batch.spans.append(
                Span(
                    trace_id, inv_id, "check_inventory", "inventory-service", ts,
                    inventory_span_ms, Layer.APPLICATION, parent_span_id=root_id,
                )
            )
            batch.spans.append(
                Span(
                    trace_id, str(uuid.uuid4()), "SELECT inventory", "inventory-db", ts,
                    db_span_ms, Layer.DATA_AI, parent_span_id=inv_id,
                )
            )
            batch.spans.append(
                Span(
                    trace_id, pay_id, "charge_card", "payment-service", ts,
                    payment_span_ms, Layer.APPLICATION, parent_span_id=root_id,
                )
            )

            interaction_ms = root_span_ms + rng.gauss(200, 30)
            batch.metrics.append(
                Metric(
                    "checkout_interaction_latency_ms", interaction_ms, ts,
                    Layer.USER_EXPERIENCE, {"trace_id": trace_id},
                )
            )

            if rng.random() < _abandon_probability(interaction_ms):
                abandoned += 1
                batch.events.append(Event("cart_abandoned", ts, Layer.USER_EXPERIENCE, {"trace_id": trace_id}))
            else:
                batch.events.append(Event("checkout_completed", ts, Layer.USER_EXPERIENCE, {"trace_id": trace_id}))

        batch.metrics.append(
            Metric("cart_abandonment_rate", abandoned / SESSIONS_PER_TICK, ts, Layer.USER_EXPERIENCE)
        )

        if tick == INCIDENT_START_TICK:
            batch.logs.append(
                LogRecord(
                    "inventory-db slow query threshold breached",
                    ts, Layer.DATA_AI, severity="WARNING", attributes={"table": "inventory"},
                )
            )

    return batch


def _abandon_probability(interaction_ms: float) -> float:
    """Simple comfort-threshold model: abandonment climbs once interaction
    latency crosses ~400ms (baseline sessions run ~290ms; incident sessions
    run ~670ms), saturating well above it."""
    comfort_threshold = 400.0
    if interaction_ms <= comfort_threshold:
        return 0.03
    excess = interaction_ms - comfort_threshold
    return min(0.9, 0.03 + excess / 600.0)
