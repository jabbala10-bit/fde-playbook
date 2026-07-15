# Case Study 9: Global Pharmaceutical — AI-Assisted Pharmacovigilance and Drug Safety Signal Detection

## Engagement Context

**Client:** A top-10 global pharmaceutical company with a marketed portfolio of 47 products spanning oncology, immunology, rare disease, and primary care, operating in 62 countries. Annual adverse event (AE) report volume: approximately 180,000 individual case safety reports (ICSRs) per year, received from healthcare providers, patients, clinical trial investigators, and medical literature mining.

**Engagement trigger:** The company's pharmacovigilance (PV) department had grown from 140 to 220 FTEs in three years in response to volume growth, with no corresponding improvement in processing cycle time — mean time from AE receipt to submission remained at 11 days for serious ICSRs (against a 15-day regulatory deadline, leaving a 4-day buffer that was regularly consumed by late-arriving supplemental information). Three regulatory commitments with FDA and EMA required the company to submit periodic safety update reports (PSURs) on defined schedules; two of the three most recent PSURs had been submitted with minor data quality findings that required corrective action plan documentation. The VP of Global Pharmacovigilance was directed by the Chief Medical Officer to evaluate AI for the PV function.

**Timeline:** 28 weeks from kickoff to initial Phase 1 deployment (the longest timeline in this case study series, driven by GxP validation requirements described below).

**Team:** Principal AI FDE (architecture, requirements, GxP validation framework), 2 FDEs, 1 data engineer (safety database and Oracle Argus integration), the VP of Global PV as executive sponsor, Director of Case Processing, Director of Signal Detection and Risk Management, 3 senior medical case assessors, VP of Regulatory Affairs, and critically: the company's GxP Validation Lead and Quality Assurance Director.

**What makes this engagement technically and regulatorily distinct from all prior case studies:** Pharmacovigilance operates under Good Pharmacovigilance Practice (GVP) guidelines issued by the EMA, FDA regulatory requirements under 21 CFR Parts 310, 314, and 600, and the ICH E2 series of international harmonization guidelines governing safety data collection, analysis, and reporting. Software used in GxP-regulated processes — including any AI system used to process or influence PV data — is subject to computer system validation (CSV) requirements: it must be formally validated before use through Installation Qualification (IQ), Operational Qualification (OQ), and Performance Qualification (PQ) protocols, and every change to a validated system requires a change control process that may require revalidation.

This is the only context in the entire case study series where the regulatory framework requires formal documented validation of the software system itself — not just evaluation of its outputs, but a structured protocol demonstrating that the system was installed correctly (IQ), performs its functions as specified (OQ), and produces accurate results in the intended use environment (PQ). The validation documentation must be maintained in an inspection-ready state and is subject to review by FDA and EMA during inspections and audits. Skipping or shortcutting CSV is not a technical decision — it is a regulatory compliance decision with inspection-finding consequences.

This validation requirement is why this engagement's timeline was 28 weeks rather than 16–22: 8 weeks of the timeline were validation protocol development and execution, with no shortcuts available.

---

## Initial Framing

VP of Global PV: *"We're drowning in case volume. I need AI to help my team process cases faster without compromising the quality of our safety data or our signal detection. And I need whatever you build to pass a regulatory inspection."*

This framing was accurate and well-calibrated — the VP understood the regulatory constraint from the outset. The decomposition required nonetheless: "process cases faster" collapsed at least four distinct processing steps with different accuracy profiles and different automation amenability, and "signal detection" was a separate analytical function with its own technical requirements, different in kind from case processing.

---

## Discovery

**Stakeholder interviews (8 sessions):**

*VP of Global PV:* "We have good people. The problem is volume, repetition, and the cognitive fatigue that comes from processing the thousandth very similar report. I'm worried we're missing safety signals not because our team is incompetent but because the volume-to-analyst ratio has gotten too high."

*Director of Case Processing:* "About 60% of our case volume is what I'd call mechanically complex but intellectually routine — they're serious reports that have to be entered, coded, and assessed, but the assessment is straightforward because the drug, the event, and the patient profile are all well within our known safety profile. Those are the ones where I wonder if AI could help. The other 40% are genuinely complex — new events, unusual patient profiles, suspected product quality issues. Those need expert eyes."

*Director of Signal Detection:* "The thing nobody tells you about pharmacovigilance signal detection is that most of it isn't dramatic. You don't get 'the drug causes heart attacks.' You get 'this statistical measure is slightly elevated for this preferred term in this age subgroup.' Deciding whether that's a signal or noise requires domain expertise, knowledge of the epidemiological background rate, knowledge of the drug's mechanism, and judgment about whether similar signals have been investigated before. I am genuinely worried about AI in this space — I've seen too many examples of naive signal detection finding patterns that are methodological artifacts."

*Senior Medical Case Assessor (14 years):* "I can look at an adverse event report and know within 30 seconds whether it needs careful attention or whether it's routine. Not because I'm extraordinary — it's pattern recognition from 14 years of looking at these. I think AI could learn some of those patterns. What I'm not sure it can do is recognize the report that looks routine but isn't — the one where something about the patient's history or the event sequence doesn't quite add up. Those are the ones that become important safety signals."

*VP of Regulatory Affairs:* "The FDA and EMA both have active AI guidance programs. The EMA published GVP Module VI guidance that touches on AI for signal detection. The FDA has issued draft guidance on AI in drug development. I need this system to be buildable in that regulatory environment, and I need it to be defensible in an inspection. That means validation, that means change control, and that means I need to know exactly what the AI is doing at every step."

*GxP Validation Lead:* "I've been asked to be part of this from day one because the earlier an AI system is built with validation in mind, the more efficiently it validates. Systems built without thinking about validation and then validated afterward are expensive and often require significant rework. I need the requirements to be specified in a format that can drive the validation protocols directly."

*Quality Assurance Director:* "For every significant change to a GxP system, we do an impact assessment. If this AI changes how cases are coded, how signals are detected, or how safety reports are generated, those are PV critical functions and require PV-level validation rigor. I need to understand the risk category of each AI component before I can tell you what level of validation it needs."

**Contextual inquiry (4 sessions):**

Session 1 (Medical case assessor, ICSR processing): Observed processing of a serious ICSR (serious adverse event — a hospitalization). The assessor's workflow: read the narrative, extract the critical elements (patient demographics, drug history, event characteristics, outcome), code the adverse event using MedDRA (Medical Dictionary for Regulatory Activities — the global controlled vocabulary for AE coding), code the drug product using the company's proprietary drug dictionary, complete the structured data fields in Oracle Argus (the safety database), assess causality (was the drug likely the cause of the event?), and write a narrative assessment. Total time: 47 minutes. "The coding is the most variable part. For an event I've seen a thousand times, I know exactly what MedDRA term to use. For an unusual presentation, I may search the MedDRA hierarchy for 10 minutes before I find the right term."

Session 2 (Signal detection analyst): Observed a weekly signal detection meeting review. The analyst had run a disproportionality analysis (PRR — Proportional Reporting Ratio — a standard pharmacoepidemiological signal detection method) across the previous week's case volume. He was presenting 3 elevated signals for the clinical review team's assessment. Two were assessed as "known association, no new information"; one was assessed as "possible new signal, requires further investigation." The time spent on the two known-association signals: approximately 20 minutes each. The time spent on the possible new signal: approximately 45 minutes. "The routine ones take just as long to properly document as the interesting ones. That's where I'd most want help."

Session 3 (Case processing, MedDRA coding workflow): Watched a newer assessor (2 years) navigate MedDRA coding for an atypical event presentation. She spent 12 minutes in the MedDRA browser, tried three different term hierarchies, ultimately selected a term. A senior assessor later reviewed the case and changed the coding to a more specific term. Asked about the frequency of such corrections: "Probably 15–20% of my coding on unusual events gets changed at review. For routine events it's under 5%."

Session 4 (Medical literature review): The medical literature team processed a weekly literature search alert (automated searches of PubMed and Embase for publications mentioning the company's products and adverse events). Volume: approximately 400 abstracts per week. The team manually screened all 400 for potentially relevant safety information. Of 400 abstracts reviewed, typically 5–8 required full-text retrieval and 1–2 required case entry. "We're screening 398 abstracts per week to find 2 that matter. If AI could do the initial screening confidently, it would free a significant amount of time."

**Synthesis:** The case volume consisted of four distinct workflow components with very different automation profiles:

| Workflow | Volume | Automation Suitability | Key Constraint |
|---|---|---|---|
| ICSR data entry and structured field extraction from source documents | 180,000/year | High for structured extraction | Data integrity, GxP validation |
| MedDRA coding assistance | 180,000/year | High for routine events; assist-only for novel presentations | Coding accuracy critical for signal detection |
| Causality assessment | ~72,000 serious cases/year | Assist-only; expert review required | Safety-critical judgment |
| Signal detection | Continuous/weekly | Assist-only; generate candidate signals, expert adjudication required | High risk of spurious signals |

Medical literature screening was a fifth component with strong automation potential: a binary classification task (relevant / not relevant for preliminary screening) with high volume and low per-unit harm from false negatives at the screening stage (because all abstracts flagged as relevant still received human review).

---

## AI Architecture Decisions

**Decision 1: GxP risk categorization drives validation requirements**

Working with the QA Director and Validation Lead, the AI system's components were categorized by PV function criticality before any architecture was finalized:

- **PV-Critical components** (validation per GAMP 5 Category 4/5): Any component contributing to data that flows into regulatory submissions (MedDRA coding, ICSR structured data, causality assessment). Required full IQ/OQ/PQ validation.
- **PV-Supportive components** (validation per GAMP 5 Category 3): Components supporting case processing efficiency without direct impact on regulatory submission data (literature screening classification, document classification). Required OQ/PQ validation, no IQ required.
- **PV-Administrative components**: Reporting and dashboard functions with no direct impact on safety data. Required only operational qualification.

This categorization was documented in the Computer System Validation Plan before development began, because changing a system's validation category after development — discovering that what was built as a PV-Administrative function actually touched PV-Critical data — requires either retroactive validation (expensive) or system redesign (more expensive). Building the categorization into the architecture from the start is the only economically rational approach.

**Decision 2: MedDRA coding as AI-assisted with mandatory human review, not AI-determined**

MedDRA coding is the single most consequential data element in pharmacovigilance. Incorrect coding — specifically, coding an adverse event at an overly generic term rather than the specific term that captures its medical character — can suppress signal detection: if 100 reports of a specific event are coded to 10 different MedDRA terms rather than the single most specific one, the signal may not reach statistical significance at any term even though all 100 reports represent the same underlying event.

The architecture therefore treated MedDRA coding as AI-suggested, human-confirmed — not AI-determined. The output was: a ranked list of the top 3–5 candidate MedDRA terms with the supporting text evidence from the narrative that drove each suggestion, presented to the assessor for selection. The assessor's selection was logged. The AI's suggestion was logged. Agreement rate between AI suggestion and assessor selection was tracked as a quality metric.

This architecture was deliberately conservative — a more aggressive approach could have made the top AI suggestion the default, requiring assessors to actively change it rather than actively confirm it. The conservative approach was chosen because: (1) default bias (Behavioral Economics, Part VI of the methodology document) would have made assessors less likely to change a presented default, meaning AI errors would pass through at higher rates; (2) the regulatory inspection risk of a system that "defaulted to" an AI coding suggestion was different from one where the human assessor "confirmed" a suggested term; the framing of human agency in the process mattered for regulatory defensibility.

**Decision 3: Signal detection as hypothesis generation, never hypothesis confirmation**

The Director of Signal Detection's concern (Session 2 and interview) was addressed architecturally by limiting the AI signal detection component to candidate hypothesis generation, with all confirmation and adjudication performed by the clinical and epidemiology team.

The signal detection architecture:
```
Safety database → disproportionality analysis (PRR, ROR, BCPNN — 
  standard pharmacoepidemiological methods, deterministic, auditable)
  → Candidate signal list: elevated signals above pre-defined thresholds

For each candidate signal:
  → Context retrieval: background rate literature, prior assessments of 
    this drug-event combination, similar historical signals and their outcomes
  → Claude-generated candidate signal summary: "This analysis identified 
    a PRR of [X] (95% CI: [lower, upper]) for [event] in [population subgroup] 
    with [drug]. This is above the pre-specified threshold of [Y]. 
    [N] cases contribute to this signal; the median time to onset is [Z].
    [Prior assessment context from retrieval]."
  → Routes to clinical signal assessment team for adjudication

The AI system does not assess, classify, or characterize signals as 
confirmed, refuted, or requiring label change. It generates the candidate
list and provides structured context for expert evaluation.
```

The Director of Signal Detection's exact words in the requirements review: "If the AI tells me 'this is a signal,' my team will over-weight that assessment even if they consciously try not to. If the AI tells me 'here are the numbers, here is the context, here is what similar patterns have looked like before,' my team will do the right thing with them. The AI should do the second thing, not the first."

**Decision 4: The validation documentation architecture**

The GxP validation documentation was designed in parallel with the system architecture — not after it. The Validation Lead's principle: "Every requirement must be in a format that can be directly traced to a validation test. If I can't write an OQ test case from a requirement, the requirement isn't specific enough."

This constraint forced a level of requirements specificity that was higher than any prior engagement in this guide. Example:

*Insufficiently specific requirement (rejected):* "The system shall suggest MedDRA terms accurately."

*Validation-traceable requirement (accepted):* "For ICSR narratives in the OQ test set, the system shall return the assessor-confirmed preferred term within the top-3 suggestions in ≥ 90% of cases. The system shall return the correct System Organ Class (SOC) as the top-ranked SOC in ≥ 97% of cases. Test set: 300 ICSRs with known correct MedDRA coding, spanning 12 therapeutic areas and 3 event complexity levels."

The Validation Lead's contribution was transformative for requirements quality: every requirement became testable because she refused to accept ones that weren't. The mutual discipline between requirements specificity and validation testability is one of the most productive feedback loops available in any GxP AI engagement.

**Validation protocols executed:**

*IQ (Installation Qualification):* Documented verification that the system was installed in the correct environment, with the correct software components and versions, connected to the correct data sources. Largely infrastructure-level verification. Duration: 2 weeks.

*OQ (Operational Qualification):* Tested each system function against its specified requirements using defined test cases. MedDRA coding: 300-case test set per the requirements. Literature screening: 500-abstract test set with known relevance labels. Signal detection: 6 months of historical safety data with known signal outcomes used as a retrospective validation set. Duration: 4 weeks.

*PQ (Performance Qualification):* Testing in the intended production environment, with representative production-level data volume, to confirm the system performs as required under actual operating conditions. Duration: 3 weeks (included a parallel-run period where AI outputs were evaluated against assessor decisions on live cases).

---

## A Prevented Error: The Literature Screening False Negative Risk

During OQ of the literature screening component, the test set included 8 cases of correctly published serious adverse events that had been deliberately seeded — papers in the training distribution that should have been flagged as relevant. The literature screening classifier correctly identified 7 of 8 (87.5%).

The QA Director's assessment was immediate: "One missed serious published adverse event in a seeded test of 8 is not acceptable for a PV-critical function. Either this component is not PV-critical and the missed case doesn't flow to regulatory submission, or the threshold needs to be significantly higher."

The classification resolved cleanly: medical literature screening is PV-critical because a missed relevant publication can mean a failure to identify a reportable safety signal. The recall requirement for the PV-critical category was raised to ≥ 98% on serious event abstracts. The model did not meet this threshold with the initial implementation. The component was reclassified as an alert-generation aid rather than a screening decision tool: instead of classifying abstracts as relevant/not-relevant (a binary that created a false-negative pathway), the system ranked all abstracts by relevance score and presented the full ranked list to reviewers with AI-assisted triage — the top 10% received priority review, the remainder were confirmed by the reviewer as not requiring full-text retrieval based on the ranking and a quick abstract scan. This eliminated the false-negative pathway entirely while preserving the efficiency gain of directing reviewer attention to the highest-priority items first.

---

## Outcomes (measured at 120 days post Phase 1 deployment)

| Metric | Before | After |
|---|---|---|
| Mean time from ICSR receipt to database entry | 4.8 days | 2.1 days |
| Serious ICSR processing cycle time (receipt to submission) | 11 days | 7.2 days |
| Days of buffer before 15-day regulatory deadline | 4 days | 7.8 days |
| MedDRA coding accuracy (AI top-1 suggestion confirmed by assessor) | N/A | 84% routine / 71% novel events |
| MedDRA coding corrections at QC review | 17% (baseline) | 9% (AI-assisted) |
| Literature screening — hours/week on abstract screening | ~12 hrs/week | ~3 hrs/week |
| Signal detection candidate list generation time | 2–3 hours/week | 22 minutes/week |
| GxP validation finding at subsequent inspection | N/A | 0 findings on AI system |
| PSUR data quality findings (next submission cycle) | 2 findings (corrective action required) | 0 findings |

