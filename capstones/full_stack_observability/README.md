# Capstone 4 — Full-Stack Observability

### The 5-layer / MELT framework, built and exported to every major platform

*Part of [The FDE Playbook](../../README.md)'s [capstones](../). Operationalizes the full-stack observability model — 5 layers (User Experience, Application, Infrastructure, Network, Data & AI) instrumented with MELT (Metrics, Events, Logs, Traces) — as real, testable code, then shows the same telemetry exported to Datadog, Dynatrace, New Relic, Splunk, and Grafana Cloud via one OTLP exporter. Complements [notes/17](../../notes/17_observability_and_debugging_field.md) (app/GCP layer) and [notes/21](../../notes/21_hardware_gpu_inference_and_observability.md) (GPU layer) — this capstone is the cross-layer correlation piece neither of those covers.*

## Objective

Diagnose a full-stack incident the way a platform like Datadog or
Dynatrace claims to make possible: start from a business-impact signal
(cart abandonment rate), trace down through the layers using real
correlation math — not vibes — and end with a ranked, evidence-backed root
cause that also explicitly rules out the layers that are clean.

## The scenario

[`simulate.py`](./simulate.py) generates 60 minutes of a synthetic
e-commerce checkout flow. At minute 30, an `inventory-db` query latency
spike is injected (Data & AI layer). It cascades: `inventory-service`'s
spans slow down (Application layer) → checkout page interaction latency
rises (User Experience layer) → cart abandonment rate climbs (the business
metric). The Infrastructure layer (pod CPU) and Network layer (DNS
resolution) stay flat throughout — they're the red herrings a full-stack
tool (and a candidate) needs to correctly rule out, not just ignore.

## Setup

```bash
pip install -e .          # from repo root; stdlib-only, no vendor account needed
python -m capstones.full_stack_observability simulate
python -m capstones.full_stack_observability topology
python -m capstones.full_stack_observability diagnose
python -m capstones.full_stack_observability export --vendor local
```

## The exercise

[`correlation.py`](./correlation.py)'s `rank_root_cause_candidates()` is a
deliberate no-op — it returns the same 4 candidate metrics in declaration
order, not ranked. Fix it to sort by `abs(correlation)` descending, so
`inventory_db_query_ms` (correlation ≈0.95) surfaces first and
`checkout_pod_cpu_pct`/`dns_resolution_ms` (correlation ≈0) are visibly
last — i.e. ruled out, not just present. `cli.py diagnose` prints this
list directly; re-run it before and after your fix.

## Grading rubric

| Dimension | 1 (needs work) | 3 (solid) | 5 (strong) |
|---|---|---|---|
| Root cause identification | Named a layer without evidence | Named `inventory_db_query_ms` and cited its correlation coefficient | Also explained *why* the other 3 candidates are ruled out (near-zero correlation), not just silent |
| Topology reasoning | Didn't use `topology.py`'s output | Used the dependency graph to explain the cascade (`inventory-db` → `inventory-service` → `checkout-service`) | Could point to the exact span (`check_inventory`) via `critical_path()` as where the latency actually accumulates |
| Anomaly detection | Didn't run `anomaly.py` | Ran it, found the spike at minute 30 | Can explain why a rolling baseline (not a fixed threshold) is what makes this "AI-driven alerting" rather than a static alert rule |
| Multi-vendor export | Only tested `--vendor local` | Built a dry-run request for at least 2 of the 5 vendors | Can explain, without looking, why the *same* `OTLPHTTPExporter` class works for all 5 (they all speak OTLP) — this is the actual point of the exercise |

Run `pytest tests/capstones/test_full_stack_observability.py -v`.

## "For all providers" — the multi-vendor export

[`exporters.py`](./exporters.py)'s `VENDOR_CONFIGS` covers all 5 platforms
named in the source brief:

| Vendor | Endpoint pattern | Auth header |
|---|---|---|
| Datadog | `https://otlp.{site}/v1/traces` | `DD-API-KEY` |
| Dynatrace | `https://{environment_id}.live.dynatrace.com/api/v2/otlp/v1/traces` | `Authorization: Api-Token ...` |
| New Relic | `https://otlp.nr-data.net:4318/v1/traces` | `api-key` |
| Splunk (Observability Cloud) | `https://ingest.{realm}.signalfx.com/v2/trace/otlp` | `X-SF-Token` |
| Grafana Cloud | `https://otlp-gateway-{region}.grafana.net/otlp` | `Authorization: Basic ...` |

Every one of them is a config entry, not a new integration — that's the
lesson: instrument with OTel once, and the vendor becomes a swappable
backend rather than something re-instrumented per migration.
`OTLPHTTPExporter.export()` defaults to `dry_run=True` (build the
request, send nothing) so this is safe to explore without a vendor
account; `--send` with a real `--api-key` sends it for real.

**Endpoints/headers are illustrative of the pattern each vendor documents
at time of writing** — verify current ingestion URLs against the vendor's
own OTLP docs before pointing real traffic at them.

## Go live (stretch goal)

Swap `simulate.py`'s synthetic generator for the `opentelemetry-sdk`
instrumenting a real service, and point `OTLPHTTPExporter` at a real
vendor sandbox account with `--send`. Compare the vendor's own root-cause
suggestion (Dynatrace's Davis AI, Datadog's Watchdog) against what
`diagnose` computed here — and be ready to explain any disagreement.
