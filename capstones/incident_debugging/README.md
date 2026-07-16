# Capstone 3 — Production Incident/Debugging Drill

### The instrumented service layer from reference-architecture.md, as real code — with a bug hidden in it

*Part of [The FDE Playbook](../../README.md)'s [capstones](../). [`service.py`](./service.py) implements [reference-architecture.md](../../reference-architecture.md)'s request lifecycle (Gateway → Input Guardrails → Router → Model Call → Output Guardrails → Logging → Eval Sampling) — the architecture three other docs in this stack point to but never build. This capstone builds it, then breaks it on purpose.*

## Objective

Diagnose and fix a seeded production bug the way you'd actually do it in
the field: from logs and symptoms first, source code second. This is also
the closest thing in the repo to Interview Round 4 ("Technical Deep Dive
... live coding or debugging session ... architecture critique") from
[notes/18](../../notes/18_interview_blackbook_case_studies.md).

## Setup

```bash
pip install -e .          # from repo root; stdlib-only
python -m capstones.incident_debugging run --seed 7
```

Full instructions: [runbook.md](./runbook.md). Don't pass `--reveal` until
you've formed a hypothesis from the trace.

## Grading rubric

See [runbook.md](./runbook.md#grading-rubric).

## Go live (stretch goal)

Swap the in-memory `LogRecord` list in `service.py` for real GCP Cloud
Logging + Cloud Monitoring, per
[notes/17_observability_and_debugging_field.md](../../notes/17_observability_and_debugging_field.md),
and reproduce the same drill against a real dashboard instead of a JSON
dump.
