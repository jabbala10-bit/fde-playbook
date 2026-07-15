# Case Study 8: State Human Services Agency — AI-Assisted Benefits Eligibility Processing

## Engagement Context

**Client:** A mid-size U.S. state's Department of Health and Human Services administering four means-tested benefit programs: Medicaid (700,000 enrolled beneficiaries), SNAP (310,000 households), TANF cash assistance (41,000 households), and a state-funded housing assistance program (22,000 households). Combined program expenditure: approximately $5.8B annually.

**Engagement trigger:** The federal government's end of continuous Medicaid enrollment (the "unwinding" that began in 2023) triggered a requirement that all states redetermine Medicaid eligibility for every enrolled beneficiary — approximately 700,000 people — within 12 months. The department had processed an average of 18,000 eligibility actions per month under normal operations. The unwinding required approximately 60,000 per month for 12 months. Staff headcount had not increased. The backlog grew to 140,000 pending cases within 60 days of the unwinding start. The Secretary of the department, facing federal oversight letters and media coverage of low-income families losing coverage, brought in the Principal AI FDE team with a mandate she described in the first meeting as: "I need help processing cases faster without wrongly terminating anyone's benefits."

**Timeline:** 20 weeks from kickoff to initial deployment.

**Team:** Principal AI FDE (architecture, requirements, civil rights and due process analysis), 2 FDEs, 1 data engineer (eligibility system integration), the Deputy Secretary as executive sponsor, Director of Eligibility Policy, Director of IT, General Counsel, 4 senior eligibility caseworkers, 2 supervisors, the State Medicaid Director, and critically: a representative from the state's legal aid network (invited by the Principal AI FDE, not by the agency) whose organization regularly litigated against the agency in benefits termination disputes.

**What makes this engagement categorically distinct:** Government benefits programs are constitutionally constrained in ways private-sector software is not. Goldberg v. Kelly (1970) and Mathews v. Eldridge (1976) establish that before the government can terminate benefits a person relies on for basic sustenance, due process requires adequate notice, an opportunity to be heard, and an adjudication by a neutral decision-maker. These are not policy preferences — they are constitutional rights. An AI system that assists in, accelerates, or influences benefits termination decisions without satisfying these requirements creates constitutional exposure, not merely business risk. Additionally, federal civil rights law (specifically Section 1557 of the ACA for Medicaid, Section 3 of the Food and Nutrition Act for SNAP) prohibits program administration that has a discriminatory disparate impact on protected classes — meaning a system that routes determinations with differential accuracy or speed by race, national origin, disability status, or age is a federal civil rights violation regardless of intent.

The legal aid representative's invitation was the Principal AI FDE's single most consequential stakeholder decision in this engagement. It is standard practice in government AI deployments to consult only internal and vendor stakeholders. The people who most directly understand the failure modes of benefits administration AI — from the claimant's perspective, not the agency's — are the legal advocates who litigate the cases when the system fails. Excluding them from requirements development in a system affecting their clients is both epistemically poor and ethically questionable. Including them produced requirements that the agency's internal stakeholders, however well-intentioned, would not have surfaced.

---

## Initial Framing

Secretary's framing: *"Process more cases faster without wrongly terminating anyone."*

This framing was correct in spirit but contained a crucial ambiguity: "wrongly terminating" has two distinct meanings with different implications. One is technical accuracy — the system recommends termination when the person is actually eligible. The other is procedural adequacy — the system processes a case so fast that the required notice, right to appeal, and opportunity to provide additional documentation are compressed or bypassed. A system can be technically accurate (the person really isn't eligible based on the data available) and still constitute a procedural due process violation (because the person wasn't given adequate opportunity to provide documentation that would have established their eligibility). The difference between these failure modes was not intuitive to the technical team and required early, explicit surfacing in the requirements process.

---

## Discovery

**Stakeholder interviews (9 sessions):**

*Secretary:* "The federal oversight letters are explicit — we cannot have mass coverage loss from administrative errors. But I also cannot not act on the backlog. These are in tension."

*Deputy Secretary:* "Our caseworkers are working mandatory overtime and still falling behind. The morale problem is becoming a retention problem. I've lost four experienced eligibility workers this month alone."

*Director of Eligibility Policy:* "The rules are complex. Federal regulations plus state plan amendments plus court orders plus policy memos — a caseworker needs to know approximately 400 pages of policy to do this correctly. New caseworkers make errors. The experienced ones carry the institutional knowledge but they can't scale."

*Director of IT:* "Our eligibility system is the MMIS — Medicaid Management Information System. It's from 1998. The data model is not what you'd design today. We have fields that mean different things in different program contexts. I need you to understand that before you make any promises about what you can do with this data."

*General Counsel:* "Two things keep me up at night. First: if we use AI to make or substantially influence a benefits decision and we can't explain that decision in plain language to the beneficiary, we have a due process problem. Second: if this system produces differential outcomes by race or disability status that aren't explained by program eligibility factors, we have a disparate impact problem. I need both of those addressed architecturally, not in policy."

*Legal Aid Representative:* "The cases I litigate almost always have the same pattern: a beneficiary gets a notice that says 'your benefits have been terminated because you are no longer eligible,' they have no idea why, the evidence in the file doesn't support termination, and by the time it gets to me the person has been without Medicaid for three months and has delayed care consequences. The notice isn't descriptive, the caseworker can't explain the decision, and often nobody can tell me what information was relied on. If you automate any part of this process, every one of those problems gets worse unless you design specifically against them." [pause] "And one more thing — the households with the most complex situations are the ones with limited English proficiency, with disabilities, with irregular income. Those are the cases most likely to get it wrong, and they're also the cases where getting it wrong is most harmful. Whatever you build, it is going to be hardest for those people and easiest for the ones who need it least."

*Senior Caseworker (11 years):* "The parts I spend the most time on aren't the eligibility determination itself — I've done that enough times I know the rules cold. It's the documentation gathering: calling people to ask for missing documents, waiting for them to respond, chasing things down. If AI could handle any of that, it would help."

*New Caseworker (8 months):* "I'm worried about the policy complexity. My supervisor reviews my work, but she's got 60 cases to review this week. I know I'm making errors. I can feel when I'm not confident about something but I don't always know who to ask or where to look."

*State Medicaid Director:* "CMS is watching us very closely. Whatever we deploy has to pass muster in our federal-state relationship. They've sent guidance about AI in eligibility that I need you to read before we finalize anything."

**Contextual inquiry (5 sessions):**

Session 1 (Senior caseworker, routine Medicaid redetermination): Processing a household's annual Medicaid redetermination. The case involved a working family with variable income — a common complexity pattern. The caseworker spent 18 minutes navigating the MMIS, cross-referencing income reported against wage verification from a state database, reviewing previous case history, and calculating modified adjusted gross income (MAGI) against the CHIP and Medicaid thresholds. She completed the determination in 24 minutes total. Asked about the distribution: "The easy cases — a family whose income is clearly above or clearly below threshold — I can do in 8 minutes. The complex ones are 45+ minutes. The system lumps them all in the queue with no differentiation."

Session 2 (New caseworker, incomplete documentation case): Observed a case where the household had been sent a document request and had not responded. The caseworker was following up by phone — 3 attempts, no answer, sent a certified letter. Asked how long cases sat in this state: "Sometimes months. The backlog means nobody's chasing these aggressively. They just age out and get closed for non-cooperation, which often isn't fair — the person didn't understand what we needed."

Session 3 (Supervisor, error review): Observed a supervisor reviewing a new caseworker's batch of 12 decisions. She identified 2 errors — one a policy application error (wrong income calculation methodology for a self-employed household), one a documentation sufficiency error (accepting a document that was technically insufficient per policy). "Without review these would have gone out wrong. But I can only review so many files. When the backlog is this large, the quality control breaks down."

Session 4 (Legal aid observation — not the representative, a different organization contacted independently): Reviewed 3 open cases where the legal aid attorney was appealing benefits terminations. In each case, the attorney identified specific documentation in the case file that should have been sufficient to maintain eligibility but had either been overlooked or miscoded. Pattern: incomplete documentation of the determination rationale made it impossible for the beneficiary to construct an appeal without legal help.

Session 5 (IT systems walkthrough with Director of IT): Mapped the actual data available in the MMIS for each program. Key findings: income data was frequently 2–4 months stale (sourced from quarterly state wage records, not real-time). Address data had a 12% inconsistency rate between programs for households enrolled in multiple programs. Document imaging was inconsistent — some documents were machine-readable PDFs; others were photographs of documents taken on cell phones, at varying orientations and quality.

**Synthesis and reframe:**

The agency's framing was "process more cases faster." The correct framing, after discovery, had three distinct components:

1. **Straight-through processing acceleration** for genuinely simple cases (clear eligibility, complete documentation, no complexity flags): AI-assisted routing and documentation verification could safely accelerate these without risk.

2. **Caseworker decision support for complex cases**: Policy complexity and documentation assembly challenges were the primary causes of error and delay in complex cases. AI that surfaced the relevant policy provisions, flagged documentation sufficiency, and assembled context from the MMIS could reduce error rates and processing time simultaneously.

3. **Procedural adequacy infrastructure for every adverse action**: Every determination involving a potential benefit reduction or termination needed to be traceable, plain-language explainable, and documented in a form that supported the beneficiary's right to a meaningful appeal — regardless of AI involvement.

The legal aid representative's framing became the architectural forcing function: "Whatever you build has to produce a decision the beneficiary can understand and appeal." This was not a usability requirement. It was a constitutional due process requirement, and it constrained every component of the architecture.

---

## Requirements Documentation

**Functional Requirements**

*FR-01: Document Classification and Completeness Verification*
The system shall classify uploaded documents (income verification, identity documents, residency verification, disability documentation) by type and extract relevant data fields, and shall assess whether the submitted documentation meets the evidentiary requirements for each program determination type.

*FR-02: Case Complexity Routing*
The system shall classify incoming cases into processing tiers based on complexity indicators:
- Tier A (Straight-through eligible for AI-assisted fast track): single program, clear income above/below threshold, complete documentation, no complexity flags, no prior adverse action history
- Tier B (Caseworker-assisted with AI decision support): variable income, multi-program household, borderline income, incomplete documentation, prior appeal history, or any complexity flag
- Tier C (Experienced caseworker mandatory, no AI routing): cases involving disability determination, immigration status, domestic violence disclosure, active legal action, or any factor requiring individualized judgment outside of categorical rules

*FR-03: Policy Retrieval and Decision Support*
The system shall, for any case in Tier B processing, surface the relevant policy provisions, income calculation methodology, and documentation requirements applicable to the household's specific circumstances — retrieved from the verified policy document corpus.

*FR-04: Determination Rationale Documentation (Constitutional Requirement)*
The system shall, for every case where the AI-assisted process contributes to an adverse determination (reduction or termination of benefits), generate a plain-language rationale document meeting the following requirements:
- States in plain, accessible language (6th-grade reading level target) the specific reason(s) for the determination
- Cites the specific evidence relied upon (document name, relevant data point)
- States the specific program rule or regulation that was applied
- States what the beneficiary could do to appeal the determination, including the appeal deadline
- Contains no unexplained technical or legal jargon

This requirement, proposed by the legal aid representative and directly responsive to General Counsel's due process concern, was the single most structurally consequential functional requirement in the engagement. It drove the citation architecture, the output format, and the human review step — because a plain-language rationale document cannot be produced by AI alone for cases requiring individualized judgment.

*FR-05: Human Review Gate for Adverse Actions*
No AI-assisted determination resulting in a proposed benefit reduction or termination shall be finalized without caseworker review and explicit approval. The caseworker's approval action shall be logged with the full AI-generated rationale and the caseworker's identity and timestamp.

**Non-Functional Requirements**

*NFR-01: Disparate Impact Monitoring*
The system shall log all determination outcomes with demographic indicators (race/ethnicity, primary language, disability status, age) available from program enrollment data. A monthly disparate impact analysis shall compare determination outcomes and processing times by protected class. Any statistically significant disparity not explained by program eligibility factors shall trigger a mandatory review by the Director of Eligibility Policy and General Counsel before the next deployment cycle.

*NFR-02: Plain Language and Accessibility*
All beneficiary-facing outputs (notices, rationale documents, documentation request letters) shall meet a 6th-grade or lower reading level target, be available in the top 5 languages spoken in the state's beneficiary population, and comply with Section 508 (ADA) requirements for accessibility of electronic documents.

*NFR-03: Explainability Depth*
Every determination supported by AI shall produce a traceable evidence chain: specific document → specific extracted data → specific policy provision applied → specific outcome. This chain shall be retained in the case record and accessible to the beneficiary, their legal representative, and any fair hearing officer.

*NFR-04: Error Rate Targets*
Based on the current expert caseworker error rate of approximately 4.2% (measured by supervisor review sampling) and the legal aid representative's input on the harm asymmetry of false terminations vs. false approvals, the following targets were established:
- False termination rate (AI-assisted determination that terminates benefits a person is actually entitled to): ≤ 1.5% — substantially lower than the current human baseline
- False approval rate (AI-assisted determination that approves benefits a person is not entitled to): ≤ 3% — near the human baseline (the asymmetry is deliberate: the harm of wrong termination is far greater than the harm of wrong approval)

*NFR-05: Documentation Request Follow-up*
The system shall automatically generate follow-up communication (email and/or SMS where available, letter otherwise) for cases awaiting documentation, at defined intervals, in the beneficiary's preferred language, stating specifically what is needed and how to provide it.

**Civil Rights and Due Process Requirements**

*CR-01 (Due Process):* The system shall not contribute to any adverse determination without generating a plain-language rationale document meeting FR-04 standards. This requirement is non-waivable and takes precedence over any processing speed objective.

*CR-02 (Disparate Impact):* The system shall comply with the non-discrimination requirements of Section 1557 of the ACA, Section 3 of the Food and Nutrition Act, and the applicable provisions of the Fair Housing Act. Compliance shall be demonstrated through ongoing disparate impact monitoring per NFR-01, with results reported quarterly to the Secretary.

*CR-03 (Right to Appeal):* Every adverse determination notice produced with AI assistance shall contain accurate, plain-language information about the right to request a fair hearing, the deadline for doing so, and the process for obtaining free legal representation (per the state's legal services directory).

*CR-04 (Language Access):* Consistent with Executive Order 13166 and Title VI of the Civil Rights Act, all AI-generated beneficiary communications shall be available in the top languages spoken in the program population. Documents requiring translation shall be produced using human-reviewed translation templates, not automated machine translation deployed without human review.

---

## AI Architecture Decisions

**Decision 1: Hard tiering with no AI involvement in Tier C**

Tier C cases — disability determination, immigration status, domestic violence, active legal action — were excluded from any AI processing by architectural design. No AI-generated output, routing recommendation, or documentation flag was surfected for Tier C cases. The system simply identified a Tier C flag and routed to the experienced caseworker queue with the flag noted.

This was not a capability limitation. It was a principled boundary: these case types require individualized judgment that cannot be reduced to categorical rules, and the harm of AI error in these contexts (incorrectly routing a domestic violence case, misclassifying immigration status affecting eligibility) was severe enough that the efficiency gain did not justify the risk.

**Decision 2: RAG over the verified policy corpus with forward-reference resolution**

Policy retrieval followed the same architecture established in Case Study 4 (contract intelligence): RAG over a curated, versioned policy document corpus. The unique challenge here was the policy corpus structure: federal regulations, state plan amendments, court orders (consent decrees from prior litigation had modified some program rules), and operational memos existed as separate documents, and the operative rule for a given case might be the intersection of multiple overlapping sources, with a court order taking precedence over a state plan amendment that took precedence over a federal regulation.

The chunking and retrieval architecture was designed to preserve this precedence hierarchy, with source documents tagged by type (federal regulation / state plan / consent decree / operational memo) and the retrieval ranking logic applying precedence weighting such that a consent-decree-level policy provision always surfaced in the top-k results when applicable — regardless of recency or raw similarity score.

**Decision 3: Plain-language rationale generation with strict grounding requirements**

The FR-04 rationale document was the architectural heart of the due process compliance requirement. The generation prompt required:

```
SYSTEM: You are generating a plain-language benefits determination rationale 
for a beneficiary of [Program Name] in [State Name]. This document is a 
legal notice and must meet the following requirements:

1. Reading level: 6th grade or below (Flesch-Kincaid target ≤ 7.0)
2. Language: [Beneficiary preferred language]
3. Every factual claim must be supported by a specific piece of evidence
   cited in the CASE EVIDENCE section. Format citations as 
   [Document: {document_name}, Data: {specific_data_point}]
4. Every rule applied must be cited as [Rule: {policy_source}, {section}]
5. You must include the specific appeal right language provided in 
   APPEAL_LANGUAGE below — do not paraphrase or shorten it
6. You must not include any jargon, acronym, or technical term without 
   defining it in plain language immediately

CASE EVIDENCE: {structured_evidence_json}
POLICY PROVISIONS APPLIED: {retrieved_policy_chunks}
APPEAL_LANGUAGE: {state_standard_appeal_notice_text}
DETERMINATION OUTCOME: {outcome}

Generate the determination rationale document.
```

Every output was validated against: reading level (automated Flesch-Kincaid check), citation completeness (every factual claim must match an item in the evidence JSON), and appeal language inclusion (mandatory string match). Documents failing any validation were returned to the caseworker queue as "rationale incomplete — manual completion required" rather than sent.

**Decision 4: Disparate impact monitoring infrastructure built before deployment**

Before any case was processed by the system, the disparate impact monitoring infrastructure was fully operational. This was not a post-deployment add-on — it was a deployment prerequisite. The monitoring infrastructure was built in weeks 8–12, before the system processed a single live case, because General Counsel's position was direct: "If we deploy and then discover a disparate impact problem retroactively, we have a civil rights violation we knew was possible and did nothing to prevent in advance."

The monitoring logic used a Cochran-Armitage trend test for the primary analysis (comparing determination rates by race/ethnicity across the income distribution) plus a separate analysis comparing processing times by disability status (testing whether cases with disability flags were systematically processed more slowly, potentially implying constructive denial through delay).

---

## The Legal Aid Representative's Ongoing Role

The legal aid representative participated in three additional sessions after the initial discovery interviews: a requirements review session (reviewing the draft requirements document and surfacing two gaps), a pilot design review session (reviewing the proposed pilot methodology from the perspective of beneficiary harm if something went wrong), and a post-pilot review session (reviewing a sample of 50 cases processed through the system against their legal standards for adequacy of notice and rationale).

This is an unusual practice — a Principal AI FDE inviting an organization that regularly sues the client to participate in the system design. The rationale: the legal aid organization has the most complete information about how benefits determinations fail from the beneficiary's perspective. That information is essential for building a system that doesn't fail those people. The cost of excluding that perspective is borne by the beneficiaries, not by the agency — which makes including it an ethical obligation, not just a smart design choice.

The legal aid representative's post-pilot review finding: "The rationale documents are substantially better than anything I've seen this agency produce before. For the first time, I can look at a denial notice and immediately understand exactly what the agency relied on and what the beneficiary needs to challenge. That's a meaningful improvement in due process, not just speed."

---

## Pilot Design

**Phase 1 (Weeks 13–17):** Tier A straight-through processing for 15,000 cases (single-program Medicaid renewals for households well above threshold). No adverse actions — this first phase only fast-tracked approvals and renewals with no benefit change, zero risk to beneficiaries.

Week 3 finding: The document completeness check was generating "incomplete documentation" flags at a 34% rate — far higher than expected. Investigation revealed the classifier was flagging valid documents that were photographs at angles or in lower resolution than the training data. The classifier was retrained on a broader range of document quality conditions, reducing the flag rate to 11% (consistent with the actual incomplete-documentation rate estimated by senior caseworkers).

**Phase 2 (Weeks 17–20):** Added Tier B processing with caseworker decision support. FR-04 rationale document generation activated for all proposed adverse actions — reviewed by caseworkers before any notice was sent.

Week 19 finding — critical: The caseworker review step for Tier B adverse actions was taking an average of 23 minutes per case — substantially longer than the 8–12 minutes anticipated. Observation revealed the reason: caseworkers were not simply confirming AI-generated rationale documents — they were using them as a scaffold to do a more thorough review than they would have done without AI support, because the structured evidence presentation made it easier to spot gaps. This was not a workflow problem to be fixed — it was a quality improvement signal. The target was revised: Tier B processing time was expected to be longer than Tier A but meaningfully shorter than the current baseline for complex cases, while producing higher-quality documentation.

---

## Outcomes (measured at 90 days post full deployment)

| Metric | Before | After |
|---|---|---|
| Average case processing time (Tier A) | 8–12 min | 3.1 min |
| Average case processing time (Tier B) | 24–45 min | 18 min |
| Caseworker policy application error rate (sampled) | 4.2% | 1.8% |
| Cases requiring documentation follow-up successfully resolved | 41% | 68% |
| Rationale document adequacy (legal aid review sample) | Not previously measured | 94% met due process standard |
| Disparate impact findings (monthly monitoring) | N/A | 0 statistically significant disparities detected in 90 days |
| Backlog reduction (total pending cases) | 140,000 | 71,000 (−49%) |
| Beneficiary fair hearing requests (rate per 1,000 adverse actions) | Not previously tracked | 4.2/1,000 (trending data only) |

The backlog reduction of 49% in 90 days did not reach the full unwinding processing requirement, but combined with an emergency CMS-approved extension and a temporary staff augmentation, the agency met its federal oversight obligations for the first time since the unwinding began.

