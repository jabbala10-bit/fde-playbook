# Case Study 2: Clinical Documentation AI at a Regional Hospital Network

## Engagement Context

**Client:** A regional health system with 4 hospitals, 800 employed physicians, and approximately 1.2 million patient encounters annually.

**Engagement trigger:** An internal workforce survey showed physicians spending an average of 2.8 hours per day on EHR documentation — the highest reported figure in the health system's history. Physician burnout had driven 15% annual turnover over the previous 2 years, with exit interviews consistently citing documentation burden as the primary driver. The CFO calculated the replacement cost of physician turnover at $22M annually. The Chief Medical Officer had budgeted for an ambient AI documentation solution and evaluated three commercial vendors. They retained the Principal AI FDE team before making a vendor decision, specifically to design the deployment architecture and clinical validation protocol.

**Timeline:** 24 weeks from kickoff to Phase 2 deployment.

**Team:** Principal AI FDE (technical lead and deployment architecture), 1 FDE (integration and tooling), Chief Medical Information Officer (CMIO), 3 physician champions across specialties, clinical informatics team (EHR integration).

**What makes this engagement distinct:** The failure mode here is not a bad user experience or a missed SLA. It's a patient safety event. A hallucinated clinical finding in an AI-generated note — a medication dosage that wasn't mentioned, a diagnosis that wasn't made, a negative finding reversed to positive — can propagate through a patient's record and influence subsequent clinical decisions. The accuracy bar is categorically different from any of the other engagements in this guide.

---

## Initial Framing

CMO's request: *"We need to pick one of these three vendors and deploy it to 800 physicians as fast as possible. The burnout situation is urgent. Tell me which one to buy."*

This framing had two problems. First, it assumed the vendor selection decision could be made without a clinical validation protocol — which was wrong. All three vendors had published accuracy claims, but none had been benchmarked against this health system's patient population, specialty mix, or EHR configuration. Second, it assumed that deploying to 800 physicians simultaneously was the right approach — which was also wrong, for reasons that would become clear in discovery.

---

## Discovery

**Stakeholder interviews (8 sessions):**

- CMO: "I need this done. The burnout numbers are destroying us. I don't want to spend 6 months evaluating — I want to deploy."
- CMIO: "I'm worried about accuracy. I've seen demos where the AI made up a medication the patient wasn't taking. That would be a serious safety event."
- Primary Care Physician Champion: "I dictate my notes anyway. If the AI can do it better, I'm fine with that. My concern is that it needs to get the medications right, every time."
- Hospitalist Champion: "My notes are complicated — multiple problems, complex medication reconciliation. The demos I've seen are good for simple visits but I don't know how they'd handle a complex inpatient case."
- Surgeon: "I don't want AI writing my operative notes. Those are liability documents. I'll write those myself."
- Epic EHR Administrator: "The integrations are messy. Two of the three vendors have different levels of Epic certification. That matters for workflow."
- Malpractice Insurance Advisor: "The question is attestation. If a physician attests to an AI-generated note, they own it. Make sure they understand that before they start using it."
- Nursing Director: "Nurses document too, but nobody's talking about nursing documentation. The physician focus ignores half the documentation burden."

**Contextual inquiry (6 sessions, including full patient encounter observations):**

Session 1 (Primary care): Physician saw 24 patients in an 8-hour shift. Documented 18 during the shift (between appointments, in hallways). Completed the final 6 after leaving the clinic — starting at 6:45 PM, finishing at 8:20 PM. When asked what the post-shift documentation felt like: "This is the worst part of the job. I'm typing notes at 8 PM when I should be home with my family. And I'm tired, so the quality is lower."

Session 2 (Hospitalist, complex patient): Observed a 45-minute rounding encounter with a patient with 12 active diagnoses, 14 medications, and a complex social history. The physician dictated a note from memory and reference to the EHR. Note contained one error (a medication dose — caught by a pharmacist the next day) and one omission (a family history finding). Asked afterward: "The documentation is hard because I see 18–20 patients a day. By patient 15, I'm accessing memory that's several hours stale."

Session 3 (Surgeon): Confirmed the surgical note concern. "I will not have AI write my operative report. But I'd use it for pre-op and post-op notes. Those are more formulaic."

Session 4 (Observation of current documentation workflow): Identified 4 distinct documentation types with different complexity profiles:
1. Routine outpatient visit (simple, high-volume, best candidate for ambient AI)
2. Complex outpatient visit (multiple problems, moderate AI candidate)
3. Inpatient rounding note (high complexity, fragmented information, challenging for AI)
4. Procedural notes (operative reports, high liability, physician preference for manual)

**Critical discovery:** Physicians had significantly different documentation complexity profiles across specialties. A family medicine physician's average note complexity was categorically different from a hospitalist's. Deploying a single vendor solution across all 800 physicians, without specialty-specific validation, would produce excellent performance in some specialties and dangerous performance in others.

**Discovery reframe:** The CMO's urgency was real — but the right path was a staged deployment beginning with the best-candidate specialty/visit type combination, validated rigorously before expanding. Moving fast everywhere simultaneously was the highest-risk path, not the fastest path.

---

## AI Architecture Decisions

**Decision 1: Vendor evaluation protocol before selection**

The first architectural decision was procedural: before selecting a vendor, design and execute a clinical validation protocol. This decision cost 6 weeks and was the most contested intervention of the engagement. The CMO wanted to move immediately. The Principal AI FDE's position:

"If we deploy the wrong vendor and a physician attestation error causes a patient harm event, we will spend 18 months in remediation. Six weeks of validation is the faster path to sustainable deployment."

The argument was accepted. The validation protocol:

- Selected 100 transcribed patient encounters across 3 specialties (primary care, internal medicine, hospitalist)
- Encounters were de-identified and split into a validation set (70) and a holdout set (30)
- All three vendors generated notes from the transcripts
- Notes were reviewed by 6 physician reviewers (2 per specialty) blinded to which vendor produced each note
- Reviewers scored: factual accuracy (were all facts from the encounter correctly represented?), completeness (were any clinically significant facts omitted?), hallucination presence (did the note contain facts not supported by the encounter transcript?), and clinical usability (would you use this note with minor edits?)

**Validation results:**

| Metric | Vendor A | Vendor B | Vendor C |
|---|---|---|---|
| Factual accuracy | 94.1% | 96.8% | 91.3% |
| Completeness (no critical omission) | 88.2% | 93.4% | 86.7% |
| Hallucination rate | 3.8% | 1.2% | 6.1% |
| Clinical usability (≥ 4/5) | 71% | 84% | 63% |

Vendor B's hallucination rate of 1.2% was the decisive metric. In a health system with 1.2 million encounters annually, 1.2% hallucination rate represents approximately 14,400 notes per year with at least one hallucinated clinical fact — of which some percentage would propagate into patient records and clinical decisions.

The clinical advisory panel's position: even 1.2% was too high for inpatient documentation, where notes are relied upon by multiple subsequent clinicians. The recommendation was to deploy Vendor B for outpatient primary care visits (lower complexity, lower propagation risk) first, with more stringent human review requirements for inpatient settings pending further validation.

**Decision 2: Encounter type stratification**

Rather than deploying a single workflow for all documentation, the architecture stratified by encounter type:

*Tier 1 (Ambient generation, lightweight review):* Routine outpatient visits (primary care, preventive medicine, straightforward follow-ups). AI generates a draft; physician reviews and edits before attestation. Estimated 5–8 minutes of review per note vs. 15–25 minutes of drafting.

*Tier 2 (Ambient capture, structured review):* Complex outpatient and moderate inpatient encounters. AI generates a draft with flagged uncertainty sections (where the model's confidence was lower, flagged in the UI with a yellow highlight). Physician completes a structured review checklist before attestation. Estimated 10–15 minutes of review.

*Tier 3 (Ambient capture, physician-led composition):* High-complexity inpatient, surgical, and procedural notes. AI provides a structured transcript and key fact extraction but does not generate a complete draft. Physician writes the note with AI-extracted facts available as reference. Estimated savings: 30–40% on note drafting time through fact organization.

This stratification was more complex to deploy but was the correct clinical risk management architecture. A flat "AI writes the note, physician approves" approach would apply the same risk profile to a routine blood pressure check and a complex 12-diagnosis hospitalist note — which was not acceptable.

**Decision 3: Uncertainty signaling in the UI**

The hallucination risk required a UI intervention beyond standard review workflows. Working with the CMIO and physician champions, designed an uncertainty signaling system:

*Confident content:* Displayed in standard black text. Facts the model retrieved from the transcript with high confidence (direct speech acts, clear statements).

*Inferred content:* Displayed in dark blue text with a "⚠ inferred" tag. Facts the model derived from context (e.g., if a patient mentioned stopping a medication without explicitly saying why, the model might infer a side effect — flagged as inferred).

*Low-confidence content:* Displayed with a yellow background highlight and a "? verify" tag. Sections where the transcript was unclear, the encounter was complex, or the model's training data suggested lower reliability for this content type.

Physician feedback on uncertainty signaling during pilot: "This is the most useful thing. It tells me where to read carefully instead of making me re-read the whole note. My review time dropped from 12 minutes to 6 minutes because I know what to focus on."

**Decision 4: Attestation architecture**

The malpractice advisor's concern about attestation required a formal design response. The attestation UI was designed with explicit language that the physician was reviewing and taking responsibility for the content — not just clicking an "approve" button:

```
ATTESTATION STATEMENT (required before signing)

I, [Physician Name], have reviewed this note in its entirety. I have 
verified that all clinical facts, medications, diagnoses, and findings 
are accurate and complete to the best of my knowledge. I understand 
that this note was assisted by AI generation and that I am responsible 
for its clinical accuracy and completeness.

[ ] I have verified all sections marked "? verify"
[ ] I have reviewed all sections marked "⚠ inferred"  
[ ] I attest that this note accurately represents the clinical encounter

[Sign note]
```

The checklist was not optional. The "Sign note" button was disabled until all three checkboxes were completed. The completion state and timestamp were logged in the EHR audit trail.

---

## Evaluation Framework

The evaluation framework for this engagement required ongoing clinical quality monitoring, not just pre-deployment validation.

**Ongoing accuracy sampling:** A 2% random sample of all AI-assisted notes was reviewed by a clinical quality analyst each week. The sample was reviewed against the source encounter recording for: factual accuracy, clinical completeness, hallucination presence.

**Physician-reported accuracy incidents:** A "Report accuracy concern" button was available on every AI-assisted note. Physicians who found an error could flag it in 10 seconds. The flag captured: note type, encounter type, nature of concern (factual error / omission / hallucination / unclear), and the specific text in question.

**Monthly accuracy review:** CMIO, Principal AI FDE team, and vendor reviewed: accuracy sampling results, reported accuracy incidents, hallucination rate trend, time-savings metrics, and any near-miss or patient safety events.

**The safety threshold:** Defined before deployment and documented: if the ongoing hallucination rate exceeded 2% in any specialty tier for two consecutive measurement periods, that tier would be suspended pending investigation. This was a formal, board-reviewed deployment policy — not an informal agreement.

---

## Pilot Design and Execution

**Phase 1 pilot (Weeks 9–16):** 30 primary care physicians at 2 clinics. Tier 1 encounters only (routine outpatient). 4-week onboarding period, 4-week measurement period.

Onboarding design: Each physician received a 45-minute onboarding session covering: how the system works (not magic — it transcribes and drafts), what the uncertainty signals mean, attestation responsibilities, and how to report concerns. The session ended with a live demonstration of a deliberate error ("I'm going to show you what a hallucination looks like so you recognize it in practice") followed by correct physician review and correction.

This deliberate error demonstration was one of the most effective trust-calibration interventions in the engagement. Physicians who had seen what an error looked like were more diligent in their review — not more resistant to the technology.

**Phase 1 results:**
- Average documentation time reduction: 34% per encounter
- Post-shift documentation (after-hours documentation): reduced from 2.1 hours/day to 47 minutes/day
- Physician-reported accuracy: 4.1/5
- Accuracy incidents reported: 12 in 4-week period; 9 were confirmed genuine errors, 3 were physician preference disagreements (not factual errors)
- Hallucination rate (sampling): 0.9% — below the 2% threshold
- Unexpected finding: 4 physicians preferred not to use the system. Interviews revealed: 2 had personal workflows that were already efficient and didn't benefit significantly; 1 had privacy concerns about the ambient recording; 1 felt the AI-generated language didn't match their personal documentation style. All 4 continued to have access to the system but opted out of regular use. No pressure to continue was applied.

The 4 opt-outs were treated as valid data, not as failures. The system wasn't universally beneficial — and documenting the non-adopter population honestly was part of the Principal AI FDE's obligation.

---

## Outcomes (measured at 90 days, post Phase 2 expansion to 180 physicians)

| Metric | Before | After (Phase 2) |
|---|---|---|
| Avg daily documentation time | 2.8 hours | 1.7 hours |
| Post-shift documentation (after hours) | 2.1 hrs/day | 51 min/day |
| Physician satisfaction (documentation burden) | 2.4/5 | 3.9/5 |
| Hallucination rate (ongoing sampling) | N/A | 0.8% |
| Accuracy incidents (flagged per 1,000 notes) | N/A | 7.2 |
| Patient safety events attributable to AI documentation errors | N/A | 0 |
| Physician voluntary adoption rate (invited cohort) | N/A | 91% |
| Annualized documentation time recovered (180 physicians) | — | ~79,000 physician hours |

---
