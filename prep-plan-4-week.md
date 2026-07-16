# The 4-Week FDE Prep Plan

### Sequences the whole playbook into a schedule — conceptual reading paired with hands-on building every week

*Part of [The FDE Playbook](./README.md). If the rest of the stack is the reference library, this is the syllabus: what to read, build, and drill, in what order, so the conceptual material and the [capstones](./capstones/) reinforce each other instead of sitting side by side.*

> Budget roughly 2-3 hours/day. Each week ends with a checkpoint — don't move on until you can do it, not just recognize it. If you're short on time, the checkpoints are the part to protect; the reading list is compressible, the checkpoint isn't.

---

## Week 1 — Role & foundations

**Goal:** internalize how an FDE thinks before touching infrastructure. Everything downstream assumes this mental model.

**Read:**
- [README.md](./README.md) — the whole playbook, once, end to end
- [notes/01_fde_role_persona_and_mission.md](./notes/01_fde_role_persona_and_mission.md)
- [notes/12_consulting_mindset_and_frameworks.md](./notes/12_consulting_mindset_and_frameworks.md)
- [notes/13_discovery_checklist_and_scoping.md](./notes/13_discovery_checklist_and_scoping.md)
- [notes/20_fde_glossary_and_reference.md](./notes/20_fde_glossary_and_reference.md) + [glossary.md](./glossary.md) (skim both — on-ramps, not deep reads)
- [decision-driven-engineer.md](./decision-driven-engineer.md) Part 0 + [dsa-mastry-pattern.md](./dsa-mastry-pattern.md)'s recognition index
- 2-3 of [case-studies/](./case-studies/) — pick from different domains (e.g. [shadow-ai.md](./case-studies/shadow-ai.md), [clinical-doc-ai.md](./case-studies/clinical-doc-ai.md))

**Build/drill:**
- Run 5-8 DSA pattern-recognition drills from [dsa-mastry-pattern.md](./dsa-mastry-pattern.md) — timed, cold, no notes.
- For each case study you read, fill the [Discovery Toolkit](./discovery-toolkit.md)'s use-case scoring rubric and stakeholder map *as if you were the FDE on that engagement*, before reading the case study's own analysis of it.

**Checkpoint:** you can state the operating loop (land → wedge → prove value → productionize → expand), name the two currencies (speed, trust), and cold-summarize one case study's wedge + governance flag + demo-to-production gap in under 3 minutes.

---

## Week 2 — Data & cloud infrastructure

**Goal:** the plumbing every AI system sits on top of. This is the least glamorous week and the one that determines whether Week 3's systems actually work.

**Read:**
- [notes/02_advanced_sql_and_query_tuning.md](./notes/02_advanced_sql_and_query_tuning.md) through [notes/11_terraform_iac_for_fde.md](./notes/11_terraform_iac_for_fde.md) (10 notes — SQL, data modeling, medallion architecture, Spark/Ray, data quality, GCP networking, GKE, BigQuery, VPC Service Controls, Terraform)
- [databases/relational-database.md](./databases/relational-database.md), [databases/nosql-db.md](./databases/nosql-db.md), [databases/db-performance.md](./databases/db-performance.md)
- [reference-architecture.md](./reference-architecture.md) — read it as a spec, not prose; you're building it next week in Capstone 3
- [notes/21_hardware_gpu_inference_and_observability.md](./notes/21_hardware_gpu_inference_and_observability.md) §1-4 — the self-host-vs-API decision framework and GPU sizing math; this is infra decision-making, so it belongs here even though it's numbered 21

**Build/drill:**
- Write 3 non-trivial SQL queries against a dataset you already have access to (window functions, a CTE, an anti-join) — notes/02's patterns, not toy syntax.
- Read [capstones/incident_debugging/service.py](./capstones/incident_debugging/) start to finish and map every function back to a box in reference-architecture.md's diagram, before running it.

**Checkpoint:** you can draw reference-architecture.md's request lifecycle from memory and explain what each of the 3 "async" mentions is protecting against.

---

## Week 3 — AI/LLM systems & governance

**Goal:** the actual subject matter — RAG, evals, agents, and the governance layer that makes them deployable. This is the heaviest hands-on week.

**Read:**
- [notes/14_google_adk_multi_agent_orchestration.md](./notes/14_google_adk_multi_agent_orchestration.md), [notes/15_llm_evaluation_inner_outer_loop.md](./notes/15_llm_evaluation_inner_outer_loop.md), [notes/16_enterprise_rag_blueprint_gcp.md](./notes/16_enterprise_rag_blueprint_gcp.md)
- [notes/18_interview_blackbook_case_studies.md](./notes/18_interview_blackbook_case_studies.md) §2 — read this *before* touching Capstone 1, it's the worked answer
- [governance-playbook.md](./governance-playbook.md), [eu-ai-act.md](./eu-ai-act.md), [ai-and-data-governance.md](./ai-and-data-governance.md)
- [eval-driven-development.md](./eval-driven-development.md)
- [coding/rag.py](./coding/rag.py), [coding/mcp_coding.py](./coding/mcp_coding.py) — read as code, not prose

**Build/drill:**
- **[Capstone 1 — Enterprise RAG](./capstones/enterprise_rag/):** setup, baseline eval, then do the reranker exercise. Target: measurable recall improvement over baseline.
- **[Capstone 2 — Governance Assessment](./capstones/governance_assessment/):** run both sample profiles, then write your own third profile and defend its risk tier.

**Checkpoint:** `pytest tests/capstones/test_enterprise_rag.py tests/capstones/test_governance_assessment.py -v` passes, your reranked `retrieval_recall_at_k` beats the no-op baseline, and you can defend your Capstone 2 profile's risk classification without looking at the source.

---

## Week 4 — Production, debugging & interview

**Goal:** close the demo-to-production gap for real, then prove you can perform under interview conditions.

**Read:**
- [notes/17_observability_and_debugging_field.md](./notes/17_observability_and_debugging_field.md), [notes/19_artifact_templates.md](./notes/19_artifact_templates.md)
- [notes/21_hardware_gpu_inference_and_observability.md](./notes/21_hardware_gpu_inference_and_observability.md) §5-7 — the troubleshooting playbook and GPU-level observability signals, as the natural extension of notes/17
- Re-read [notes/18_interview_blackbook_case_studies.md](./notes/18_interview_blackbook_case_studies.md) in full
- [security/](./security/) Parts 2 and 6 at minimum (cloud/AI security + zero trust; OAuth/GDPR engineering) — more if security is your target domain, see [security/README.md](./security/README.md)

**Build/drill:**
- **[Capstone 3 — Incident/Debugging Drill](./capstones/incident_debugging/):** follow the [runbook](./capstones/incident_debugging/runbook.md) exactly — logs first, code second. Time yourself.
- **[Capstone 4 — Full-Stack Observability](./capstones/full_stack_observability/):** run `diagnose`, do the root-cause ranking exercise, then build a dry-run export to at least 2 of the 5 vendors (Datadog, Dynatrace, New Relic, Splunk, Grafana Cloud).
- Full mock interview loop using [interview-drills.md](./interview-drills.md): technical screen → system design → behavioral → deep dive/debugging → case study, each self-graded against that file's rubrics.

**Checkpoint:** all four capstones' tests pass (`pytest -q` from repo root, fully offline), you diagnosed the Capstone 3 fault in under 20 minutes without reading `service.py` first, you correctly ruled out 2 of Capstone 4's 4 candidate layers using correlation evidence rather than guessing, and you've completed one full mock loop with self-scored rubrics for every round.

---

## After week 4

Repeat the mock loop weekly with a fresh Capstone 3 seed
(`python -m capstones.incident_debugging run --seed <new>`) and a new
[interview-drills.md](./interview-drills.md) system-design prompt — the
goal is that the loop itself stops being novel, so what's left to perform
under pressure is the material, not the format.
