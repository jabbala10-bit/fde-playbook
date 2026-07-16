# Capstone 2 — Governance Assessment Tool

### The artifact an FDE actually hands a customer during discovery/scoping

*Part of [The FDE Playbook](../../README.md)'s [capstones](../). Ties to [governance-playbook.md](../../governance-playbook.md) and the [Discovery Toolkit](../../discovery-toolkit.md)'s governance checklist — this is the code-generated version of that checklist's output.*

## Objective

Given a structured description of an AI system, produce a combined EU AI
Act + GDPR risk classification, an obligations list, and a remediation
checklist — in both JSON (machine-readable) and Markdown (customer-facing)
form. Reuses [`coding/eu-ai-act.py`](../../coding/eu-ai-act.py)'s
`EUAIActAssessor` and [`coding/gdpr.py`](../../coding/gdpr.py)'s
`GDPRAssessor` rather than reimplementing the rule engines — see
[`loader.py`](./loader.py) for how a hyphenated, non-package script gets
loaded and reused.

## Setup

```bash
pip install -e .          # from repo root; stdlib-only
python -m capstones.governance_assessment assess capstones/governance_assessment/sample_systems/legal-rag-system.json --format markdown
python -m capstones.governance_assessment assess capstones/governance_assessment/sample_systems/clinical-doc-ai.json --format markdown
```

Two worked sample profiles are included:
- `sample_systems/legal-rag-system.json` — the Capstone 1 RAG system, classifies as **transparency** (EU AI Act) / **high_risk_processing** (GDPR).
- `sample_systems/clinical-doc-ai.json` — echoes [case-studies/clinical-doc-ai.md](../../case-studies/clinical-doc-ai.md)'s ambient documentation system, classifies as **high_risk** (EU AI Act) / **special_category_data** (GDPR) — matching that case study's "patient safety event" framing.

## The exercise

Write a third profile for a system of your own choosing (reuse one of the
other [case studies](../../case-studies/) if you want a running start) and
defend, in a paragraph, why it lands at the risk tier it does — which flags
or keywords in your profile actually drove the classification. Then check
your reasoning against `_eu.EUAIActAssessor.detect()` and
`_gdpr.GDPRAssessor.detect()`'s rule logic in the source files.

## Grading rubric

| Dimension | 1 (needs work) | 3 (solid) | 5 (strong) |
|---|---|---|---|
| Risk tier | Can't explain why the tool picked the tier it did | Can point to the specific flags/keywords that drove it | Can predict the tier *before* running the tool, for a new profile |
| Obligation mapping | Obligations list is treated as a black box | Can map each obligation back to an EU AI Act article or GDPR provision | Can explain which obligations would change if the actor role flipped (provider vs. deployer, controller vs. processor) |
| Remediation checklist | Checklist copied verbatim into a customer deliverable | Checklist translated into concrete next actions with owners | Checklist sequenced by risk-reduction-per-effort, matching the [Discovery Toolkit](../../discovery-toolkit.md)'s "de-risk the biggest unknown first" |

Run `pytest tests/capstones/test_governance_assessment.py -v`.

## Go live (stretch goal)

Wire a real LLM (Claude API, `pip install -e '.[live]'` +
`ANTHROPIC_API_KEY`) to turn `to_markdown()`'s structured output into a
narrative remediation memo a non-technical stakeholder could read — the
"translate up" skill from the root [README.md](../../README.md)'s
Communication section.
