# The Forward Deployed Engineer In the Field
### An End-to-End Account of a 12-Week AI Deployment Engagement

---

**Client:** Meridian FinTech AG *(Fictitious · BaFin-Regulated · Frankfurt)*
**Engagement:** 12 Weeks · AI-Powered Customer Support System · Prototype → Production
**Outcome:** Multi-agent LangGraph system · 40% ticket deflection · Zero PII events · BaFin-compliant

*All client details are fictitious and used for illustration purposes only.*

---

## Key Metrics

| 12 | 72 hrs | 40% | 0 | 4 |
|---|---|---|---|---|
| Engagement Weeks | First Prototype | Ticket Deflection | PII Leakage Events | Engineers Upskilled |

---

## The Cast of Characters

| Name | Role | Stake | Communication Frequency |
|---|---|---|---|
| Klaus Richter | CTO, Meridian FinTech AG | Executive sponsor — budget, risk appetite, strategic direction | Weekly steering call · Ad-hoc on blockers |
| Sabine Maier | Head of Customer Operations | Business owner — ticket SLA, agent productivity, escalation policies | Daily standup · Weekly demo |
| Marcus Chen | Head of Compliance & Data Privacy | Risk gatekeeper — BaFin obligations, GDPR, PII data flows | Bi-weekly + milestone reviews |
| Priya Sharma | Lead Engineer, Platform Team | Technical counterpart — codebase access, infrastructure, CI/CD | Daily pairing / async Slack |
| Tom Fischer | Senior Engineer, Platform Team | Integration owner — CRM, ticketing system (Zendesk), auth | Daily standup · Code review |
| Anika Bauer | Product Manager, Support Experience | Requirements owner — user stories, acceptance criteria | Daily standup · Weekly demo |
| Erik Lund | DevOps / SRE Lead | Infrastructure owner — Kubernetes, secrets, monitoring, go-live | Weekly + go-live sprint |

---

## 00 — Executive Summary

This document provides a granular account of a 12-week Forward Deployed Engineer (FDE) engagement at Meridian FinTech AG — a fictitious BaFin-regulated digital bank in Frankfurt. It is written to serve two audiences: engineers considering the FDE career path who want to understand what the role actually involves day-to-day, and clients evaluating whether to engage an FDE and what to expect during such an engagement.

The FDE role sits at the intersection of principal engineering, technical consulting, and customer success. Unlike a traditional consultant who recommends and leaves, an FDE embeds directly in the client environment, builds working software alongside the client team, and owns outcomes — not just deliverables. Unlike a staff engineer, the FDE has no permanent home team; their craft is applied across organisations, problem types, and technology stacks in rapid succession.

The core FDE skill is not any single technology. It is the ability to take an ambiguous, high-stakes business problem, reduce it to a buildable scope in 48 hours, produce a working prototype that changes the client's perception of what is possible, and then carry that prototype to production-grade quality while transferring enough knowledge that the client's team can own it after the FDE leaves.

This case study traces the engagement from first contact through final handoff, covering: pre-engagement preparation; discovery workshop format and outputs; architecture decision-making and trade-off analysis; the daily rhythm of build-test-demo sprint cycles; production hardening for a BaFin-regulated environment; go-live operations; and the knowledge transfer and retrospective that close the engagement.

---

## 01 — Phase 0: Pre-Engagement Preparation
*Days −5 to 0 · Before walking through the door*

The worst thing an FDE can do is walk into a client site cold. Every hour of preparation before the engagement starts is worth three hours during it. The goal of pre-engagement is to arrive with hypotheses — not answers, but structured questions — and enough context to ask the right ones within the first hour.

### Days −5 to −3: Intelligence Gathering

> **FDE Rule #1:** Never ask a client a question you could have answered with 30 minutes of research. Arriving prepared signals respect for the client's time and immediately differentiates you from a generic consultant.

- **Public technical footprint review.** Check engineering blog, open-source GitHub repos, job postings (reveals current stack, skill gaps, and pain points), LinkedIn profiles of key engineers. Meridian's job postings showed: 3 open "senior backend" roles (understaffed), Python/FastAPI listed, AWS + Terraform. They were hiring for what they didn't have.
- **Regulatory landscape audit.** Meridian is BaFin-regulated (German banking supervisor). Pull BaFin's current AI guidance documents, DORA obligations active from Jan 2025, and any Merkblatt publications on AI in financial services. Note: any AI system touching customer data in a FinTech requires a Data Protection Impact Assessment (DPIA) under GDPR Art. 35.
- **Competitive context.** Research what similar FinTechs (N26, Trade Republic, Solarisbank) are doing with AI support automation. Build a one-page competitive landscape. This will be used in the discovery workshop to calibrate ambition.
- **Technology stack hypothesis.** Based on job postings and blog posts, hypothesise the likely stack. Meridian: AWS, Kubernetes, Python FastAPI, PostgreSQL, Kafka, Zendesk. Prepare integration research for each component.
- **Contracting review.** Re-read the statement of work (SOW) carefully. Note: 12 weeks, deliverable is a 'proof of concept to production AI support system.' Identify gaps — 'proof of concept to production' is ambiguous. Will need to align on definition of 'production' in Week 1.

### Days −2 to −1: Preparation Artifacts

| Artifact | Purpose | Content | Used When |
|---|---|---|---|
| Problem Hypothesis Canvas | Force-ranks the client's likely problems before validation | 3 problem hypotheses with supporting evidence + what would falsify each | Day 1 discovery workshop |
| Technology Risk Matrix | Pre-identifies integration risks before seeing the codebase | Likely stack, known failure modes, questions to ask CTO and engineers | Day 1 technical deep-dive |
| Stakeholder Power/Interest Map | Plans communication strategy per stakeholder | 2×2 grid: power vs. interest; communication cadence per quadrant | Throughout engagement |
| Definition of Done Checklist | Pre-aligns on what 'production' means before the client defines it differently in Week 10 | 15-item checklist: monitoring, security, runbook, load test, compliance sign-off, etc. | Week 1 kickoff, Week 10 go-live gate |
| First 72-Hour Sprint Plan | Pre-defines the prototype scope to accelerate the first sprint after discovery | Provisional architecture + stack choices + first MVP feature set | Revised after Day 2 discovery workshop |

### Day 0: Arrival Protocol

1. Get repository access, Slack invite, Jira access, and AWS console read-only access **before** the kickoff meeting. If these are not ready, escalate to CTO immediately — access delays are the #1 killer of FDE productivity in Week 1.
2. Walk the support floor for 30 minutes before the kickoff meeting. Listen to a live support call. Read 20 recent support tickets. This is worth more than any stakeholder briefing — you will understand the problem viscerally, not abstractly.
3. Run `git log --oneline -50` on the main backend repository. Read the last 10 pull request descriptions. In 15 minutes you understand: code quality, review culture, deployment frequency, and what the team has been working on.
4. Identify the most senior engineer on the platform team (Priya Sharma) and the most sceptical stakeholder (Marcus Chen, Compliance). Both need to be addressed directly in the kickoff.
5. Set up personal development environment: repo cloned, Python venv configured, AWS credentials working, Zendesk API test call successful. Do not wait for someone to set this up for you.

> **FDE Mindset at Day 0:** You are a guest in someone else's organisation. The client's engineers have been here for years. They know more about the business context than you ever will. Your value is not knowing more than them — it is bringing pattern recognition from 15+ similar engagements that they do not have access to, and the ability to make consequential technical decisions quickly under uncertainty.

---

## 02 — Phase 1: Discovery
*Weeks 1–2 · Understanding before building*

### The Discovery Workshop — Day 1 (Full Day)

The discovery workshop is the most important event of the engagement. Done well, it produces a shared, written understanding of the problem that every stakeholder — technical and business — agrees on. Done badly, it produces a nice presentation that gets ignored when the pressure of Week 4 arrives.

The FDE **runs** the discovery workshop, not facilitates it. There is a difference: a facilitator helps the group arrive at their own conclusions. The FDE is there to arrive at the *right* conclusion — which means actively challenging assumptions, surfacing hidden constraints, and proposing concrete options rather than open-ended questions.

| Time | Activity | FDE Goal | Output |
|---|---|---|---|
| 09:00–09:30 | Kickoff: FDE introduces self, engagement context, and today's agenda | Set expectations: we are here to define a buildable problem, not to brainstorm | Aligned agenda |
| 09:30–10:30 | Problem Mapping: Each stakeholder describes the problem from their perspective (15 min each) | Surface conflicting definitions early. Note: Operations wants speed; Compliance wants control; CTO wants scalability. | Written problem statements per stakeholder |
| 10:30–11:00 | Walk the floor: FDE leads group in reviewing 30 real support tickets live on screen | Make the abstract concrete. Forces stakeholders to agree on what 'a support ticket' actually is. | Ticket taxonomy: 5 categories, % volume each |
| 11:00–12:00 | Constraint mapping: What cannot change? (Regulatory, technical, organisational) | Identify the real boundaries before proposing solutions. This session has killed 3 naive AI proposals. | Constraint register (12 items at Meridian) |
| 12:00–13:00 | Lunch — informal. FDE eats with engineers, not executives. | Build trust with the delivery team. Learn what they are afraid to say in the meeting. | Informal intelligence |
| 13:00–14:30 | Solution Exploration: FDE presents 3 concrete architecture options with trade-offs | Do not present one option. Three options forces a choice rather than a refinement loop. | Shortlist to 1–2 options |
| 14:30–15:30 | Success Metrics Workshop: Define what 'success' means in numbers | Force specificity. 'Better support' is not a metric. '40% reduction in SLA breach rate' is. | 3 primary KPIs with current baselines and targets |
| 15:30–16:00 | Risk Workshop: What could go wrong? What are the 3 biggest risks? | Surface the Compliance team's concerns before they become blockers in Week 8. | Risk register with mitigation owners |
| 16:00–16:30 | Wrap-up: FDE reads back Problem Statement, Success Metrics, Constraints, and Next Steps | Test for consensus. If anyone disagrees, surface it now, not in Week 6. | Signed-off Problem Statement document |

> **Meridian Discovery Finding #1 (Unexpected):** The compliance team had already received informal guidance from BaFin that any AI system making autonomous decisions on customer complaints (even routing decisions) would require a human-in-the-loop control. This was not in the initial brief. If discovered in Week 8 instead of Day 1, it would have required a full architectural rework. Discovery workshops exist to surface facts like this early.

### Discovery Output: The Problem Statement

Every FDE engagement should produce a single, written Problem Statement that fits on one page. This document becomes the north star for all architectural decisions. When trade-offs arise in Week 6, the question is always: *which option better serves the Problem Statement?*

---

**MERIDIAN FINTECH AG — PROBLEM STATEMENT** *(Agreed: Week 1, Day 2)*

**Problem:** Meridian's customer support team of 42 agents handles ~3,200 tickets/week across email, chat, and phone. 40% of tickets breach the 24-hour SLA. 65% of tickets are routine (account queries, card limits, transaction disputes) that require no specialist knowledge. Agents spend ~60% of their time on these routine tickets, leaving insufficient capacity for complex cases where human judgement is genuinely required.

**Goal:** Deploy an AI system that handles routine tickets autonomously (with human oversight as required by BaFin guidance) and triages complex tickets to the correct specialist team — reducing SLA breach rate from 40% to <15% and freeing agent capacity for high-value interactions.

**Success Metrics:** (1) SLA breach rate < 15% · (2) AI deflection rate ≥ 35% · (3) Agent satisfaction score ≥ 4.0/5 · (4) Zero BaFin compliance incidents

**Non-Negotiable Constraints:** HITL required for autonomous decisions (BaFin) · All PII redacted before LLM processing (GDPR) · No customer PII sent to US-based LLM providers without data processing agreement · Full audit trail of all AI decisions for BaFin examination

---

### Weeks 1–2: Stakeholder Interviews & Technical Landscape

| Stakeholder | Duration | Key Questions Asked | Critical Finding |
|---|---|---|---|
| Klaus Richter (CTO) | 60 min | What does success look like in 12 months? What has been tried before and failed? | A previous chatbot project failed 18 months ago due to hallucinations on financial advice queries. The team is sceptical. Need visible guardrails from Day 1. |
| Sabine Maier (Head of Ops) | 90 min + ticket review | Walk me through your best agent's workflow. What decisions do they make that AI cannot? | The real bottleneck is not answering routine queries — it is routing: wrong-team tickets cause 60% of SLA breaches. Routing accuracy is the killer feature. |
| Marcus Chen (Compliance) | 120 min | What AI-related guidance have you received from BaFin? What would constitute a compliance incident? | BaFin has indicated informally that decisions affecting customer accounts require a human-in-the-loop. All AI decisions need to be logged with reasoning for potential examination. |
| Priya Sharma (Lead Eng) | 3 hrs (pairing) | Show me the ticket lifecycle in code. Where are the integration points? What keeps you up at night? | Zendesk webhook is reliable but the internal CRM API has 15% timeout rate under load. No vector extension in PostgreSQL. Strong CI/CD but no LLM eval tooling. |
| Tom Fischer (Eng) | 2 hrs (pairing) | Talk me through the Zendesk integration. How does auth work? What are the rate limits? | Zendesk API is rate-limited to 700 requests/min. The internal CRM API is the real risk: 15% timeout rate at load. |
| Support Agents (×3) | 30 min each | What information do you look up most often? What would you never trust a computer to decide? | Agents look up account balance, transaction history, and card limit in CRM for 70% of tickets. Trust is the product risk, not the technical risk. |

### The Technical Landscape Assessment

What the FDE found in the Meridian codebase after 3 hours of reading:

- 47 Python microservices, 12 actively maintained
- No vector database anywhere in the stack
- Zendesk webhooks processed synchronously (risk: slow AI response blocks webhook acknowledgement → Zendesk retry storm)
- CRM API client has no circuit breaker (explains the 15% timeout propagation)
- No existing LLM code whatsoever — greenfield for AI, but also means no team experience with LLM failure modes
- Strong test culture: 78% coverage on core services, good GitHub Actions CI
- AWS ECS Fargate — easy to deploy new services without infra changes

---

## 03 — Phase 2: Architecture Decisions
*Weeks 2–3 · Making the hard choices before writing a line of production code*

The most consequential work of any FDE engagement happens before the first sprint. Architecture decisions made under deadline pressure in Week 8 are almost always the wrong ones. The FDE's job is to make the hard choices early, document them explicitly, and get stakeholder buy-in before building begins.

At Meridian, the FDE produced five Architecture Decision Records (ADRs) over 4 days. An ADR records: a significant architectural choice, the options considered, the trade-offs evaluated, and the rationale for the decision made — especially what was explicitly **not** done and why. This prevents the 'why didn't we do X?' conversations in Week 9.

### ADR-001: LLM Provider Selection

| | |
|---|---|
| **Decision Driver #1** | BaFin/GDPR constraint: no EU customer PII can be sent to a US-based service without a valid Data Processing Agreement (DPA) and Standard Contractual Clauses (SCCs) |
| **Decision Driver #2** | Compliance team requires full data residency in EU. Azure OpenAI provides EU data residency with a signed DPA available. |
| **Option A: Azure OpenAI (EU region)** | ✅ **Chosen.** EU data residency, Microsoft DPA available, same GPT-4 model quality. Slightly higher latency (+80ms) but within SLA. Already in Microsoft EA that Meridian holds. |
| **Option B: OpenAI Direct** | ❌ Rejected. US data residency. Would require 6-week legal review for DPA + SCCs. Not viable within 12-week engagement. |
| **Option C: Self-hosted Llama 3 on AWS** | ❌ Rejected for MVP. Would require GPU cluster procurement (4–6 week lead time), MLOps tooling, and quality evaluation. Recommended as future Phase 2 cost-optimisation. |
| **Decision** | Azure OpenAI (GPT-4-turbo) in West Europe region with Microsoft BAA/DPA signed before first API call. Review at 6 months for self-hosted cost optimisation. |

### ADR-002: Agent Framework

| | |
|---|---|
| **Decision Driver** | The system needs a stateful, multi-step agent that can pause for human review (HITL required by BaFin), resume after agent action, and maintain conversation context across multiple turns. |
| **Option A: LangChain (standard chain)** | ❌ Rejected. LangChain chains are stateless — no native HITL pause/resume. Would require significant custom state management code that replicates what LangGraph provides natively. |
| **Option B: LangGraph StateGraph** | ✅ **Chosen.** Native HITL `interrupt()` support. TypedDict state schema prevents data corruption between nodes. MemorySaver for conversation persistence. Conditional edges enforce routing logic. BaFin compliance requirement for human-in-the-loop is a first-class LangGraph feature. |
| **Option C: Custom orchestration** | ❌ Rejected. Estimated 3× development time vs. LangGraph for the same capabilities. The engagement has 12 weeks — not the time to build a framework. |
| **Decision** | LangGraph 0.1.x with typed Pydantic v2 state schema. HITL interrupt pattern used for any autonomous decision that affects a customer account. |

### ADR-003: PII Handling Architecture

| | |
|---|---|
| **Decision Driver** | GDPR Article 25 (privacy by design) + BaFin examination requirement: customer PII must never be sent to LLM providers. |
| **Approach** | Microsoft Presidio PII detection pipeline runs on all ticket content before any LLM call. Identified entities (names, IBAN, email, phone, German Personalausweis numbers) are replaced with typed placeholders: `[PERSON_1]`, `[IBAN_1]`, etc. Post-LLM output runs a second Presidio pass to catch any PII that may have leaked through. |
| **Custom Recognisers** | Meridian's CRM uses internal account numbers in format `MFT-XXXXXXXX`. Added custom Presidio recogniser with regex pattern. Also German tax IDs — not in default Presidio, added via custom `EntityRecogniser`. |
| **Audit Log** | Every Presidio redaction event logged with: timestamp, ticket ID, entity type, confidence score. Stored separately from ticket content with restricted access. |
| **Decision** | Presidio dual-pass (pre + post LLM) with custom FinTech recognisers. All redactions logged to immutable audit table. PII never leaves EU. Monthly review of redaction false-positive rate — threshold: < 0.5%. |

### ADR-004: Routing Architecture

| | |
|---|---|
| **Problem** | The discovery finding was that routing (wrong-team assignment) causes 60% of SLA breaches. Need routing system with > 92% accuracy across 7 routing destinations. |
| **Option A: Fine-tuned classification model** | ❌ Rejected. 6-week training pipeline setup + 5,000+ labelled tickets required. Too slow for this engagement. |
| **Option B: Pure RAG** | ❌ Insufficient alone. Tested on 500 historical tickets: 84% routing accuracy, short of 92% target due to ambiguous tickets. |
| **Option C: Hybrid — GPT-4 classification with RAG-grounded examples** | ✅ **Chosen.** GPT-4 with 5 similar historical tickets as examples in context (few-shot RAG) achieves 93.5% routing accuracy on test set. Understandable reasoning logged. Explainable to BaFin. No training pipeline required. |
| **Decision** | Hybrid: Chroma vector store of 50k historical tickets → retrieve top-5 similar → GPT-4 few-shot classification with chain-of-thought reasoning → confidence threshold → HITL if confidence < 0.85. Routing decisions logged with full reasoning chain. |

### System Architecture at Week 2

```
Zendesk Webhook
  → FastAPI Async Receiver
  → Presidio PII Redaction
  → LangGraph StateGraph Orchestrator
      → [RoutingAgent]: Chroma RAG (50k tickets) + GPT-4 few-shot
          → routing decision (HITL if confidence < 0.85)
      → [ResolutionAgent]: GPT-4 + Policy RAG (internal FAQ/policy docs)
          → draft response
      → [HumanReviewNode]: LangGraph interrupt()
          → human agent approves/edits response
      → [ResponseDispatch]: Approved response posted back to Zendesk

All LLM calls     → Azure OpenAI West Europe
All PII           → stripped pre-LLM, checked post-LLM via Presidio
All decisions     → audit log (PostgreSQL immutable table)
All traces        → LangSmith project (sampled 20% routine, 100% HITL events)
```

---

## 04 — Phase 3: Build Sprints
*Weeks 3–8 · The daily craft of FDE delivery*

### The Daily Rhythm

| Time | Activity | Notes |
|---|---|---|
| 08:00–08:30 | Review overnight GitHub notifications, LangSmith traces, any errors in staging | Do this before the standup so you can report status, not discover it publicly |
| 08:30–09:00 | Daily standup (15 min max) with Priya, Tom, Anika | FDE-run standup: Yesterday / Today / Blockers. No war stories. No architecture discussions. |
| 09:00–12:00 | Deep build work — coding, testing, LangSmith trace analysis | Protect this block aggressively. No meetings. Slack notifications off. |
| 12:00–13:00 | Lunch — usually with a different team member each day | Relationship maintenance. Informal intelligence. Learn what is worrying people before it becomes a formal issue. |
| 13:00–14:30 | Pairing session with client engineer (rotates: Priya or Tom) | Knowledge transfer is built into every afternoon. The FDE should never be the only person who understands any part of the system. |
| 14:30–15:30 | Stakeholder async communication: Slack updates to Sabine and Klaus, PR reviews | Keep stakeholders informed without meetings. A 3-sentence Slack message at 15:00 prevents a 30-minute status call request at 09:00. |
| 15:30–16:30 | Documentation sprint: ADRs, runbook updates, decision logs | Write the documentation the same day as the decision. Never catch up on docs in the last week. |
| 16:30–17:30 | Code review of Tom's PRs + preparation for tomorrow's build block | Review PRs within 24 hours — this is a commitment. Unreviewed PRs block the client team's progress. |
| 17:30–18:00 | EOD: update personal notes, blockers list, anything to escalate | The FDE writes a private daily log of decisions made and why. This is the raw material for the retrospective and the next ADR. |

### The Weekly Demo — Non-Negotiable

Every Friday at 14:00, the FDE presents a working demo of whatever was built that week. This is not optional and is not cancelled if the week went badly. If the week went badly, you demo what went wrong and what was learned from it. The weekly demo serves multiple critical functions:

- **Maintains client trust.** The client can see progress with their own eyes. Trust built on visible working software is far more durable than trust built on status presentations.
- **Forces the team to finish things.** 'Demo-able by Friday' is a forcing function that prevents perpetual work-in-progress. If it cannot be demoed, it is not done.
- **Surfaces requirement mismatches early.** At Meridian, Week 4's demo revealed that Sabine Maier's definition of 'routine ticket' excluded all transaction dispute tickets. This changed the routing model scope. Discovering this in Week 4 rather than Week 10 saved an estimated 3 weeks of rework.
- **Creates a shared narrative.** The demo series becomes the story of the engagement. By Week 10, stakeholders can narrate the journey from 'AI didn't exist here' to 'AI handles 40% of our tickets.'

### Week 3: The First Prototype (72 Hours)

The first prototype is the most important deliverable of the engagement. It does not need to be good. It needs to be real — a working system that the client can interact with, query, and break. The 72-hour target is deliberate: it forces the FDE to make scope decisions under time pressure, which produces a simple system that actually teaches you something about the problem.

**Monday (Day 1):**
- 08:00–10:00: Set up LangGraph project structure, FastAPI skeleton, Azure OpenAI connection. Verify endpoint returning responses. Commit baseline to GitHub.
- 10:00–12:00: Write Presidio pipeline. Test against 50 real anonymised tickets. Discovered: 3 false positives (company name 'Meridian' flagged as person name). Added to blocklist. Custom `MFT-XXXXXXXX` account number recogniser working.
- 13:00–15:00: Build simplest possible RoutingAgent — single GPT-4 call with 5 hardcoded example tickets. No RAG yet. Validating that the routing prompt works on real data.
- 15:00–16:30: Pair with Tom on Zendesk webhook setup. Discover the synchronous processing risk — if LangGraph takes > 20 seconds, Zendesk will retry the webhook (creating duplicate tickets). Decision: decouple via a Redis queue. 2-hour scope increase, but critical correctness fix.
- 16:30–18:00: Implement Redis queue decoupling. Webhook handler acks immediately, pushes to queue, LangGraph worker consumes asynchronously. ADR-005 written.

**Tuesday (Day 2):**
- 08:00–10:00: Ingest 50,000 historical Meridian tickets into Chroma vector store using ada-002 embeddings. Cost: €4.20. Verify retrieval quality on 10 test queries.
- 10:00–12:00: Replace hardcoded examples with RAG retrieval. Test hybrid routing on 100 labelled test tickets. Initial accuracy: 88.4%. Added chain-of-thought prompting. Accuracy improved to 91.9%.
- 13:00–15:00: Build LangGraph `interrupt()` for HITL. When routing confidence < 0.85, the graph pauses and sends a review request to the human agent dashboard. Human approves/overrides → graph resumes.
- 15:00–16:30: Build the basic ResolutionAgent — generates a draft response using GPT-4 with Meridian's FAQ document indexed in Chroma. Initial quality: accurate but too formal. Tone prompt added.
- 16:30–18:00: Wire everything together. End-to-end test: real Meridian ticket → Presidio → LangGraph → routing decision → resolution draft → (simulated) human approval → Zendesk API response post. First end-to-end success at 17:52.

**Wednesday (Day 3):**
- 08:00–10:00: Bug fixing from overnight test run (50 tickets through the pipeline). 3 bugs found: (1) Chroma throws on empty ticket body, (2) Azure OpenAI returns 429 rate limit at 50 concurrent requests — add exponential backoff, (3) Presidio strips postal codes as PII — add to allowlist.
- 10:00–12:00: Add LangSmith tracing. Configure project `meridian-support-agent`. Every ticket flow now has a full trace. First LangSmith dashboard built: cost/ticket = €0.023 average.
- 12:00–14:00: Prepare the Friday demo. Write 5 demo scenarios with real (anonymised) tickets. Prepare 'what went wrong' section — honest about the scope changes (Redis queue) and the accuracy result (91.9%, target is 92%).

> **Week 3 Friday Demo Result:** Sabine Maier, after seeing the prototype process a live ticket from her queue in 8 seconds and generate a routing decision with a plain-English explanation, said: *'I didn't think this was possible without a year of data science work.'* This is the moment the engagement changed from a vendor relationship to a partnership.

### Weeks 4–6: Build Sprints — Scope Evolution

| Week | Primary Build Focus | Scope Decision Made | Stakeholder Impact |
|---|---|---|---|
| Week 4 | Routing accuracy improvement + Zendesk live integration | Sabine Maier revealed transaction dispute tickets should stay with specialist team, not be AI-routed. Removed from routing scope. Routing accuracy improved to 94.2% on narrower scope. | Reduced deflection target from 40% to 35% — but quality increase justified the scope reduction. |
| Week 5 | Resolution quality + Policy RAG expansion | Compliance team reviewed 50 AI-generated draft responses. 3 contained language that could be interpreted as financial advice. Added Guardrails AI validator for financial advice language. | Marcus Chen (Compliance) became an active advocate rather than a blocker after this session. He became a co-builder. |
| Week 6 | Human agent dashboard + HITL workflow | Tom Fischer proposed reusing Meridian's existing React internal tool instead of building a new dashboard. Saved 2 weeks of frontend development. | Agent experience improved significantly — familiar UI rather than a new tool to learn. |

### Technical Challenge: The CRM API Timeout Problem

In Week 5, the FDE hit the known CRM API timeout risk identified in Week 1. Under load testing with 50 concurrent ticket resolutions, the CRM API timed out 18% of the time. The FDE's decision process (recorded in the daily log):

> *Options: (1) reduce concurrency to avoid CRM load, (2) cache CRM responses in Redis, (3) make CRM call optional — degrade gracefully if timeout. Option 1 creates a throughput ceiling that does not scale. Option 2 introduces stale data risk. Option 3 is the right answer: if CRM is unavailable, the resolution agent responds without account history, which is still better than no response. When CRM context is unavailable, the response includes a soft prompt for the human reviewer to verify account details before sending.*

**ADR-006 written:** 'Graceful degradation on CRM API timeout — resolution proceeds without account context, human reviewer flagged.'

---

## 05 — Phase 4: Production Hardening
*Weeks 7–10 · The difference between a prototype and a production system*

The gap between a working prototype and a production-grade system is where most internal AI projects die. The FDE's job in this phase is to systematically close every gap between 'it works in the demo' and 'it works at 03:00 on a Monday when the on-call SRE is asleep and a flood of Monday morning tickets arrives simultaneously.'

### The Production Readiness Checklist

| # | Requirement | Status at Week 7 | Owner | Resolution |
|---|---|---|---|---|
| 1 | All PII redacted pre/post LLM (Presidio) | ✅ Green | FDE + Marcus Chen | Audit log active, false-positive rate 0.3% |
| 2 | Azure OpenAI DPA/BAA signed | ✅ Green | Klaus Richter + Legal | Microsoft Enterprise Agreement covers this |
| 3 | HITL interrupt for confidence < 0.85 | ✅ Green | FDE + Priya | Tested with 500 low-confidence tickets |
| 4 | Full audit log of all AI decisions + reasoning | 🟡 Amber — log exists but not immutable | FDE + Tom | Week 8: Added PostgreSQL append-only partition with no UPDATE/DELETE grants |
| 5 | LangSmith observability on all LLM calls | ✅ Green | FDE | 100% HITL events, 20% routine sampled |
| 6 | Load test: 200 concurrent tickets in < 30s | 🔴 Red — currently 180 concurrent before latency breach | FDE + Erik Lund | Week 9: ECS task count increased, LiteLLM gateway added for request queuing |
| 7 | Zendesk webhook decouple + Redis queue | ✅ Green | FDE + Tom | Redis Sentinel for HA. Tested: webhook storm → no duplicate tickets |
| 8 | CRM API graceful degradation | ✅ Green | FDE + Priya | Tested: CRM down → system continues, human reviewer flagged |
| 9 | Rollback procedure documented and tested | 🟡 Amber | FDE + Erik | Week 9: Ran rollback drill. Rollback time: 4 min via ECS task definition swap |
| 10 | Guardrails AI: financial advice blocker | ✅ Green | FDE + Marcus Chen | Tested with 50 adversarial prompts. 0 bypasses. |
| 11 | Monitoring: Prometheus + Grafana + PagerDuty | 🔴 Red | Erik Lund | Week 9: Deployed. Dashboards: ticket volume, routing accuracy, cost/ticket, error rate |
| 12 | DPIA filed | 🟡 Amber | Marcus Chen + Legal | Week 10: Filed with DPO. BaFin notification not required (low-risk AI under Article 6) |
| 13 | Agent training completed | 🔴 Red | Sabine Maier + FDE | Week 11: 2-hour training session with 12 agents. Written guide produced. |
| 14 | Runbook for on-call SRE documented | 🔴 Red | FDE + Erik | Week 11: Written. Covers: high error rate, LangSmith spike, Azure OpenAI outage, Presidio false positive escalation |
| 15 | Formal sign-off from Compliance | 🔴 Red — pending DPIA | Marcus Chen | Week 12: Signed. Condition: monthly compliance review meeting for first 6 months |

### Week 9: Load Testing — A Real Problem Found

Load testing revealed the system could handle 180 concurrent ticket resolutions before latency breached the 30-second SLA. Target was 200 concurrent. The bottleneck: Azure OpenAI TPM (tokens per minute) quota.

- **Root cause:** Azure OpenAI deployed quota was 100k TPM. At 200 concurrent tickets with average 600 tokens/ticket, the system hit rate limits at 180 concurrent.
- **Solution:** Deployed LiteLLM as an AI Gateway between the LangGraph agent and Azure OpenAI. LiteLLM handles request queuing, retry logic, and routing to a fallback Azure OpenAI deployment in Sweden Central when the primary deployment is throttled.
- **Outcome:** With LiteLLM gateway + second region fallback, the system handles 250 concurrent tickets at p99 < 28 seconds. 25% headroom above target.

**ADR-007 written:** 'LiteLLM AI Gateway for load distribution and fallback across Azure OpenAI deployments.'

### The Compliance Review — Week 10

Marcus Chen conducted the formal compliance review in Week 10. This was a structured 3-hour session with the FDE walking through every data flow, every decision point, and every log entry that would be visible in a BaFin examination. The FDE prepared a compliance dossier of 28 pages covering: system architecture, data flows with PII annotation, HITL decision log samples, Guardrails AI configuration and test results, and the LangSmith trace archive policy.

**Marcus Chen's formal conclusion:**
> *"The system architecture as presented satisfies the requirements of GDPR Articles 5, 22, and 25. The human-in-the-loop interrupt mechanism satisfies the BaFin informal guidance on AI decision-making in customer-facing financial services. The audit log architecture satisfies requirements for examination-readiness. Conditional on: (1) monthly compliance review meetings, (2) DPIA review within 12 months if ticket volume increases above 150% of current baseline, (3) annual red-team exercise on the Guardrails AI validator."*

---

## 06 — Phase 5: Go-Live & Handoff
*Weeks 11–12 · Transferring ownership without dropping the baton*

### The Go-Live Strategy: Canary, Not Big Bang

| Phase | Traffic | Duration | Monitoring Focus | Rollback Trigger |
|---|---|---|---|---|
| Phase 1: Shadow mode (Week 10) | 0% AI responses sent — system runs in parallel, outputs logged but not used | 5 business days | Routing accuracy on live traffic vs. human routing decisions. Target: > 90% agreement. | N/A — no customer impact possible |
| Phase 2: Canary 10% (Week 11, Day 1) | 10% of incoming tickets routed through AI pipeline | 48 hours | Error rate, SLA breach rate, agent satisfaction, PII audit log | Error rate > 2% OR any PII event OR agent revolt |
| Phase 3: Canary 30% (Week 11, Day 3) | 30% through AI pipeline | 48 hours | Same + cost/ticket vs. projection | Same as above + cost > €0.08/ticket |
| Phase 4: Canary 70% (Week 11, Day 5) | 70% through AI pipeline | 2 business days | Full metric suite + HITL rate (target < 15%) | HITL rate > 20% |
| Phase 5: Full deployment (Week 12, Day 1) | 100% AI pipeline | Ongoing | Full monitoring suite active, weekly review meeting | Automated PagerDuty rollback if error rate > 5% for 10 consecutive minutes |

> **Week 11, Day 2 — An Unexpected Event:** At 14:23, the monitoring dashboard showed a 3-minute spike in HITL escalation rate from 12% to 47%. PagerDuty fired. Root cause: a Meridian press release published at 14:15 generated 23 identical customer questions about a new product feature in 18 minutes. The routing model had never seen this ticket type. Resolution: FDE added 5 synthetic 'new product inquiry' tickets to the Chroma vector store. HITL rate returned to 11% within 20 minutes. **Lesson:** Live systems face distribution shifts that test sets cannot anticipate. LangSmith + fast reindexing is the remediation path.

### Knowledge Transfer — Built Throughout, Not Done at the End

The worst FDE handoffs happen when the FDE spends Weeks 1–10 building in isolation and then tries to transfer 10 weeks of context in Week 12. Effective knowledge transfer is woven into every week:

- **Pairing sessions (daily).** Priya Sharma paired with the FDE every afternoon. By Week 8, she had written 40% of the non-prototype code and could explain every architectural decision.
- **Documentation written same-day.** Every ADR, runbook, and architectural diagram was written the same day as the decision. The documentation was part of the work, not an afterthought.
- **Code reviews as teaching.** When Tom Fischer submitted PRs, the FDE's reviews were detailed — not just 'LGTM' but explanations of why a pattern was chosen, links to relevant ADRs, and alternative approaches with their trade-offs.
- **Weekly demo audience expansion.** By Week 8, the Friday demos included 3 support agents learning the system from the user perspective, 2 platform engineers learning from the engineering perspective, and Marcus Chen learning the compliance evidence trail.

### The Handoff Package

| Document | Description |
|---|---|
| Architecture Overview Doc | 25-page document covering system architecture, data flows, component interactions, and operational characteristics. Written for an engineer who has never seen the system. |
| ADR Library (7 ADRs) | Every significant architectural decision documented: options considered, trade-offs, decision made, and what was explicitly rejected. |
| Runbook: Routine Operations | Day-to-day operational guide: how to check system health, add new ticket types to the routing model, update the policy RAG knowledge base, review LangSmith traces. |
| Runbook: Incident Response | On-call guide: 8 incident scenarios with step-by-step remediation. Covers: Azure OpenAI outage, Redis queue backup, high HITL escalation rate, Presidio false positive spike. |
| Runbook: Compliance Review | Monthly compliance review checklist for Marcus Chen: audit log review, Guardrails AI test run, PII redaction false-positive rate check, HITL decision log spot-check. |
| Evaluation Harness | 200-question golden test set with routing ground truth. Run weekly via GitHub Actions. Alerts on routing accuracy < 92% or faithfulness < 0.88. |
| LangSmith Project Guide | How to read traces, set up experiments, compare model versions, investigate a specific ticket's AI decision trail. |
| Team Training Recording | 2-hour training session (recorded) covering: system overview, human agent dashboard, HITL workflow, how to interpret AI routing decisions, how to report issues. |

### The Retrospective — Week 12, Final Day

1. **What went better than expected?** Prototype speed, compliance team engagement, routing accuracy, agent adoption of the dashboard.
2. **What went worse than expected?** CRM API stability, Azure OpenAI quota, the Week 11 press-release distribution shift.
3. **What would we do differently from Day 1?** Negotiate Azure OpenAI quota increase before Week 1, not Week 9. Start DPIA in Week 1 alongside architecture work, not Week 9 after system is built.

---

## 07 — Outcomes & Business Impact
*12 weeks later — what changed*

### Quantified Results (Measured at 30 Days Post Go-Live)

| Metric | Result | Target |
|---|---|---|
| Ticket Deflection Rate | **40%** | 35% |
| SLA Breach Rate | **11%** | < 15% |
| Routing Accuracy | **94.2%** | 92% |
| Agent Satisfaction | **4.3 / 5** | 4.0 |
| Cost per AI-Handled Ticket | **€0.022** | < €0.10 |
| BaFin Compliance Incidents | **0** | 0 |
| PII Leakage Events | **0** | 0 |
| HITL Escalation Rate | **12.8%** | < 15% |
| Client Engineers Fully Trained | **4** | — |

### Qualitative Outcomes

**The compliance team became a co-builder.** Marcus Chen went from the engagement's primary sceptic (Week 1) to co-authoring 2 of the 7 ADRs and representing the system to BaFin examiners in the post-engagement review. This is the most important outcome — not the technical system, but the organisational capability to own, extend, and defend it.

**The failed chatbot precedent was overcome.** The 18-month-old failed chatbot project was the ghost haunting the engagement. By Week 4's demo, when Sabine Maier saw the routing explanation, the narrative shifted permanently. The system explains its decisions — the previous chatbot did not.

**Agent adoption was faster than projected.** The decision in Week 6 to use the existing internal React tool was key. Agents did not have to learn a new tool — they had a new feature in a familiar tool. 38 of 42 agents were using the HITL review dashboard by Week 2 of full deployment.

**Knowledge was successfully transferred.** 8 weeks after the FDE's departure, Priya Sharma's team shipped two improvements independently: (1) expanded the policy RAG knowledge base with 200 new FAQ articles, (2) added a new routing destination for regulatory inquiry tickets. Neither required the FDE's involvement.

### What the FDE Took to the Next Engagement

- **LiteLLM AI Gateway as standard** — not an afterthought for load testing. Every AI system should have an AI Gateway layer from Day 1. Added to the pre-engagement technology risk matrix template.
- **Start DPIA in Week 1** — not after architecture is finalised. The DPIA informs the architecture as much as the architecture informs the DPIA. Running them in parallel saves weeks.
- **Distribution shift monitoring as a first-class production concern** — the Week 11 press-release incident showed that routing accuracy on a static test set is necessary but not sufficient. Added semantic drift monitoring to the production readiness checklist.
- **The compliance team is an asset, not an obstacle** — when engaged early, given real visibility into design decisions, and given a formal sign-off pathway, compliance professionals become the strongest advocates for AI systems they helped shape.

---

## 08 — The FDE Playbook
*Reusable principles extracted from this engagement*

1. **Discovery before architecture.** The worst AI system designs come from engineers who started coding before understanding the problem. The discovery workshop is the most important meeting of the engagement — prepare harder for it than for any technical sprint.

2. **Prototype in 72 hours or you are not prototyping — you are designing.** The prototype does not need to be good. It needs to be real enough to change the client's mental model of what is possible. Scope down until it fits in 72 hours.

3. **Write the ADR before you write the code.** An Architecture Decision Record that takes 2 hours to write saves 20 hours of re-architecture later. Every significant decision gets an ADR — especially the decisions not to do something.

4. **Pair with a client engineer every afternoon.** If you are the only person who understands any part of the system by Week 6, you have failed at knowledge transfer. Build redundancy into human understanding, not just infrastructure.

5. **Demo every Friday. Without exception.** If the week went badly, demo what went wrong and what you learned. A weekly demo of 'we discovered the CRM API has a 15% timeout rate and here is how we handled it' builds more trust than a polished demo of feature work.

6. **Make the compliance team a co-builder.** Engage the compliance team in design decisions from Week 1. Give them a formal sign-off pathway. They will become your most powerful advocate because they co-own the outcome.

7. **The real constraint is always discovered during discovery.** The BaFin HITL requirement at Meridian. The failed chatbot precedent. The CRM API instability. None of these were in the initial brief. Thorough discovery is the only way to find them before they find you.

8. **Canary deploy always.** There is no such thing as a 'small' production deployment for an AI system. Shadow mode → 10% → 30% → 70% → 100%, with explicit rollback triggers at each gate. The Week 11 press-release distribution shift would have been a production incident without the canary buffer.

9. **Documentation on the same day as the decision.** Documentation written a week after the decision is reconstruction, not documentation. The details that matter — the options rejected, the concerns raised, the edge cases identified — are gone by then.

10. **Build monitoring before you build features.** LangSmith tracing was deployed in Week 3 alongside the prototype. The cost-per-ticket metric and the routing accuracy metric were live from Day 1 of the prototype. Without these, the Week 9 load testing would have been a week of blind debugging.

11. **The FDE is not the smartest person in the room.** The client's engineers know their codebase, their users, and their organisational constraints far better than you ever will. Your value is the pattern recognition from other engagements they do not have access to. Be curious and humble about what they know that you do not.

12. **Start the handoff on Day 1.** The end of the engagement is determined by what was built in the first week. If the first week's prototype is undocumented black-box code that only the FDE understands, the handoff will fail regardless of how much documentation is written in Week 12.

---

> **The FDE Credo:** An FDE engagement succeeds when the client's team is more capable after the engagement than before it — not just because a new system exists, but because they understand why it was built the way it was, can extend it independently, and have a mental model of the trade-offs that will serve them for the next 3 years of decisions.
>
> If the client needs the FDE to return for every non-trivial change, the knowledge transfer failed. The measure of FDE success is the quality of the thing the client builds *after* you leave.
