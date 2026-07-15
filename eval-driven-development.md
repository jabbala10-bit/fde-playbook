# Eval-Driven Development

### How to actually build the "superpower" the rest of this stack keeps naming

*Part of [The FDE Playbook](./README.md). Consumes the [instrumented service layer](./reference-architecture.md)'s eval sampling hook; feeds the governance evidence trail in [The Governance Playbook](./governance-playbook.md) and [EU AI Act guide](./eu-ai-act.md) (Art 15).*

> "Eval-driven, always" gets said a lot and built rarely. This is the difference between "it feels better" and "accuracy went 82% → 91%" — and it's the only way to productionize a frontier model without flying blind. If you skip this doc and just vibe-check your prompts, you're not doing the job.

---

## The reframe

An eval is not a test suite you write once and forget. It's the **instrument you use to see** whether a change helped, hurt, or did nothing — for every prompt edit, model swap, guardrail tweak, and RAG pipeline change. No eval, no signal. No signal, no engineering — just opinion with extra steps.

**The core discipline:** define the metric *before* you optimize, not after. If you can't say what "better" means in a number, you're not ready to change the system.

---

## Step 1 — Build the golden set

This is the highest-leverage hour in the whole practice, and the one most commonly skipped.

- **Source real examples**, not synthetic ones. A demo on hand-picked inputs proves nothing (see the [FDE Playbook](./README.md)'s prototype-stage trap); an eval set on hand-picked inputs has the same disease.
- **Start small and real** — 30–50 genuinely representative examples beats 500 synthetic ones. Grow it as you find failure modes in production.
- **Include the edge cases that already broke something.** Every production incident should mint a new golden-set example — this is how the eval set gets smarter over time instead of staying frozen at v1.
- **Label with the answer you'd accept**, not just the answer you got. For open-ended tasks, write a rubric, not a single gold string.
- **Hold out a slice.** Don't tune against 100% of your golden set — keep 20% untouched so you can catch overfitting to the eval itself.

| Golden set size | When it's enough |
|---|---|
| 20–30 examples | Early prototype stage — enough to catch gross regressions |
| 100–300 examples | Pre-production — enough for a stable percentage-based metric |
| 500+ examples | High-risk / regulated use case — enough to support a declared accuracy claim (Art 15) |

---

## Step 2 — Pick the right metric type

Different tasks need fundamentally different measurement approaches. Using the wrong one is the most common eval mistake.

| Task shape | Metric approach | Watch out for |
|---|---|---|
| Classification, extraction, structured output | Exact match / F1 against labeled data | Brittle to harmless formatting variation — normalize before comparing |
| Retrieval / RAG | Precision@k, recall@k, groundedness (is the answer supported by retrieved context) | Groundedness ≠ correctness — a well-grounded answer can still be wrong if retrieval pulled the wrong doc |
| Open-ended generation, summarization, chat | LLM-as-judge against a rubric | Position bias, self-preference bias, rubric ambiguity — see below |
| High-stakes decisions (credit, hiring, medical) | Human eval, ideally domain-expert | Slow and expensive — use it to calibrate the automated metric, not to run on every change |
| End-to-end business impact | Task success rate / downstream business metric | The metric that actually matters, but slowest to get signal on — pair with a faster proxy metric for iteration speed |

**The pattern:** use a fast proxy metric (exact match, LLM-as-judge) for day-to-day iteration, and periodically check it against the slow, expensive, trustworthy metric (human eval, business outcome) to make sure the proxy hasn't drifted from what actually matters.

---

## Step 3 — Design the LLM-as-judge carefully, if you use one

LLM-as-judge is powerful and easy to get wrong quietly.

- **Write a rubric, not a vibe.** "Rate 1–5 for helpfulness" is nearly useless. "Does the response cite a source for every factual claim? Does it decline when the question is out of scope?" is gradeable.
- **Randomize position** when comparing two outputs — judges have a measurable bias toward whichever answer comes first (or, with some judges, second).
- **Watch self-preference bias** — a judge model tends to score its own family's outputs more favorably. If you can, judge with a different model than the one you're evaluating.
- **Calibrate against human labels periodically.** Run the judge and a human on the same 30–50 examples, check agreement. If they diverge, fix the rubric before trusting the judge again.
- **Log the judge's reasoning, not just the score.** When a score looks wrong, you need to see *why* the judge gave it to debug the rubric or the underlying failure.

---

## Step 4 — Get the statistics right

- **A percentage point of "improvement" on 20 examples is noise.** Know your sample size before you trust a delta — a rule of thumb: don't claim a change helped unless the eval set is large enough that the swing couldn't plausibly be chance (a simple binomial confidence interval on your pass rate will tell you this).
- **Report a range, not a point estimate**, when the sample is small: "87% ± 6%" is honest; "87%" invites false confidence.
- **Don't tune against the eval set you're reporting on.** This is the classic overfitting mistake — use the held-out slice from Step 1 for the number you actually report.
- **Re-run the full suite on every material change**, not a spot check — a fix for one failure mode silently regressing another is the single most common way production quality erodes over time.

---

## Step 5 — Wire it into the loop

The eval only earns its keep if it's in the path of every change, not a manual step someone forgets under deadline pressure.

- **CI gate:** every prompt, model, or guardrail change runs the full golden set before merge; block on regression past a defined threshold.
- **Production sampling:** the [instrumented service layer](./reference-architecture.md)'s eval hook scores a percentage of live traffic continuously, off the critical path — this is how you catch drift between releases, not just at release time.
- **Dashboard, not just a log.** Accuracy over time, broken down by failure category, visible to the team — not a number that only exists in a CI log nobody reads.
- **A failure taxonomy.** Don't just track pass/fail — tag *why* something failed (hallucination, refusal-when-shouldn't, wrong format, stale retrieval). This is what turns "it's worse" into "retrieval regressed on multi-hop questions," which is actually actionable.

---

## The iteration loop

```
  golden set  ──►  run eval  ──►  score + failure taxonomy
       ▲                                    │
       │                                    ▼
  add new failure          diagnose: prompt? retrieval? model? guardrail?
  cases from prod                           │
       ▲                                    ▼
       └──────────────  make ONE change  ◄──┘
                              │
                              ▼
                        re-run full suite
                        (regression check)
```

Change one thing at a time. Changing the prompt and the retrieval strategy in the same iteration means you can't attribute the eval delta to either one.

---

## Anti-patterns

- **No eval set at all — iterating on vibes.** The single most common failure mode this whole doc exists to prevent.
- **An eval set frozen at v1**, never updated with real production failures — it stops reflecting reality within weeks.
- **Reporting a number with no sample size or confidence range attached.**
- **Using an LLM-as-judge with no rubric and no calibration check.**
- **Tuning against 100% of the eval set**, so the reported number is optimistic by construction.
- **Evals that only run in CI, never in production** — you catch regressions at release time but miss drift between releases.

---

## One-page quick reference

**The discipline:** define the metric before you optimize; no measurement, no engineering.

**Golden set:** real examples, not synthetic; grows from production incidents; hold out 20%.

**Metric choice:** match the task shape (exact match / retrieval metrics / LLM-as-judge / human eval / business outcome); use a fast proxy for iteration, calibrate against a slow trusted metric periodically.

**LLM-as-judge:** rubric over vibes; randomize position; watch self-preference bias; calibrate against humans.

**Statistics:** know your sample size; report a range on small samples; never tune against what you report.

**Wiring:** CI gate on every change + continuous production sampling + a dashboard + a failure taxonomy.

**Change discipline:** one variable at a time, full suite re-run, every time.

> The whole thing in a sentence: **build a real, growing, held-out golden set; measure with the metric that matches the task; run it on every change and continuously in production — and never trust a number you can't attach a sample size to.**

---

*Back to [The FDE Playbook](./README.md) · [Instrumented Service Layer](./reference-architecture.md) · [The Governance Playbook](./governance-playbook.md)*
