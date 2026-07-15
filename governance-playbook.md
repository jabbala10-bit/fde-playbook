# The FDE Governance Playbook

### Using AI & data governance as a deployment tool — for Forward-Deployed Engineers and full-stack AI architects

> Most engineers treat governance as a compliance tax that lands late. For an FDE it's the opposite: you're the rare person who is technical, customer-facing, *and* owns the deployment end to end — so governance questions land on **you first**, in the discovery room, before anything is built. Handled well, governance fluency is a deal-accelerator and a moat, not overhead. This playbook is how to hold it and how to use it.

---

## The reframe (read this first)

Governance is not a gate at the end of the build. For you it's an **input at the start** and a **capability you sell**.

- The enterprise deals that stall — finance, healthcare, government, anything touching personal data — stall in *legal and risk review*. The person who can sit in the room and say "here's what your use case triggers, here's how we architect around it, here's what you own vs. what we own" **unblocks those deals**. That person shortens the sales cycle.
- You are translating between three languages at once: the **model's capabilities**, the **customer's business**, and the **regulatory frame**. Almost no one can speak all three. That's the moat.
- Governance done right is **compliance-by-design**: the same instrumented service layer you'd build for observability, cost, and evals *is* your governance substrate. You're not adding work — you're getting compliance as a side effect of good architecture.

**Your role in one line:** you are the *translator and flag-raiser*, not the lawyer. Know enough to classify a use case live, design around it, and know when to escalate to counsel.

---

## What to carry in your head

You don't memorize statutes. You carry four layers, in priority order.

### 1. The four mental models (these reason about almost anything)
- **Classify by use, not by tech.** The same model is minimal-risk in one feature and high-risk in another. Risk attaches to the *use case*.
- **Provider vs. deployer.** Who *builds/ships* it vs. who *uses* it decides whose obligations are whose. This determines what you own vs. what the customer owns.
- **Data governance is AI governance.** AI runs on data; the data regime (GDPR, DPDP, etc.) is usually where AI compliance actually lives.
- **Extraterritoriality is the default.** You rarely escape a regime by being headquartered elsewhere — it applies if you serve that market.

### 2. The regime map (know which applies to *this* customer)
Enough working knowledge to raise the flag early, not to write the opinion: EU AI Act (risk tiers), data laws (GDPR, UK GDPR/DUAA, India DPDP, Korea PIPA, China PIPL), the US federal-vs-state patchwork, and sector rules (HIPAA, financial services, etc.). *You only need the ones your customer touches.*

### 3. The portable frameworks (learn these deeply — your operating system)
- **NIST AI RMF** — the risk-management method: **Govern · Map · Measure · Manage**.
- **ISO/IEC 42001** — the AI management system standard (auditable, certifiable).

These travel across every jurisdiction, they're what you actually *build and document against*, and several regimes reward adopting them (US state safe harbors). If you master one thing in this playbook, make it these two.

### 4. The frontier-model layer (if you deploy frontier models)
Model-level governance: evals and red-teaming, safety cases, systemic-risk thresholds, acceptable-use policies, and the lab's responsible-scaling / deployment commitments. **At the customer boundary you are often the enforcement point** for the lab's usage policies, plus misuse monitoring and dual-use / export-control awareness.

---

## The operating model — governance across the deployment lifecycle

Governance is a *different job* at each stage. This is the spine of how you use it.

| Stage | Your governance job | Output |
|---|---|---|
| **Discovery / scoping** | Ask the governance questions *first*. Classify the use, flag deal-breakers before build. | A risk classification + escalation flags |
| **Architecture** | Translate obligations into system design (logging, evals, human-in-loop, guardrails, data residency). Compliance-by-design. | A reference architecture with governance hooks |
| **Build** | Generate artifacts inside the normal SDLC — not a separate compliance project. | Risk register, evals in CI, versioned tech docs, data lineage |
| **Rollout / handoff** | Make the customer competent to operate compliantly as *deployer*. | Instructions-for-use, oversight training, monitoring + incident process |
| **Production** | Keep the post-market loop running. | Drift/incident monitoring, docs kept current on every change |

The highest-leverage stage is **discovery** — catching that a use is high-risk or prohibited *before* three months of build is the single most valuable thing you do.

---

## Deep dive 1 — The discovery question set (run this with the customer)

Ask these in scoping. Each answer either clears the path or raises a flag. You're not interrogating — you're de-risking their project and yours.

**Jurisdiction & reach**
- Which countries are the users in? Where is the data stored and processed?
- Any data leaving a region (cross-border transfer)? Any data-residency requirements?

**Use case & risk tier**
- What decision does the system make or influence, and about whom?
- Does it touch any high-stakes domain — hiring/HR, credit/essential services, healthcare, biometrics, education, law enforcement, critical infrastructure? *(→ EU high-risk gate)*
- Could it be read as manipulation, social scoring, or emotion/biometric inference? *(→ prohibited-practice gate)*
- Is there a human in the loop, or is it fully automated? *(→ automated-decision rules)*

**Data**
- Does it process personal data? Special-category data (health, biometric, etc.)?
- Any children's/minors' data? *(→ strict consent regimes)*
- What's the lawful basis for the training and the runtime data?
- What's the data lineage — where did training/context data come from, and are the rights clean?

**Roles & responsibility**
- Are we the *provider* or the *deployer* here — or does fine-tuning make us a provider?
- Who signs off on the risk acceptance? Who's accountable on the customer side (DPO, risk owner)?

**Model & capability**
- Own model, hosted API, or fine-tune? *(→ GPAI provider vs. downstream)*
- What's the acceptable-use policy of the model provider, and can this use case violate it?
- What's the blast radius if it's wrong, jailbroken, or misused?

**Deployment & operations**
- What logging, monitoring, and human-override does the workflow need?
- What's the incident path when it fails in production?
- What existing framework does the customer run (ISO 42001? NIST? none)?

> The pattern: **three of these questions usually surface the one constraint that reshapes the whole design.** That's the same "find the number that breaks the naive design" move from system design — applied to compliance.

---

## Deep dive 2 — Governance hooks in your reference architecture

Design these once, into your standard stack, and every deployment inherits compliance. The unifying idea: **route every model call through one instrumented service layer.** That single layer is where most obligations get satisfied at once.

| Governance hook | What it does | Which obligations it satisfies |
|---|---|---|
| **Unified model-call gateway** | Every inference flows through one path | The substrate for all of the below |
| **Immutable audit logging** | Inputs, outputs, model + prompt version, timestamps, scores, overrides | Logging/traceability (e.g. EU Art 12), incident forensics, accountability |
| **Eval + red-team harness in CI** | Accuracy, bias, robustness, jailbreak tests on every change | Accuracy/robustness (Art 15), NIST *Measure* |
| **Human-in-the-loop controls** | Surface confidence + explanations, override/stop control, anti-automation-bias | Human oversight (Art 14) |
| **Guardrails layer** | Input/output filtering, prompt-injection defense, PII redaction, policy checks | Robustness, safety, acceptable-use enforcement |
| **Provenance / watermarking** | Metadata + labels on generated media; "you're talking to AI" disclosure | Transparency (Art 50), content-labeling rules |
| **Data-governance plane** | Residency routing, PII handling, retention, lineage capture, consent state | Data-protection regimes (GDPR/DPDP), Art 10 data governance |
| **Access control + tenancy** | Who can call what, data isolation per customer | Security (Art 15), data-protection safeguards |
| **Model registry + versioning** | Track model/prompt versions and their eval results | Technical documentation (Art 11), change management |
| **Drift + incident monitoring** | Detect degradation, route serious incidents | Post-market monitoring (Art 72), incident reporting (Art 73) |

Build the gateway + logging + eval harness first — they're both good engineering *and* the load-bearing compliance pieces. Everything else bolts onto them.

---

## The provider ↔ deployer handoff (own vs. transfer)

A huge share of FDE governance work is **making the boundary explicit**. Obligations split, and unclear splits cause both compliance gaps and finger-pointing.

| You (provider / builder) typically own | The customer (deployer) typically owns |
|---|---|
| System design, risk management, technical file | Using it within the documented purpose |
| Declared accuracy, evals, robustness | Assigning competent human oversight |
| Instructions for use, transparency features | Monitoring operation, keeping logs |
| Conformity assessment, registration, CE marking | Input-data relevance, informing affected people |
| Post-market monitoring system | Fundamental-rights impact assessment (if applicable) |

Your customer-facing craft: **produce the instructions-for-use, train their humans on oversight, and stand up their monitoring + incident process** — so the handoff actually holds. A deployer who doesn't understand their obligations is a liability that traces back to your deployment.

---

## NIST AI RMF + ISO 42001 as your operating system

Master the *shape* of both; they're how you organize everything above.

**NIST AI RMF — four functions:**
- **Govern** — the culture, roles, and accountability wrapping everything (cross-cutting).
- **Map** — establish context and classify risks (this is your *discovery* stage).
- **Measure** — analyze, benchmark, and track risks (your *eval harness*).
- **Manage** — prioritize, respond, monitor (your *guardrails + production loop*).

**ISO/IEC 42001** — an auditable AI management system (like ISO 27001 but for AI): policies, roles, risk/impact assessment, lifecycle controls, continual improvement. It's the *certifiable* backbone that maps cleanly onto the EU Act's process requirements and reassures enterprise buyers.

Why they're your OS: hard legal requirements differ and shift by jurisdiction; these frameworks are stable, portable, and buildable. Anchor your architecture to them and you're most of the way to compliant *everywhere*, then localize the deltas.

---

## Frontier-model deployment layer (if applicable)

When you deploy frontier models into customer environments, add:
- **Enforcing the lab's acceptable-use policy** at the customer boundary — you're often the enforcement point.
- **Misuse / abuse monitoring** — detection and response for prohibited use.
- **Dual-use judgment** — recognizing capability that could cause serious harm (cyber, bio, etc.) and handling it appropriately.
- **Export-control / access awareness** — who is allowed to access what, across borders.
- **Model-level evals + safety cases** — beyond product evals, understanding the model's own risk profile and any responsible-scaling commitments attached to it.

---

## Red flags → escalate to counsel immediately

Don't improvise on these. Flag and stop:
- The use looks **prohibited** (social scoring, manipulation, untargeted biometric scraping, emotion inference in work/education).
- **High-stakes domain** (hiring, credit, healthcare, biometrics, law enforcement, migration) — high-risk obligations likely apply.
- **Children's data** or special-category data.
- **Cross-border transfer** of personal data out of a regulated region.
- **Automated decisions** with legal/significant effects on people.
- Anything where **"is this legal?"** is a real question rather than a rhetorical one.

Escalating early is a strength signal, not a weakness. The failure mode is building first and asking later.

---

## Anti-patterns (how FDEs get governance wrong)

- **Treating it as a final gate** instead of a discovery input → expensive rebuilds.
- **Giving legal advice** instead of raising flags → you're an engineer; scope and escalate.
- **Not documenting the negative findings** → "we assessed X and it's not high-risk because…" is itself required evidence. Absence of a paper trail is a risk.
- **Bolting governance onto a scattered codebase** → build the single service layer first, or you'll retrofit forever.
- **Fuzzy provider/deployer boundary** → make ownership explicit or inherit the gap.
- **Over-building minimal-risk products** → classification prevents wasted months as much as it prevents illegal products.

---

## One-page quick reference

**Mindset:** governance is a deal-accelerator you own, not a tax you pay.

**Carry:** 4 mental models (classify by use · provider vs deployer · data-gov is AI-gov · extraterritorial) → regime map (only what the customer touches) → NIST AI RMF + ISO 42001 (deeply) → frontier layer (if applicable).

**Use, by stage:** discovery = classify + flag · architecture = compliance-by-design · build = artifacts in the SDLC · handoff = make the deployer competent · production = keep the loop running.

**Build once:** unified model-call gateway + immutable logging + eval harness → most obligations satisfied as a side effect.

**Always:** classify first (use, not tech) · document negative findings · escalate the red flags · you translate and flag, counsel decides the law.

> The whole thing in a sentence: **be the person who can turn a compliance question into an architecture decision in real time** — that's what makes you trusted with the deals that matter, and it's a genuinely rare skill.
