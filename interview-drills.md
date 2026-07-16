# Interview Drill Bank

### Gradable practice prompts for each round of the FDE interview loop

*Part of [The FDE Playbook](./README.md). Companion to [notes/18_interview_blackbook_case_studies.md](./notes/18_interview_blackbook_case_studies.md), which already has a full worked system-design answer ("Design an Enterprise RAG for a Legal Firm") — this file adds new, non-duplicate prompts plus grading rubrics, and is the practice material [prep-plan-4-week.md](./prep-plan-4-week.md) Week 4 uses for the mock loop.*

> Self-grade honestly. The point of a rubric is to catch the gap between "I could talk about this" and "I did talk about this, at this level" — grading generously defeats the purpose.

---

## 1. System-design prompts

Give yourself 45-60 minutes each: 5 minutes clarifying requirements, then
architecture, then tradeoffs — mirroring notes/18's "Round 2: System
Design" structure. Say your answer out loud or write it as if presenting
to a technical stakeholder; silently knowing the answer doesn't count.

### 1.1 — Governance triage for a new product line

*"A customer wants to add an AI feature that auto-approves small business
loans under $50,000 using an LLM to summarize applicant financials and a
separate scoring model to recommend approve/deny. Walk me through how you'd
scope this, and what governance posture it needs."*

Build your answer, then run it through
[Capstone 2](./capstones/governance_assessment/) with a profile you write
yourself — compare your predicted risk tier to what the tool outputs, and
be ready to explain any mismatch (credit scoring is EU AI Act Annex III
high-risk; did you catch that from the description alone?).

### 1.2 — The instrumented service layer, live

*"Your customer already has three teams independently calling an LLM API
directly from their services. Convince their engineering lead why that's a
problem, and sketch what you'd replace it with."*

Your answer should arrive at [reference-architecture.md](./reference-architecture.md)'s
shape without you having memorized the doc — if you can only recite it,
you haven't internalized *why* one layer beats three. [Capstone 3](./capstones/incident_debugging/)
is this architecture in code; use it to ground specifics (what does the
router actually resolve? what's on the critical path vs. async?).

### 1.3 — Greenfield: field-service AI copilot

*"A utility company wants an AI copilot for field technicians — voice
queries against equipment manuals and safety procedures, usable on a
tablet with unreliable connectivity in the field."*

No worked answer exists for this one in the repo — that's deliberate. Use
[discovery-toolkit.md](./discovery-toolkit.md)'s scoring rubric to decide
the wedge, [reference-architecture.md](./reference-architecture.md) for the
system shape, and think through the offline/unreliable-connectivity
constraint explicitly — it changes the architecture (local caching? sync
strategy?) in a way the other two prompts don't force you to consider.

### System-design grading rubric (score each 1-5)

| Dimension | 1 | 3 | 5 |
|---|---|---|---|
| Technical correctness | Architecture has a component that wouldn't actually work | Architecture is sound and complete | Sound, complete, and you preempted the follow-up question |
| Value framing | Jumped straight to architecture | Tied choices back to the business metric | Could state the metric and target *before* describing any architecture |
| Tradeoff reasoning | Presented one option with no alternatives considered | Named the alternative and why you didn't pick it | Named the alternative, the condition under which you'd switch, and the cost of switching |
| Communication clarity | Technical jargon a non-technical exec couldn't follow | Could explain the same answer to an exec in under 2 minutes | Did both — technical depth *and* an exec-ready summary, unprompted |

---

## 2. Behavioral prompts (STAR format)

Each is built from a failure mode in [README.md](./README.md#failure-modes--anti-patterns).
Answer in Situation/Task/Action/Result — a real example if you have one,
otherwise a specific hypothetical you'd actually execute.

1. **Wrong-sized engineering.** *"Tell me about a time you had to decide
   between shipping something rough now versus building it right."* (Tests: judgment on the over-/under-engineering tradeoff.)
2. **The demo that never productionizes.** *"Tell me about a project that
   looked great in a demo but struggled to reach production. What
   happened?"* (Tests: honesty about the demo-to-production gap, and what you'd do differently.)
3. **Going native.** *"Tell me about a time a customer pushed you toward a
   solution you didn't think was right. What did you do?"* (Tests: whether you can hold the product/lab perspective under pressure.)
4. **Hero mode / bus factor.** *"Tell me about a system you built that had
   to keep running after you left. How did you make sure of that?"* (Tests: whether "done" means "shipped" or "shipped and handed off.")
5. **Skipping evals.** *"Tell me about a time you had to convince someone
   — technical or not — that 'it feels better' wasn't good enough
   evidence."* (Tests: whether eval-driven development is a habit or a slogan for you.)

### Behavioral grading rubric (score each 1-5)

| Dimension | 1 | 3 | 5 |
|---|---|---|---|
| Specificity | Generic, no concrete situation | Named a real situation with details | Named numbers/outcomes, not just narrative |
| Ownership | Blamed circumstances or others | Owned your role in the outcome | Owned it *and* named what you changed afterward |
| Self-awareness | No reflection on what you'd do differently | Named one thing you'd change | Named the change and how you've since applied it elsewhere |

---

## 3. Live debugging prompts

*"Something's wrong in production. Here's the trace."*

Run [Capstone 3](./capstones/incident_debugging/) with a seed you haven't
used before (`python -m capstones.incident_debugging run --seed <n>`) and
follow its [runbook.md](./capstones/incident_debugging/runbook.md) under a
20-minute clock. This is the closest analog in the repo to notes/18's
"Round 4: Technical Deep Dive ... live coding or debugging session."

**Grading:** see the rubric in
[runbook.md](./capstones/incident_debugging/runbook.md#grading-rubric).

*"Cart abandonment is up. Where do you even start?"*

Run `python -m capstones.full_stack_observability diagnose` on
[Capstone 4](./capstones/full_stack_observability/) without reading
`simulate.py` first. State your hypothesis for the root cause, and which
of the 4 layers you'd rule out and why, before checking it against the
correlation output. This is the "start from business impact, work down
through the layers" version of the same skill — see that capstone's
[grading rubric](./capstones/full_stack_observability/README.md#grading-rubric).

---

## 4. Self-tracking checklist

Copy this per mock round:

```
Round: ______________________   Date: ______________
Prompt used: ________________________________________
Time taken: _______   Time budget: _______

Technical correctness   [ ] 1  [ ] 2  [ ] 3  [ ] 4  [ ] 5
Value framing            [ ] 1  [ ] 2  [ ] 3  [ ] 4  [ ] 5
Tradeoff reasoning       [ ] 1  [ ] 2  [ ] 3  [ ] 4  [ ] 5
Communication clarity    [ ] 1  [ ] 2  [ ] 3  [ ] 4  [ ] 5

Biggest gap this round: _____________________________
One change before the next round: __________________
```

Run the full loop (technical screen → system design → behavioral → deep
dive/debugging → case study) at least once before treating yourself as
interview-ready — a strong score on one round in isolation doesn't predict
performance across all five back to back.
