# The Forward-Deployed Engineer Playbook

### The craft of deploying frontier AI into real customer environments

> The FDE is a fusion role: part engineer, part consultant, part product manager, part trusted advisor. You parachute into a customer's world, find the highest-value thing frontier AI can do for them, build it for real, prove it works, and expand from there. This playbook is the operating system for that job — the mindset, the lifecycle, the technical craft, and the customer-facing craft that engineers systematically underrate. The [Governance Playbook](./governance-playbook.md) is one module of this.

## Contents

This repo is a small stack, not a single doc — start here, then branch out:

| Doc | What it covers |
|---|---|
| **[README.md](./README.md)** (this file) | The FDE role, operating loop, deployment lifecycle, and technical/customer-facing craft |
| **[governance-playbook.md](./governance-playbook.md)** | Using AI & data governance as a deployment tool — discovery questions, architecture hooks, provider/deployer split |
| **[eu-ai-act.md](./eu-ai-act.md)** | Build-oriented, risk-tier-by-risk-tier guide to EU AI Act compliance |
| **[ai-and-data-governance.md](./ai-and-data-governance.md)** | Comparative regulatory map — US, UK, EU, China, South Korea, Japan, India |
| **[decision-driven-engineer.md](./decision-driven-engineer.md)** | Mental-model reference for DSA, systems design, the machine, memory, concurrency — and the FAANG interview meta-game |
| **[dsa-mastry-pattern.md](./dsa-mastry-pattern.md)** | ~22-pattern recognition index + tested templates, companion to the DSA part above |
| **[reference-architecture.md](./reference-architecture.md)** | Build spec for the instrumented service layer every other doc points to but never specced |
| **[eval-driven-development.md](./eval-driven-development.md)** | How to actually build eval-driven development — golden sets, metric choice, LLM-as-judge, CI wiring |
| **[discovery-toolkit.md](./discovery-toolkit.md)** | Fillable templates: use-case scoring, stakeholder map, governance checklist, definition of done |
| **[glossary.md](./glossary.md)** | One page for every acronym and term the stack assumes you already know |
| **[llm-slm.md](./llm-slm.md)** | LLM vs. SLM selection — when a small/local model beats a frontier API call |
| **[prep-plan-4-week.md](./prep-plan-4-week.md)** | A sequenced 4-week study plan tying every doc, note, and capstone below into a schedule |
| **[interview-drills.md](./interview-drills.md)** | Practice prompts with grading rubrics for each interview round |

### Sub-collections

The stack above is the core playbook. These are deeper, self-contained collections it draws on:

| Folder | What's in it |
|---|---|
| **[notes/](./notes/)** | 20 numbered field notes — SQL, data modeling, GCP infra, LLM eval, RAG, observability, interview prep. [Index](./notes/README.md) |
| **[case-studies/](./case-studies/)** | 9 worked FDE engagements across finance, healthcare, legal, energy, insurance, security, government, pharma. [Index](./case-studies/README.md) |
| **[security/](./security/)** | A 10-part, 90-volume cybersecurity handbook for regulated/security-sensitive deployments. [Index](./security/README.md) |
| **[databases/](./databases/)** | Relational, NoSQL, setup, and performance references for the data layer under any AI system. |
| **[fde-on-field/](./fde-on-field/)** | Field notes from real engagements. |
| **[coding/](./coding/)** | 14 runnable Python reference scripts (agent frameworks, RAG, EU AI Act/GDPR assessors, LLMOps metrics). See [pyproject.toml](./pyproject.toml) to install and `pytest` to run the test suite. |
| **[capstones/](./capstones/)** | 4 hands-on, gradable projects that turn this playbook's architecture docs into working code — see [prep-plan-4-week.md](./prep-plan-4-week.md). |

---

## What an FDE actually is (and isn't)

Your mandate: **own the end-to-end deployment of frontier models for strategic customers** — discovery, scoping, system design, build, rollout, production. Not a slice. The whole arc.

What makes it different from adjacent roles:

| Role | Optimizes for | The FDE difference |
|---|---|---|
| Software Engineer | Building the thing right | You also decide *what* to build and *whether it delivers value* |
| Solutions Architect | The design on paper | You actually build and ship it, in their environment |
| Sales Engineer | Winning the deal | Your job starts where theirs ends — you make the promise real |
| Consultant | The recommendation | You don't hand over a deck; you hand over working software |
| Product Manager | The roadmap | Your "roadmap" is one customer's reality, and you code it |

**The two currencies you spend and earn: speed and trust.** A working prototype in week one buys more trust than a flawless architecture in month three. Everything in this playbook ladders up to those two.

**The core truth of the role:** frontier models are astonishingly capable in a demo and stubbornly unreliable in production. Closing that gap — the *last mile* — is 90% of the job. Anyone can get a magic demo. You get it to work every time, on their data, inside their systems, for their users. That's the value you're paid for.

---

## The core operating loop

```
   LAND  ──►  FIND THE WEDGE  ──►  PROVE VALUE FAST  ──►  PRODUCTIONIZE  ──►  EXPAND
    │              │                     │                     │               │
 immerse in     pick the ONE       working demo on        reliable, eval'd,  next use case,
 their world    highest-value      their real data,       integrated, owned  more of the org
                use case           in days not months     by them            (land-and-expand)
                                                                                   │
                                                                                   └──► loop
```

The first deployment is a **beachhead**, not the war. You win a narrow, real, high-value use case, prove it, earn trust, and expand across the organization from that credibility. Trying to boil the ocean on day one is the classic way to fail.

---

## The mindset (the principles that actually matter)

- **Value-first, not tech-first.** Start from "what's the most valuable thing I could make work for this customer," not "what's the coolest thing this model can do." The coolest demo that solves nothing is worth nothing.
- **Speed is a feature.** In discovery and prototyping, a rough working thing today beats a polished thing next month. Momentum builds trust; trust unlocks everything else. (Then flip: in production, reliability beats speed.)
- **Trust is the substrate.** Every deal, every expansion, every hard conversation runs on the trust you've banked. You bank it by shipping, by being honest about limits, and by making their problem your problem.
- **Translate bidirectionally.** Carry the model's frontier capability *into* their problem, and carry their real-world constraints *back* to inform the product and the lab. You're the membrane between the frontier and the ground.
- **The last mile is the job.** Integration, evals, guardrails, data plumbing, change management — the unglamorous 80% — is where you earn your keep. The model is the easy part.
- **Eval-driven, always.** You cannot ship, trust, or improve what you cannot measure. Evals are your steering wheel, not a formality (deep-dive below).
- **Own the outcome, not the ticket.** You're accountable for the customer getting value, not for closing a task. If the blocker is organizational, political, or data-quality, that's your problem too.
- **Stay a guest, not a native.** Immerse deeply, but don't "go native" and lose the product/lab perspective. You're there to leave behind something that works without you.

---

## The deployment lifecycle (the heart of the craft)

Each stage is a different job with a different goal, a different trap, and a concrete artifact you leave behind.

### 1 · Discovery — understand their world
**Goal:** map the customer's reality and surface candidate use cases. **You do:** immerse — sit with end users, watch the actual workflow, read their systems, map stakeholders. Ask more than you tell. **The trap:** pitching solutions before you understand the problem; falling for the loudest stakeholder's pet idea. **Artifact:** a ranked list of use cases scored by value × feasibility, plus a stakeholder map. *(Fillable templates: [discovery-toolkit.md](./discovery-toolkit.md).)*

### 2 · Scoping — pick the wedge & define success
**Goal:** choose the ONE highest-leverage use case and define what "it works" means *before* building. **You do:** pick for value × feasibility × visibility; define measurable success criteria; run the governance discovery questions; de-risk the biggest unknown first. **The trap:** scoping too big, or scoping something demo-able but not productionizable. **Artifact:** a crisp scope with success metrics, a risk/governance flag list, and a "definition of done."

### 3 · Prototype — prove value fast
**Goal:** a working thing on their *real* data, fast — days, not months. **You do:** build the thinnest slice that proves the value; use their actual data (a demo on toy data proves nothing); show it early and often. **The trap:** the demo that dazzles but can't survive contact with production — no evals, no guardrails, hand-picked inputs. Be honest that it's a prototype. **Artifact:** a working prototype + a clear-eyed read on the demo-to-production gap.

### 4 · Productionize — build for real
**Goal:** turn the prototype into something reliable, integrated, and owned. **You do:** stand up the real architecture (the instrumented service layer), build the eval suite, add guardrails, integrate with their systems, handle the data plumbing, harden security. **The trap:** under-engineering (ships, then breaks and burns trust) or over-engineering (never ships). Right-size to the actual reliability need. **Artifact:** production system + eval harness + monitoring + docs.

### 5 · Rollout — deploy & drive adoption
**Goal:** get real users using it and getting value. **You do:** change management — train users, design the human-in-the-loop workflow, manage expectations, gather feedback fast, iterate. **The trap:** treating "it's deployed" as "we're done." A technically perfect tool nobody uses is a failure. Adoption is the metric. **Artifact:** trained users, a feedback loop, adoption signal.

### 6 · Operate & hand off — make it run without you
**Goal:** reliable production operation the customer can own. **You do:** monitoring, drift/incident response, runbooks, knowledge transfer so it doesn't depend on you. **The trap:** hero mode — becoming the single point of failure. If it breaks when you leave, you didn't finish. **Artifact:** runbooks, monitoring, a customer team that can operate it.

### 7 · Expand — land-and-expand
**Goal:** parlay one proven win into the next. **You do:** use the earned trust and the reference success to find the next high-value use case, ideally with the same infrastructure you already built. **The trap:** letting the relationship go cold after the first win, or expanding into low-value work just because it's easy. **Artifact:** the next scoped use case, and a reusable platform underneath.

---

## The technical craft

- **LLM system architecture.** Route every model call through **one instrumented service layer** — the same decision that gives you observability, cost control, evals, guardrails, and governance compliance for free. This is the single highest-leverage architectural choice you make; build it first and everything else bolts on. *(Build spec: [reference-architecture.md](./reference-architecture.md).)*
- **Eval-driven development — your superpower.** This is what separates FDEs from prompt-tinkerers. Before optimizing, build an eval set from real customer examples with clear success criteria. Every prompt change, model swap, and guardrail is measured against it. Evals turn "it feels better" into "accuracy went 82% → 91%," which is what customers and your own iteration actually need. You cannot productionize frontier models without them. *(How to build one: [eval-driven-development.md](./eval-driven-development.md).)*
- **Closing the demo-to-production gap.** The prototype works on 10 hand-picked inputs; production faces 10,000 messy real ones. Guardrails (input/output validation, prompt-injection defense, PII handling, fallbacks), retries and graceful degradation, and relentless evals against real-world edge cases are how you cross it.
- **Integration & data plumbing — the unglamorous 80%.** Getting the model to the answer is easy; getting the *right context in* and the *answer into their systems* is the work. Data access, retrieval, auth, APIs, their legacy stack. Respect this; it's where most deployments actually stall.
- **Observability & cost.** Instrument latency, quality, and spend from day one. Frontier-model economics can make or break a use case; know your per-request cost and where it goes.

---

## The customer-facing craft (the half engineers underrate)

This is often what actually determines success, and it's where technically strong FDEs most commonly fall short.

- **Map the stakeholders.** Know your *champion* (wants you to win), your *economic buyer* (controls budget), your *blockers* (security, legal, skeptical end users), and your *end users* (whose adoption is the real test). Different people need different things from you.
- **Discovery by listening.** The best FDEs ask sharp questions and shut up. You're diagnosing, not presenting. The problem the customer *states* is rarely the highest-value one you'll find.
- **Demo like it matters.** A demo is storytelling: show *their* problem being solved with *their* data. Make them feel the value, don't recite features.
- **Manage expectations ruthlessly.** The gap between demo-magic and production-reliability will bite you if the customer doesn't understand it. Set honest expectations early — it's counterintuitively *trust-building*, and it's the opposite of what over-eager teams do.
- **Build credibility, then spend it.** Trust compounds: small delivered promises earn the right to make bigger ones. Protect it — one overpromise-and-miss costs more than several wins earned.
- **Learn to say no / re-scope.** Part of owning the outcome is steering the customer away from low-value or infeasible asks. "That's possible, but here's the higher-value thing we should do first" is a senior move.

---

## Communication

- **Translate up** (executives): value, risk, ROI, timeline — in their language, not yours. No model internals; business outcomes.
- **Translate down** (end users): how to use it, what to trust it for, where the limits are. Adoption depends on this.
- **Write clearly and proactively.** Status that surfaces risk early, decisions documented, expectations in writing. In a solo-deployed role, your written comms *are* your visibility.
- **Bring the ground truth back** to the lab/product team — the real-world friction, capability gaps, and edge cases you see are gold for the product. You're the field's eyes.

---

## Failure modes & anti-patterns

- **Building the wrong thing beautifully.** Flawless execution of a low-value use case. Prevention: value-first scoping, real success metrics.
- **The demo that never productionizes.** Dazzle, then stall at the last mile. Prevention: use real data early, be honest about the gap, plan productionization from the start.
- **Wrong-sized engineering.** Over-building early (never ships) or under-building late (ships, breaks, burns trust). Prevention: match rigor to the phase and the reliability need.
- **Going native.** Absorbing the customer's worldview so completely you lose the product/lab perspective and build a bespoke snowflake. Prevention: stay a guest; build to leave.
- **Hero mode / bus factor.** Becoming indispensable and undocumented. Prevention: runbooks, knowledge transfer, hand-off from day one.
- **Ignoring change management.** A great tool nobody adopts. Prevention: treat adoption as *the* metric, invest in training and workflow design.
- **Skipping evals.** Iterating on vibes. Prevention: evals before optimization, always.

---

## What success actually looks like (metrics)

Not lines of code. Not model cleverness. The real scoreboard:
- **Value delivered** — measurable business impact for the customer.
- **In production and adopted** — real users, real workflow, not a pilot gathering dust.
- **Runs without you** — the customer can operate and trust it.
- **Expansion** — the first win became the second, third, fourth.
- **Trust** — the customer brings you their next hard problem first.

---

## Mental models (quick hits)

- **The wedge** — win one narrow, real, high-value use case; expand from there.
- **Land-and-expand** — the first deployment is a beachhead, not the whole battle.
- **The last mile** — the model is 10% of the work; reliability, integration, and adoption are the 90%.
- **Demo-to-prod gap** — magic on 10 inputs ≠ reliable on 10,000; evals and guardrails cross it.
- **Two currencies** — everything trades in speed and trust.
- **Trust compounds** — small kept promises earn bigger ones; protect the balance.
- **Bidirectional translation** — capability in, constraints out; you're the membrane.

---

## How this fits your library

You now have a coherent stack for the role:

- **This playbook** — the craft of the FDE role end to end.
- **[The Governance Playbook](./governance-playbook.md)** — the governance/compliance module of this role.
- **[EU AI Act Implementation guide](./eu-ai-act.md)** — the deep reference behind the compliance stage.
- **[AI & Data Governance: US · UK · EU · Asia](./ai-and-data-governance.md)** — the comparative map for when a customer isn't EU-first.
- **[The Decision-Driven Engineer](./decision-driven-engineer.md)** + **[DSA Pattern Library](./dsa-mastry-pattern.md)** — the technical foundation the "productionize" stage rests on.
- **[The Instrumented Service Layer](./reference-architecture.md)** — the build spec for the architecture named throughout this stack.
- **[Eval-Driven Development](./eval-driven-development.md)** — how to build the "superpower" this stack keeps naming.
- **[The Discovery Toolkit](./discovery-toolkit.md)** — fillable templates for the discovery/scoping stage.
- **[Glossary](./glossary.md)** — the on-ramp for every acronym the other docs assume.
- **[The 4-Week Prep Plan](./prep-plan-4-week.md)** — sequences everything above (plus `notes/`, `case-studies/`, and the `capstones/`) into a study schedule.
- **[Interview Drills](./interview-drills.md)** — gradable practice prompts for each round of the loop `notes/18` describes.
- **[The Capstones](./capstones/)** — the hands-on layer: build the RAG system, the governance assessor, debug the instrumented service layer, and diagnose a full-stack incident across all 5 observability layers, don't just read about them.

---

## One-page quick reference

**The role:** own frontier-AI deployments end to end for strategic customers. Engineer + consultant + product + advisor.

**The loop:** land → find the wedge → prove value fast → productionize → expand.

**The two currencies:** speed and trust. Bank them by shipping and being honest.

**The core truth:** the model is 10% of the job; the last mile — reliability, integration, evals, adoption — is 90%.

**The lifecycle:** discovery (listen) · scope (pick the wedge, define success) · prototype (real data, fast) · productionize (service layer + evals + guardrails) · rollout (change management) · operate (hand off) · expand (land-and-expand).

**Build once:** the instrumented model-call service layer → observability, cost, evals, guardrails, and governance for free.

**Underrated half:** stakeholder mapping, expectation management, demo storytelling, saying no, trust compounding.

**Success =** value delivered, in production, adopted, running without you, expanding.

> The whole thing in a sentence: **find the most valuable real problem, make frontier AI reliably solve it in their world, and earn the trust to do it again — bigger.**
