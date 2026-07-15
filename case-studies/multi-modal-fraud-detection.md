# Case Study 6: Multi-Modal Fraud Detection and Claims Acceleration at a Regional P&C Insurer

## Engagement Context

**Client:** A super-regional property and casualty insurer writing $6.2B in annual premium across auto and homeowners lines in 19 states, processing approximately 380,000 claims per year through a network of 1,100 staff and independent adjusters.

**Engagement trigger:** The insurer's combined ratio had deteriorated 4.2 points year over year. The actuarial team attributed a meaningful share of this to claims leakage — overpayment due to undetected fraud, inflated repair estimates, or processing errors — estimated at $190M annually. At the same time, the claims process had become a customer satisfaction liability: average auto claims cycle time had stretched to 14 days against a newly mandated target of 5. The new Chief Claims Officer arrived with a board mandate that read, on paper, like a contradiction: reduce leakage by 25% while cutting cycle time in half. Faster claims processing is conventionally understood to mean less scrutiny — and less scrutiny is conventionally understood to mean more fraud passing through.

**Timeline:** 24 weeks from kickoff to full deployment across the auto claims line.

**Team:** Principal AI FDE (architecture, requirements, adversarial evaluation design), 2 FDEs, 1 data engineer (claims data and DMS integration), 1 computer vision specialist (damage assessment), the CCO as executive sponsor, Head of the Special Investigations Unit (SIU), 3 senior claims adjusters, Head of Claims Operations, General Counsel (state insurance regulatory compliance), and the Chief Actuary.

**What makes this engagement architecturally distinct:** This is the first engagement in the series with a genuinely adversarial population in the literal sense of the word. A subset of claimants are not merely heterogeneous users with different needs — they are an active adversary with a financial incentive to deceive the system, who will adapt their tactics in direct response to whatever detection method is deployed. A static, one-time accuracy benchmark — the evaluation backbone of every previous case study — is necessary but not sufficient here. Fraud detection systems face what security researchers call a moving target: a model trained and validated against today's fraud patterns will degrade as the population it's detecting adapts to evade it. This required building an evaluation discipline structurally different from anything in the first five case studies. It is also the first multi-modal architecture in the series, combining computer vision, document forensics, and graph-based entity resolution alongside the now-familiar LLM components.

---

## Initial Framing

CCO's request: *"I need claims processed faster and I need fewer fraudulent payouts. Build us AI that catches fraud and speeds up the good claims."*

The framing contains a useful and intuitive but ultimately misleading assumption: that speed and fraud-catching are inherently in tension, and that AI's job is to find the right balance point between them. Discovery would substantially revise this assumption. Speed and fraud detection are not structurally zero-sum if the AI does something a human reviewing every claim at uniform depth cannot do: differentiate, in seconds, between claims that warrant scrutiny and claims that don't — applying senior-adjuster-level pattern recognition to 100% of the volume instead of whatever fraction an overloaded human team can review carefully.

---

## Discovery

**Stakeholder interviews (8 sessions):**

- CCO: "The board gave me a leakage target and a speed target. I was told these were both priorities. I need to understand if that's actually achievable or if I need to go back and negotiate."
- Head of SIU: "We open about 3,200 investigations a year. Based on industry loss data for our book, we estimate we should be opening closer to 5,000 — meaning we're missing a meaningful share of what should be referred. The adjusters handling the volume don't have time to spot the patterns we look for: a claimant who's filed three claims with different insurers in 18 months, a repair shop with an unusual ratio of total-loss recommendations, an address that's appeared on multiple unrelated claims."
- Senior Claims Adjuster (12 years): "I can usually tell when something's off pretty quickly. It's never one thing — it's a combination. The story doesn't quite line up with the photos, the timeline has gaps, the repair estimate is oddly specific in a way that doesn't match the described impact. But I've got 45 open files right now. I don't always have time to sit with the ones that feel slightly off."
- Junior Claims Adjuster (8 months): "I handle the straightforward ones fine. When something feels off I escalate — but I don't always know what 'off' is supposed to look like yet. I'm worried I'm letting things through that a more experienced adjuster would catch."
- Head of Claims Operations: "The real bottleneck is documentation review and back-and-forth. A claimant submits photos, a repair estimate, sometimes medical bills for an injury claim. An adjuster reviews it, often has to go back for something missing or unclear, waits for a response, reviews again. That cycle is most of our 14 days."
- General Counsel: "Every state has its own unfair claims settlement practices act. If we deny or delay a claim improperly, or if our process produces a disparate outcome by protected class, we're exposed to bad-faith litigation and a market conduct exam from the Department of Insurance. I need to understand exactly how this system makes decisions and exactly where a human is required to act before anything adverse happens to a claimant."
- Chief Actuary: "Leakage isn't only fraud. A meaningful share is paid claims where the estimate was inflated, the coverage was misapplied, or nobody caught that the repair estimate didn't actually match what's visible in the photos. Don't build a system that only looks for fraud and ignores the much larger bucket of honest-but-inflated or honest-but-erroneous claims."

**Contextual inquiry (5 sessions):**

Session 1 (Senior adjuster, auto claim with photos): Observed review of a rear-end collision claim. The adjuster opened 14 submitted photos, cross-referenced them against a $4,200 repair estimate, and spent approximately 20 minutes confirming the damage pattern was consistent with the described accident. She caught a detail a less experienced reviewer might miss: one photo showed pre-existing rust damage near the claimed impact area that the estimate had folded into the claimed repair scope. "This happens a lot — not malicious necessarily, but it's leakage if I don't catch it."

Session 2 (Junior adjuster, document review): Observed processing of a claim with a submitted repair invoice from an unfamiliar shop. The invoice had inconsistent fonts between line items — a known forgery indicator the senior adjusters look for reflexively. The junior adjuster did not notice it and approved the claim. Asked afterward whether she'd been trained on document inconsistency indicators: "Not really — I know to check that the total adds up, but I haven't been shown what altered documents typically look like."

Session 3 (SIU investigator, fraud ring investigation): Observed a senior SIU investigator working a suspected staged-accident ring. Her method: cross-referencing claimant names, addresses, phone numbers, and repair shop affiliations across the claims database using a series of manual SQL queries and a personal spreadsheet she'd built over several years. "This entity-matching is the core of what I do, and it's entirely manual. I built my own tooling because nothing in our system does this."

Session 4 (Claims operations, back-and-forth cycle observation): Tracked a single auto claim through its full lifecycle. Initial submission to final payment: 16 days. Of that, approximately 9 days were waiting time — waiting for the claimant to submit additional photos, waiting for a repair shop estimate, waiting for the adjuster's queue to reach the file again after a request was fulfilled.

Session 5 (Computer vision feasibility review with the vision specialist and a senior adjuster): Reviewed a sample of 40 historical claims photos against their associated repair estimates. The senior adjuster could identify estimate-photo mismatches (claimed damage not visible in photos, or photos showing damage inconsistent with the described accident mechanism) in about 90 seconds per claim once she knew what to look for. This became the basis for the vision-grounding requirement described below.

**Analytics review:**

- Of 380,000 annual claims, approximately 65% were low-complexity claims with clear documentation and no fraud indicators (candidates for acceleration)
- 25% had moderate complexity (multiple parties, ambiguous liability, or incomplete documentation) requiring standard adjuster review
- 10% carried one or more fraud risk indicators warranting SIU-level scrutiny, but the existing referral rate suggested only an estimated 40% of true fraud-indicator claims were being caught and escalated
- The current document review process had no systematic forgery detection — adjusters relied entirely on individual experience and attentiveness, which the Session 2 observation showed was inconsistent across tenure levels

**Synthesis and reframe:**

Original framing: "Speed and fraud-catching are in tension; balance them."

Reframe: "The claims population is heterogeneous in a way that maps cleanly to differentiated processing: 65% can be accelerated safely with proper automated verification; 10% need more scrutiny than they currently receive, not less; the remaining 25% benefit from AI-assisted review that surfaces what currently depends on individual adjuster experience. Speed and leakage reduction are not in tension once the system can tell these populations apart — they were only in tension under a uniform-depth review model."

---

## AI Architecture Decisions

**Decision 1: Multi-modal grounding architecture**

Three input modalities required distinct processing pipelines feeding into a unified risk and routing layer:

```
Vision pipeline (damage-estimate consistency):
  Claim photos → object detection (vehicle, damage location, damage type)
  → damage severity classification per detected region
  → cross-reference against submitted repair estimate line items
  → consistency score: does claimed repair scope match visible damage?
  → flag: "estimate includes [line item] not supported by submitted photos"

Document forensics pipeline (forgery and alteration detection):
  Submitted invoices/receipts → OCR extraction
  → font and formatting consistency analysis (per-document)
  → metadata extraction (if digital file: creation/modification timestamps,
    software signature)
  → cross-reference against known-vendor invoice templates (for major repair
    shop chains in network)
  → flag: structural anomalies, font inconsistencies, metadata irregularities

Entity resolution / graph pipeline (organized fraud detection):
  Claim entities (claimant, address, phone, repair shop, witnesses, prior
  claims) → entity normalization and matching
  → graph construction: edges between claims sharing entities
  → graph pattern detection: clusters with shared repair shop + shared
    witnesses + temporal clustering = elevated ring-fraud signal
  → flag: "this claim shares 2 entities with 4 other claims in the past 90 days"

Risk synthesis layer:
  Vision flags + document flags + graph flags + structured claim features
  (claimant tenure, prior claim count, claim-to-policy-inception interval,
  geographic loss patterns)
  → composite risk score
  → routing decision: Fast-track / Standard review / SIU referral
  → Claude-generated narrative summary of risk factors for adjuster review
    (cites the specific flags driving the score — no risk score is presented
    without the underlying evidence visible)
```

The graph-based entity resolution pipeline formalized exactly the manual process the SIU investigator had built for herself in a personal spreadsheet (Session 3). This was the single highest-value technical decision in the engagement — not because the algorithm was novel, but because it converted years of one investigator's informal tooling into a system-wide capability available to every adjuster at the point of initial review, rather than only after a claim had already been escalated to SIU.

**Decision 2: Tiered routing replacing uniform-depth review**

```
Fast-track lane (target: 65% of volume):
  Criteria: composite risk score below threshold AND vision consistency
  check passed AND no document forensics flags AND no graph flags
  Process: automated verification + lightweight adjuster confirmation
  Target cycle time: 48 hours

Standard review lane (target: 25% of volume):
  Criteria: moderate risk score, or specific ambiguity flags (e.g., 
  incomplete documentation, liability ambiguity) without fraud indicators
  Process: adjuster review with AI-surfaced consistency checks and
  document analysis as decision support
  Target cycle time: 5-7 days

SIU referral lane (target: 10% of volume, but improved recall vs. baseline):
  Criteria: composite risk score above threshold, or any high-confidence
  graph/document flag regardless of composite score
  Process: full SIU investigation, AI provides structured case packet
  (entity graph, document flags, vision flags, comparable historical cases)
  Target cycle time: per SIU investigation standards (unaffected — this
  lane prioritizes recall and thoroughness, not speed)
```

Critically, no lane involved the AI autonomously denying, reducing, or closing a claim. NFR-level constraint, driven directly by General Counsel's discovery interview: every adverse action (denial, reduction, extended delay) required adjuster approval, and the fast-track lane accelerated *verification and payment of claims that passed every check*, not the suppression of scrutiny for claims that hadn't been checked.

**Decision 3: The adversarial evaluation architecture**

Standard pre-deployment benchmarking — the pattern used in all five prior case studies — measures performance against a labeled holdout set representing the current distribution of inputs. This is necessary here but insufficient, because the fraud-committing population is not a static distribution; it is a strategic actor that will adapt to whatever detection method is deployed, in the same way that email spam evolved in response to spam filters.

This required an evaluation architecture with three distinct components beyond the standard pre-deployment benchmark:

*Fraud pattern drift monitoring:* A rolling comparison between SIU-confirmed fraud outcomes (the ground truth established after investigation closes, often weeks or months after the initial claim) and the model's original risk score at intake. If the model's precision on confirmed cases begins declining over a rolling 90-day window, this is treated as a drift signal requiring investigation — has a new fraud pattern emerged that the model wasn't trained to recognize?

*Adversarial red-teaming with domain experts who think like fraudsters:* Rather than only testing the model against historical fraud cases (which by definition reflects fraud patterns the system has already learned to catch), the SIU team — who understand how sophisticated fraud rings operate and adapt — was engaged to construct synthetic claims specifically designed to evade detection: claims engineered to stay just under risk thresholds on each individual signal while still being fraudulent in combination, photos selected to avoid triggering the vision consistency check, documents formatted to avoid known forensic flags. This red-team exercise was scheduled quarterly, not once before launch, because the adversary is not static.

*Explicit acknowledgment of ground truth uncertainty:* Unlike the prior case studies' accuracy benchmarks — where a labeled clinical encounter or a labeled contract has a verifiable correct answer — fraud ground truth is fundamentally incomplete. Not all fraud is ever discovered; the dark figure of undetected fraud is, by definition, unmeasured. The evaluation framework was designed to be explicit about this limitation rather than presenting a recall figure as if it were precisely known. The reported metric was reframed: "recall against SIU-confirmed cases" (a measurable, honest figure) rather than "recall against all fraud" (an unmeasurable, overstated figure). This distinction was presented directly to the CCO and General Counsel as a governance matter, not a technical footnote — overstating confidence in fraud detection accuracy creates regulatory and reputational exposure if challenged in litigation.

**Decision 4: Fairness evaluation on the claims-handling side**

The credit bank engagement (Case Study 1) tested for fair lending bias in underwriting decisions. This engagement required a structurally similar but distinct test: does claims scrutiny — which lane a claim is routed to, how quickly it's processed, how often it's referred to SIU — correlate with protected class status or its proxies, independent of legitimate risk factors?

Constructed paired test cases varying claimant name (as an ethnicity proxy), zip code, and repair shop location while holding the underlying claim facts (damage type, accident circumstances, claim amount) constant. Result of the initial test: no significant routing disparity by name-based ethnicity proxy. A second test, however, surfaced a real issue.

**A prevented error — zip code as a fraud feature:**

During feature engineering, a data scientist proposed including claimant zip code as an input to the composite risk score, because exploratory analysis showed it was statistically predictive of fraud referral outcomes in historical data.

Requirements and fairness review intervened. Including raw zip code risked encoding historical patterns of disparate scrutiny — if certain zip codes had historically received more SIU referrals due to biased referral patterns rather than true differences in fraud prevalence, training on that history would launder the bias into the model and perpetuate it at scale, while appearing statistically justified. General Counsel's framing of the risk was direct: "If a Department of Insurance examiner runs the same test we just ran and finds a zip code correlation with no legitimate risk explanation, we have a redlining-adjacent problem in our claims handling — separate from and in addition to any underwriting issue."

Resolution: zip code was excluded as a direct model feature. Where geographic risk genuinely existed (e.g., regional patterns in staged-accident rings, documented and validated by SIU investigation outcomes rather than inferred from historical referral rates), the signal was instead derived from the graph-based entity resolution pipeline — actual documented connections between claims and known fraud network members — rather than from a geographic proxy correlated with, but not causally connected to, the underlying risk.

---

## Evaluation Framework

**Pre-deployment benchmark (vision and document pipelines):**

| Component | Metric | Target | Achieved |
|---|---|---|---|
| Vision consistency check | Precision (flagged mismatches confirmed by adjuster) | ≥ 85% | 88.3% |
| Vision consistency check | Recall (adjuster-identified mismatches also flagged by system) | ≥ 80% | 83.1% |
| Document forgery detection | Precision | ≥ 80% | 84.7% |
| Document forgery detection | Recall (against known forged-document test set) | ≥ 75% | 79.2% |
| Graph entity resolution | Entity match precision (confirmed shared entities) | ≥ 95% | 97.1% |

**Fraud detection evaluation (against SIU-confirmed cases, with explicit ground-truth caveat documented):**

| Metric | Pre-deployment baseline (existing process) | System (initial) | System (after Q2 red-team tuning) |
|---|---|---|---|
| SIU referral precision | ~62% (estimated from investigation outcomes) | 71% | 76% |
| SIU referral recall (vs. confirmed cases) | ~40% (estimated) | 58% | 67% |
| Average days to SIU referral | 11 days | 1.8 days | 1.6 days |

**Adversarial red-team results (quarterly cadence):**

Q1 (pre-launch): SIU team constructed 25 synthetic evasion-designed claims. System correctly flagged 18 of 25 (72%) as warranting additional scrutiny. The 7 missed cases informed targeted improvements to the graph entity resolution thresholds (several evasion attempts relied on slight name/address variations designed to avoid exact-match entity resolution).

Q2 (post-tuning): Re-ran an expanded set of 40 synthetic cases, including variants of the Q1 evasion techniques plus new ones. 34 of 40 (85%) correctly flagged. This cadence was established as an ongoing quarterly practice, not a pre-launch gate that, once passed, was considered permanently resolved.

---

## Pilot Design and Execution

**Phase 1 (Weeks 13–18):** Fast-track and Standard lanes deployed for 30% of auto claims volume (geographically split by region for clean comparison), SIU referral enhancement deployed system-wide (lower risk, higher value to deploy broadly immediately).

Week 2 finding: The vision consistency check was flagging a disproportionate number of false positives on claims involving older vehicles with significant pre-existing wear, which the model was sometimes confusing with claimed accident damage. Senior adjuster review identified the pattern; the vision model was retrained with an expanded training set emphasizing the wear-versus-impact-damage distinction. False positive rate on this category fell from 31% to 9% after retraining.

Week 5 finding: SIU referral volume increased 38% in the pilot region, which initially alarmed the Head of SIU — until investigation outcomes showed the increased referrals were confirming fraud at a higher rate than the existing baseline, not simply generating more noise. "We're not getting more false alarms. We're catching what we were always missing."

Week 7 finding: A junior adjuster, using the AI-surfaced document forensics flags, caught an altered invoice on her third week using the system — a forgery pattern (font inconsistency across line items) that, per the Session 2 observation, she would not have caught independently. This was the claims-side equivalent of the junior-to-senior parity effect observed in the grid operations and logistics case studies: AI-surfaced expert-pattern signals closed experience gaps for newer staff.

---

## Governance

**Audit trail:** Every routing decision, every flag, and every adjuster action (confirm, override, escalate) logged with timestamp and the specific evidence (vision flag, document flag, graph flag) that contributed to the routing decision — directly supporting General Counsel's stated need to demonstrate the basis for any claims decision in the event of regulatory inquiry or bad-faith litigation.

**Quarterly adversarial red-team:** Formalized as an ongoing governance requirement, not a one-time pre-launch activity, with SIU participation mandatory and findings reported to the CCO and General Counsel.

**Fairness monitoring:** The paired-testing methodology from discovery was operationalized as a quarterly recurring test, run by an analyst independent of the model development team, with results reported to General Counsel.

**State regulatory review:** Given the multi-state operation, General Counsel conducted a state-by-state review of unfair claims settlement practices acts to confirm the human-approval requirement for adverse actions was sufficient in every operating state, with two states (whose statutes had more prescriptive documentation requirements for claims handling timelines) requiring minor adjustments to the audit logging format.

---

## Outcomes (measured at 120 days post full deployment)

| Metric | Before | After |
|---|---|---|
| Average auto claims cycle time | 14 days | 6.2 days |
| Fast-track lane cycle time | N/A | 1.9 days |
| Claims leakage (annualized estimate) | $190M | $142M (−25%) |
| SIU referral precision | ~62% | 76% |
| SIU referral recall (vs. confirmed cases) | ~40% | 67% |
| Customer satisfaction (claims NPS) | 31 | 52 |
| Junior adjuster forgery-catch rate (sampled) | Low, untracked baseline | 71% of seeded test cases |
| Fairness paired-test disparities detected | N/A | 0 (post zip-code removal) |

The CCO's two seemingly contradictory board mandates — 25% leakage reduction and 50% cycle time reduction — were both achieved, because they had never actually been in tension once the underlying claims population was correctly differentiated.

