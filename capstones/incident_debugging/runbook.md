# Runbook — Incident Debugging Drill

### How to approach this the way you would a real production incident

1. **Generate the trace, don't peek at the fault.**
   ```bash
   python -m capstones.incident_debugging run --seed 7 > incident.json
   ```
   Pick any seed. Do **not** pass `--reveal` until after you've fixed it.

2. **Read the trace like an on-call engineer, not a code reader.** Look at
   `incident.json`'s `trace` (per-request outcome, including `error`) and
   `logs` (the structured audit record — latency, cost_tokens,
   guardrail_flags, eval_score) before opening `service.py`. Ask:
   - Did any request error out? What's common about the ones that did?
   - Is `input_redacted` actually redacted where it should be?
   - Is `cost_tokens` ever larger than you'd expect for a capped service?
   - Is `latency_ms` suspiciously high on some requests and not others?

3. **Form a hypothesis before reading `service.py`.** Which stage of the
   pipeline (Gateway → Input Guardrails → Router → Model Call → Output
   Guardrails → Logging → Eval Sampling, per
   [reference-architecture.md](../../reference-architecture.md)) does the
   evidence point to?

4. **Locate the fault in `service.py`.** Every seeded bug is marked with a
   `# BUG:` comment once you find it — but find it from the logs first.

5. **Fix the root cause, not the symptom.** E.g. don't catch-and-swallow an
   exception from a degraded backend — fix the routing logic so the
   fallback actually gets consulted.

6. **Prove it.** Run:
   ```bash
   pytest tests/capstones/test_incident_debugging.py -v
   ```
   The parametrized test for your fault should still pass (it proves the
   *fault-injection* mechanism works), and re-running
   `python -m capstones.incident_debugging run --seed 7 --reveal` against
   your patched `service.py` (temporarily hardcode the revealed fault name,
   or just call `ServiceLayer(fault=None)` — the reference-correct config)
   should show the bug is gone.

## The four seeded faults

| Fault | Pipeline stage | What it looks like in the trace |
|---|---|---|
| `pii_redaction_bypass` | Input guardrails | `input_redacted` still contains the raw SSN pattern |
| `missing_token_cap` | Model call | `cost_tokens` exceeds the 20-token cap on long prompts |
| `fallback_never_fires` | Router | Every request to `support-classifier` errors with "backend 'model-a' is degraded" |
| `eval_sampling_blocks_path` | Logging + eval sampling | `latency_ms` is elevated on every request, `eval_score` is populated synchronously |

## Grading rubric

| Dimension | 1 (needs work) | 3 (solid) | 5 (strong) |
|---|---|---|---|
| Root cause | Patched the symptom (e.g. caught the exception) | Identified and fixed the actual faulty logic | Can explain why the *design* (not just this instance) allowed the bug — e.g. "nothing enforced that the fallback path was ever exercised in tests" |
| Evidence-first diagnosis | Opened `service.py` before reading the trace | Formed a hypothesis from `incident.json` before reading code | Could have named the fault from the trace alone, no code needed |
| Regression proof | No test written/run | Existing parametrized test passes against the fix | Added a new test that would have caught this bug in code review |
| Time | N/A | Diagnosed and fixed within ~20 minutes | Within ~10 minutes, matching the pace of Round 4 (Technical Deep Dive) in [notes/18](../../notes/18_interview_blackbook_case_studies.md) |
