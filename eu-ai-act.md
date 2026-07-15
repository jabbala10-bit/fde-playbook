# Implementing EU AI Act Compliance in a Real Product

### A build-oriented guide, organized by risk category

> The AI Act is written for lawyers, but compliance is built by engineers and product teams. This guide translates the statutory obligations into **concrete artifacts you produce and systems you build**, tier by tier. The governing move is the same as any hard engineering problem: *classify first, because the risk tier determines everything you have to do.* Get the classification wrong and you either over-build (wasted months) or under-build (illegal product).
>
> Current to mid-2026, reflecting the Digital Omnibus timeline. Not legal advice — engage counsel to confirm your classification and conformity route.

---

## The operating model (how to think about it)

Compliance is **two orthogonal questions**, not one:

1. **What risk tier is my *system*?** → Prohibited / High-risk / Limited-risk (transparency) / Minimal-risk. This sets your obligations.
2. **What is my *role*?** → Provider (you build/put it on the market) / Deployer (you use it) / Distributor / Importer. This sets *which* obligations fall on you.

And a **third, separate axis** if you touch foundation models:

3. **Am I a GPAI (general-purpose AI) model provider, or building on one?** → GPAI obligations stack *on top of* the tier obligations.

A single product can occupy several of these at once. An LLM customer-support agent is: a *limited-risk* system (transparency duties), where you're a *deployer* of someone else's *GPAI*, possibly also a *provider* if you fine-tune and ship it. You must resolve all three axes.

**The compounding architecture insight:** almost every high-risk requirement — logging, data governance, evals, human oversight, incident reporting — is far cheaper to satisfy if every model call in your product flows through **one instrumented service layer** rather than being scattered across the codebase. Build that layer first; compliance then becomes configuration, not retrofit. (This is good architecture regardless of the Act.)

---

## Step 1 — Classify your system (decision tree)

```
START: Does the system do something on the Article 5 PROHIBITED list?
  (social scoring, manipulative/subliminal techniques, exploiting vulnerabilities,
   untargeted facial-image scraping, emotion recognition in work/education,
   most real-time remote biometric ID in public, certain predictive policing,
   + new: generating CSAM / non-consensual intimate imagery)
        │
       YES ──► STOP. You cannot ship this in the EU. Redesign out of the prohibited use.
        │
        NO
        ▼
Is it a HIGH-RISK use? Two gates:
   (a) Annex I: an AI system that is a safety component of a product already
       regulated by EU law (medical devices, machinery, toys, vehicles, lifts...)
   (b) Annex III: use in a listed high-stakes domain — biometrics, critical
       infrastructure, education/vocational, employment/HR (hiring, firing,
       task allocation), essential services & credit scoring, law enforcement,
       migration/asylum/border, administration of justice & democratic processes
        │
       YES ──► HIGH-RISK. Full obligations (Articles 9–15 + provider/deployer duties,
        │       conformity assessment, CE marking, registration). This is the heavy tier.
        │       (Narrow carve-out: if it's Annex III but only does a narrow procedural
        │        task / doesn't materially influence the decision, you may document it out —
        │        but you must assess and record that judgment.)
        NO
        ▼
Does it INTERACT with people, generate synthetic media, do emotion recognition,
or produce deepfakes / AI text on matters of public interest?
        │
       YES ──► LIMITED-RISK. Transparency obligations only (Article 50):
        │       disclose + label. Much lighter.
        NO
        ▼
MINIMAL-RISK (spam filters, most recommendation, AI in games, back-office tooling).
No mandatory obligations. Voluntary codes of conduct encouraged.
```

Run this per **use**, not per product. The same model can be minimal-risk in one feature and high-risk in another.

---

## Tier 1 — Prohibited: how to make sure you're not accidentally here

You don't "comply" — you *avoid*. But teams drift into prohibited territory by accident, so build a gate:

- Add an **Article 5 review** to your product-intake / design-review process. Any feature touching biometrics, emotion inference, behavioral manipulation, scoring of people, or law-enforcement/border use gets flagged for legal review *before* build.
- Watch the **December 2026** additions: systems that generate non-consensual intimate imagery or CSAM. If you run generative image/video, your safety filters and red-teaming must demonstrably prevent these outputs.
- Document the *negative* finding ("we assessed X against Article 5 and it is not prohibited because…"). Absence of a paper trail is itself a risk.

Penalty for getting this wrong: up to **€35M or 7% of global turnover**, whichever is higher. This is the one tier where a mistake is existential.

---

## Tier 2 — High-Risk: the heavy tier, mapped to what you actually build

If you're a **provider** of a high-risk system, you must satisfy seven core requirements (Articles 9–15). Here's each one translated into concrete deliverables:

| Article | Requirement | What you actually build / produce |
|---|---|---|
| **9 — Risk management** | A continuous, iterative risk process across the lifecycle | A living risk register: identified risks, likelihood/severity, mitigations, residual-risk sign-off. Re-run on every material change. Not a one-time doc. |
| **10 — Data governance** | Training/validation/test data must be relevant, representative, appropriately complete, and examined for bias | Dataset documentation (sources, lineage, collection method), bias/representativeness analysis with metrics, data-quality checks in your pipeline, documented handling of gaps. |
| **11 — Technical documentation** | The Annex IV technical file, ready *before* market | A maintained tech-doc package: system description, design specs, architecture, training methodology, performance metrics, known limitations. Treat it like living design docs, versioned. |
| **12 — Record-keeping / logging** | Automatic, tamper-evident logs enabling traceability | Immutable audit logs capturing: inputs, outputs, model + prompt version, timestamps, confidence/scores, human-override events. Defined retention. *This is where the single service layer pays off.* |
| **13 — Transparency to deployers** | Clear instructions for use so deployers can operate it safely | An "instructions for use" document: intended purpose, accuracy/limitations, required human oversight, input requirements, foreseeable misuse. Ship it with the product. |
| **14 — Human oversight** | Designed so a human can understand, intervene, and override | UI + workflow for meaningful review: surfacing confidence, explanations, an override/stop control, guardrails against automation bias. Oversight has to be *effective*, not a rubber-stamp checkbox. |
| **15 — Accuracy, robustness, cybersecurity** | Declared accuracy, resilience to errors/adversarial inputs, security | An eval suite with declared accuracy metrics; adversarial/red-team testing; drift monitoring; security hardening (prompt-injection, data poisoning, model theft). Publish the metrics you declare. |

**Then the process obligations layered on top:**

- **Quality Management System (Art 17)** — documented org processes for the above, ISO/IEC 42001 is the natural backbone.
- **Conformity assessment** — for most Annex III systems this is *self-assessment* (internal control, Annex VI): you assess and declare. Some cases (certain biometrics; Annex I products under sectoral law) require a **notified body** (third-party, Annex VII). Confirm your route early — it changes your timeline by months.
- **EU Declaration of Conformity + CE marking** — you sign a declaration and affix the CE mark.
- **Registration** in the EU high-risk AI database before going to market.
- **Post-market monitoring (Art 72)** — a plan and system to collect real-world performance data and catch emerging risks.
- **Serious-incident reporting (Art 73)** — a process to report serious incidents/malfunctions to authorities within defined windows.

**If you're a *deployer* (Art 26), not the provider**, your burden is lighter but real: use it per the instructions, assign competent human oversight, monitor operation, keep the logs the system generates, ensure input data is relevant, and inform affected workers. Public bodies and some private deployers must also run a **Fundamental Rights Impact Assessment (Art 27)** before use.

**Effective date for Annex III high-risk: 2 December 2027** (deferred by the Digital Omnibus). Annex I product-embedded: **2 August 2028**. You have runway — use it to build the artifacts above into your normal SDLC rather than a panic sprint.

---

## Tier 3 — Limited-Risk (transparency): light but non-optional

Article 50 duties. These are mostly **product/UX + a bit of engineering**, and apply from 2026 (with content-labeling specifics landing **2 December 2026**):

| Situation | What you must do | Implementation |
|---|---|---|
| System interacts with humans (chatbots, voice agents) | Tell users they're dealing with AI (unless obvious) | A clear disclosure in the UI / at conversation start. One sentence, but it must be there. |
| You generate synthetic audio/image/video/text | Mark output as artificially generated, machine-readable | Embed provenance metadata / watermarking (e.g. C2PA-style); a visible label where a person could be misled. |
| Deepfakes | Disclose the content is artificially generated | Visible disclosure on the media. |
| AI-generated text on matters of public interest | Disclose it's AI-generated | Editorial labeling. |
| Emotion recognition / biometric categorization | Inform the people exposed to it | Notice at point of interaction. |

For an LLM app, the realistic checklist is: (1) an "I'm an AI" disclosure, (2) provenance metadata on any generated media, and (3) a visible label on anything that could be mistaken for real. Build the watermarking into your generation service layer once, and every feature inherits it.

---

## Tier 4 — Minimal-Risk: nothing mandatory

Most AI (spam filters, recommendations, in-game AI, internal tooling) sits here. No obligations. Recommended good practice anyway: adopt a voluntary code, keep basic documentation, and instrument for transparency — because your risk classification can *change* as you add features, and it's cheaper to have the plumbing already there.

---

## The orthogonal axis — GPAI / foundation models

If you're building with or on foundation models, this stacks on top of the tier above.

**If you *build and release your own* general-purpose model** (Chapter V), you owe (from August 2025):
- Technical documentation of the model.
- Information + documentation to downstream providers who build on it.
- A policy to respect EU copyright law.
- A publicly available summary of training content.

**If your model crosses the systemic-risk threshold** (training compute ~10²⁵ FLOPs, or designated), add: model evaluation and adversarial testing, systemic-risk assessment and mitigation, serious-incident tracking, and cybersecurity protections. The **GPAI Code of Practice** is the practical compliance tool. Open-source models get partial exemptions *unless* they're systemic-risk.

**If you merely *build on* someone else's GPAI** (the common case — you call an API or fine-tune a hosted model): you are **not** the GPAI provider for the base model, but:
- You inherit the need to pass through relevant information to *your* users.
- If you fine-tune substantially or put your own system on the market, you may become a *provider* of the resulting AI system (and, in some cases, of a modified model) — with the tier obligations that implies.
- Your product still has its own tier classification (transparency and/or high-risk) independent of the model.

---

## Worked example — two products, end to end

### Product A: AI CV-screening tool for recruiters → HIGH-RISK
Employment/HR is Annex III, and screening materially influences hiring decisions, so the narrow-task carve-out won't save you. As the **provider**, your build plan:
- Stand up a **risk register** (Art 9) covering discrimination, false rejects, gaming.
- Document your **training data** (Art 10): where CVs came from, representativeness across protected characteristics, bias testing with concrete fairness metrics.
- Maintain the **Annex IV technical file** (Art 11) as versioned design docs.
- Log every screening decision immutably (Art 12): input CV ref, score, model version, recruiter override.
- Ship **instructions for use** (Art 13) telling recruiters the accuracy, limits, and required oversight.
- Build the **human-oversight UI** (Art 14): show reasoning, require a human decision, guard against rubber-stamping.
- Run an **eval + adversarial suite** (Art 15) and declare accuracy; monitor drift.
- Add a **QMS** (Art 17, via ISO 42001), do **self-assessment conformity**, sign the **declaration + CE mark**, **register** in the EU database, and stand up **post-market monitoring** + **incident reporting**.
- Deploying recruiters (your customers) then owe Art 26 deployer duties, including possibly a **FRIA**.
- **Deadline to be ready: 2 December 2027.**

### Product B: General customer-support chatbot on a hosted LLM → LIMITED-RISK + GPAI-downstream
Not high-risk (general support, no consequential decisions). Your obligations:
- **Disclose it's an AI** at the start of every conversation (Art 50).
- If it generates any images/media, **watermark + label** them (from Dec 2026).
- You're a **deployer** of the provider's GPAI: follow their usage terms, pass through any required info.
- Good-practice extras you'd build anyway: the single service layer with logging, an eval harness, prompt-injection guardrails, and a human-escalation path — none mandatory here, but they make an eventual high-risk feature (e.g. adding automated refunds or credit decisions) a config change instead of a rebuild.

The contrast is the whole lesson: **same underlying tech, wildly different obligations, decided entirely by the *use*.**

---

## The deliverables checklist (what a compliant high-risk product physically has)

- [ ] Written risk classification + Article 5 negative assessment
- [ ] Risk management register (living)
- [ ] Data governance / dataset documentation + bias analysis
- [ ] Annex IV technical documentation file (versioned)
- [ ] Immutable logging with defined retention
- [ ] Instructions-for-use document
- [ ] Human-oversight design (UI + workflow)
- [ ] Eval suite with declared accuracy + adversarial/red-team results
- [ ] Quality Management System (ISO/IEC 42001)
- [ ] Conformity assessment record (self or notified body)
- [ ] EU Declaration of Conformity + CE marking
- [ ] EU database registration
- [ ] Post-market monitoring plan + system
- [ ] Serious-incident reporting process
- [ ] (Deployer, if applicable) Fundamental Rights Impact Assessment

---

## Recommended build sequence

1. **Classify every use** (decision tree) and write it down. This is the highest-leverage hour you'll spend.
2. **Confirm your role(s)** — provider vs deployer changes who owns what.
3. **Build the instrumented service layer** — one path for every model call, with logging, versioning, eval hooks, and guardrails. This single decision satisfies large parts of Articles 12, 14, 15, and 50 at once.
4. **Adopt ISO/IEC 42001** as your QMS backbone — it maps cleanly onto the Act's process requirements and travels to other jurisdictions.
5. **Generate the artifacts inside your normal SDLC**, not as a separate compliance project — risk register in your tracker, tech file as design docs, evals in CI.
6. **Lock the conformity route early** (self vs notified body) so you don't discover a months-long dependency late.
7. **Register + declare + monitor** as you approach launch, and keep the post-market loop running.

---

## Timeline to plan against (post–Digital Omnibus)

| Date | What applies |
|---|---|
| Feb 2025 | Prohibited practices + AI-literacy duties (already in force) |
| Aug 2025 | GPAI model obligations + EU governance bodies (already in force) |
| Aug 2026 | Bulk of the Act applies; transparency (Art 50) framework |
| **2 Dec 2026** | New CSAM/NCII prohibitions + AI-content labeling duties |
| **2 Dec 2027** | Annex III high-risk obligations apply |
| **2 Aug 2028** | Annex I product-embedded high-risk obligations apply |

Penalties, for calibration: prohibited-practice breaches up to €35M / 7% of global turnover; other obligation breaches up to €15M / 3%; incorrect information up to €7.5M / 1%; GPAI breaches up to 3%.

---

## The one thing to remember

**Classification is the whole game.** The Act isn't one burden — it's four very different burdens, and which one you carry is decided entirely by *what your system is used for*, not what technology it uses. Nail the classification, build the instrumented service layer once, generate the paper trail inside your normal engineering process, and high-risk compliance becomes a demanding-but-tractable checklist rather than an existential threat. Verify your specific classification and conformity route with qualified counsel before you ship.
