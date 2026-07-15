# Glossary

### One page for every acronym and term this stack assumes you already know

*Part of [The FDE Playbook](./README.md). Each entry links to the doc where it's covered in depth — use this as the on-ramp, not the destination.*

> `eu-ai-act.md` alone assumes you're comfortable with GDPR, GPAI, Annex III, and conformity assessment on the first page. This is the wall of context for a reader jumping into any one file cold.

---

## Regulatory & governance

| Term | Meaning | Covered in depth |
|---|---|---|
| **EU AI Act** | Regulation 2024/1689 — the EU's comprehensive, risk-based AI law | [eu-ai-act.md](./eu-ai-act.md) |
| **GPAI** | General-Purpose AI model — a foundation model with obligations under EU AI Act Chapter V, separate from and stacking on top of your product's own risk tier | [eu-ai-act.md](./eu-ai-act.md) |
| **Annex I / Annex III** | Annex I = AI as a safety component of an already-regulated product (medical devices, machinery). Annex III = AI used in a listed high-stakes domain (hiring, credit, biometrics, etc.). Either triggers high-risk obligations | [eu-ai-act.md](./eu-ai-act.md) |
| **Provider vs. deployer** | Provider = who builds/ships the AI system. Deployer = who uses it. Obligations split between the two; fine-tuning can turn a deployer into a provider | [eu-ai-act.md](./eu-ai-act.md), [governance-playbook.md](./governance-playbook.md) |
| **Conformity assessment** | The process of confirming a high-risk system meets its obligations — usually self-assessment (Annex VI), sometimes a third-party notified body (Annex VII) | [eu-ai-act.md](./eu-ai-act.md) |
| **CE marking** | The physical/digital mark declaring EU conformity, affixed after a signed Declaration of Conformity | [eu-ai-act.md](./eu-ai-act.md) |
| **Digital Omnibus** | The 2025–2026 EU simplification package that deferred high-risk deadlines (Annex III to Dec 2027, Annex I to Aug 2028) and eased some GDPR/AI Act friction | [eu-ai-act.md](./eu-ai-act.md), [ai-and-data-governance.md](./ai-and-data-governance.md) |
| **NIST AI RMF** | US risk-management framework — four functions: Govern, Map, Measure, Manage. Portable across jurisdictions | [governance-playbook.md](./governance-playbook.md) |
| **ISO/IEC 42001** | The certifiable AI management-system standard — like ISO 27001, but for AI. The auditable backbone that maps cleanly onto the EU Act | [governance-playbook.md](./governance-playbook.md) |
| **GDPR** | EU's general data-protection law — lawful basis, data-subject rights, DPIAs, cross-border transfer rules, fines up to 4% of global turnover | [ai-and-data-governance.md](./ai-and-data-governance.md) |
| **DPDP** | India's Digital Personal Data Protection Act — India's primary data-governance backbone in the absence of a standalone AI law | [ai-and-data-governance.md](./ai-and-data-governance.md) |
| **PIPL** | China's Personal Information Protection Law — part of China's vertical, state-control-oriented data/AI regime alongside DSL and CSL | [ai-and-data-governance.md](./ai-and-data-governance.md) |
| **FRIA** | Fundamental Rights Impact Assessment — required of some deployers of high-risk EU AI Act systems (public bodies, some private deployers) before use | [eu-ai-act.md](./eu-ai-act.md) |
| **Extraterritoriality** | The default assumption that a data/AI regime applies to you if you serve that market, regardless of where you're headquartered | [governance-playbook.md](./governance-playbook.md) |

---

## Architecture & engineering

| Term | Meaning | Covered in depth |
|---|---|---|
| **Instrumented service layer** | The single gateway every model call flows through — the substrate for logging, evals, guardrails, cost control, and compliance | [reference-architecture.md](./reference-architecture.md) |
| **Guardrails** | Input/output checks — PII redaction, prompt-injection defense, policy/format validation — sitting inside the service layer | [reference-architecture.md](./reference-architecture.md) |
| **Golden set** | The curated, held-out, continuously-grown set of real examples an eval is scored against | [eval-harness.md](./eval-harness.md) |
| **LLM-as-judge** | Using a model to score another model's output against a rubric — fast and scalable, but needs calibration against human labels and position-bias controls | [eval-harness.md](./eval-harness.md) |
| **Groundedness** | In RAG evaluation: whether an answer is actually supported by the retrieved context, independent of whether the answer is correct | [eval-harness.md](./eval-harness.md) |
| **PACELC** | Extension of CAP theorem: during a **P**artition choose **A**vailability or **C**onsistency; **E**lse (normal ops) choose **L**atency or **C**onsistency | [decision-driven-engineer.md](./decision-driven-engineer.md) |
| **Little's Law** | `concurrency = arrival_rate × latency` — sizes thread pools, connection pools, and queues | [decision-driven-engineer.md](./decision-driven-engineer.md) |
| **Mechanical sympathy** | Designing with the hardware's real behavior in mind (cache lines, branch prediction, memory hierarchy) rather than against it | [decision-driven-engineer.md](./decision-driven-engineer.md) |
| **Amdahl's Law** | Speedup from parallelism is capped by the serial fraction of the work — more cores can't fix a serial bottleneck | [decision-driven-engineer.md](./decision-driven-engineer.md) |

---

## FDE role & process

| Term | Meaning | Covered in depth |
|---|---|---|
| **The wedge** | The one narrow, real, high-value use case you win first and expand from — not the whole roadmap at once | [README.md](./README.md) |
| **Land-and-expand** | The first deployment is a beachhead, not the war — you expand across the org from earned trust | [README.md](./README.md) |
| **The last mile** | Integration, evals, guardrails, data plumbing, change management — the unglamorous 80% of the actual work | [README.md](./README.md) |
| **Demo-to-production gap** | The distance between a model working on 10 hand-picked inputs and working reliably on 10,000 messy real ones | [README.md](./README.md) |
| **Champion / economic buyer / blocker** | Stakeholder types: who wants you to win, who controls budget, who can stop the deal — see the fillable map | [discovery-toolkit.md](./discovery-toolkit.md) |
| **Value × feasibility × visibility** | The three axes used to score and rank candidate use cases during discovery | [discovery-toolkit.md](./discovery-toolkit.md) |

---

*Back to [The FDE Playbook](./README.md)*
