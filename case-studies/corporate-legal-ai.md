# Case Study 4: Fortune 100 Corporate Legal — AI-Powered Contract Intelligence Platform

## Engagement Context

**Client:** A Fortune 100 consumer goods company ($31B annual revenue) with an in-house legal department of 85 attorneys and a contract portfolio exceeding 40,000 active agreements across customer contracts, supplier agreements, licensing deals, NDAs, joint venture agreements, and employment instruments.

**Engagement trigger:** The General Counsel had seen a competitor announce a legal AI initiative and received a board-level question: "What are we doing about AI in legal?" She commissioned a Principal AI FDE engagement to evaluate and build. The stated urgency was competitive — the actual urgency was different and only became visible in discovery.

**Timeline:** 22 weeks from kickoff to initial deployment.

**Team:** Principal AI FDE (architecture, strategy, requirements leadership), 2 FDEs (implementation), the GC as executive sponsor, 2 senior partners as domain leads, 4 associate attorneys as pilot users and subject matter experts, 1 IT security architect (data governance).

**What makes this engagement architecturally distinct:** Corporate legal work operates under professional responsibility rules that have no equivalent in other industries. An attorney's duty of competence (ABA Model Rule 1.1) means they cannot delegate judgment to AI. Their duty of confidentiality (Rule 1.6) means client data cannot be handled carelessly. Their duty of supervision (Rule 5.1/5.3) means they are professionally responsible for the work product of anyone — including AI systems — working under their direction. These are not compliance preferences. They are professional obligations that, if violated, expose the attorneys to bar disciplinary action. The architecture must make compliance with these obligations easy, not merely possible.

---

## Initial Framing

GC's request: *"We need AI to review our contracts. It should flag issues, summarize key terms, and help our associates work faster."*

This framing was coherent at a business level and almost entirely unspecifiable at a technical level. "Review contracts" encompasses at least five distinct workflows with different inputs, outputs, accuracy requirements, and user populations. "Flag issues" depends entirely on what constitutes an issue — which varies by contract type, business context, governing jurisdiction, and risk appetite. "Help associates work faster" is an outcome, not a requirement.

The first job of the Principal AI FDE was to decompose the initial framing into a requirements structure that could actually be built.

---

## Discovery

**Stakeholder interviews (9 sessions):**

*GC:* "The board is asking about AI. I need to demonstrate we're not behind. But I also won't put something in production that exposes our attorneys or our clients."

*Deputy GC (Litigation):* "I want AI for contract review in litigation — specifically finding provisions that are relevant to disputes. We spend thousands of hours searching contracts for indemnification clauses and limitation of liability caps during discovery. That's a specific, bounded problem."

*VP Associate General Counsel (Commercial):* "NDAs are killing us. We negotiate 15–20 per week. They're mostly the same. The junior associates who do them are wasting their careers on form documents. I'd like AI to handle first-pass review."

*VP Associate General Counsel (Supply Chain):* "Supplier contracts are complex. Force majeure clauses, minimum purchase commitments, IP ownership in co-development — these require senior attorney judgment. I'm skeptical AI gets these right."

*Senior Associate (3 years):* "I spend about 60% of my time reviewing contracts. Most of it is reading and making a checklist. The judgment calls are maybe 20% of the time. I'd love AI for the checklist part."

*Junior Associate (1 year):* "I'm often not sure what I'm looking for. I don't always know what a risky clause looks like. I worry I miss things."

*IT Security Architect:* "Our standard vendor security review takes 12 weeks. The legal data is some of the most sensitive we have. Any AI system touching active contracts needs to meet our Tier 1 data classification requirements. And it cannot go outside our Azure tenant."

*Outside Counsel Partner (interviewed for perspective):* "The firms I know that have deployed legal AI have had issues with the models confabulating case citations. That's a serious problem in litigation contexts. In transactional work it's less obvious but also less forgiving — a missed clause in a signed contract is a real liability."

*Paralegal Lead:* "The associates review contracts. But we do the initial intake — logging contracts, extracting key dates, filing. That's a lot of repetitive data entry. Nobody's asked us about that."

**Contextual inquiry (5 sessions):**

Session 1 (Junior Associate, NDA review): Observed a 1st-year reviewing a vendor NDA against the company's standard form. Time to complete: 1 hour 22 minutes. Significant time was spent re-reading the company's standard NDA to compare specific provisions. She produced a 14-point issues list. Asked how confident she was: "About 70%. I know I probably missed something." She had missed a provision on residual knowledge that a more senior attorney later flagged.

Session 2 (Senior Associate, Supplier Contract Review): Observed review of a manufacturing supply agreement. The attorney had a printed checklist of 31 items to evaluate. He worked through it methodically, annotating the contract PDF. Time: 3 hours 40 minutes. He was working on his 4th contract review that day. On the last one he said: "I'm getting tired. I'm less careful on these at the end of the day."

Session 3 (Litigation Associate): Searching 3,400 supplier contracts for indemnification clauses that might be relevant to a pending litigation. Using the DMS (document management system) full-text search — keyword-based. She was manually opening and reading contracts that matched the keyword "indemnif*". Time observed for 15 contracts: 2.5 hours. Estimated total time for 3,400 contracts: "months."

Session 4 (Paralegal, contract intake): Observed the intake process for new contracts arriving for legal review. Each contract required manual entry of 22 metadata fields (parties, effective date, expiration, governing law, contract value, etc.) into the DMS. Average time per contract: 18 minutes. Volume: 40–60 contracts per week. The paralegal was filling in fields she was not always confident in: "I put my best guess for governing law if I can't find it in the first two pages."

Session 5 (Deputy GC, contract dispute): The Deputy GC was trying to find the limitation of liability cap in a contract involved in an ongoing dispute. The contract was a 78-page MSA with amendments. Search in the DMS returned results for "limitation of liability" on 12 different pages. He was reading each one to find the operative cap. Time: 22 minutes. "This is a problem I have every week. I should be able to find a number in a contract in 30 seconds."

**Critical discovery finding:** "Contract review" was not one workflow. It was at least six:

| Workflow | User | Frequency | Accuracy Requirement | AI Suitability |
|---|---|---|---|---|
| NDA first-pass review | Junior associates | Daily (15–20/week) | High (near-standard forms) | Strong candidate |
| Standard clause extraction (dates, parties, values) | Paralegals | Daily (40–60/week) | Very high | Strong candidate |
| Issue checklist review for standard contracts | Associates | Daily | High | Moderate candidate |
| Complex contract risk review | Senior attorneys | Weekly | Very high | Weak candidate (AI assist) |
| Litigation contract search (clause-type, across portfolio) | Litigation team | Weekly | High (recall) | Strong candidate |
| Expert negotiation support | Partners/VPs | Case-by-case | Expert-level | Out of scope |

This matrix was the central output of the discovery phase. It showed that AI was a strong candidate for workflows 1, 2, and 5, a moderate candidate for workflow 3, a weak-assist candidate for workflow 4, and out of scope entirely for workflow 6. Building one system for all six would have produced one system that was mediocre at all of them.

---

## Requirements Documentation

The Principal AI FDE produced a formal requirements document before any architecture was specified. This was unusual in FDE engagements — requirements are often captured informally. In legal contexts, formal documentation served an additional purpose: it gave the attorneys a written specification they could review for professional responsibility compliance before any system was built.

**Functional Requirements by Workflow**

*FR-01: NDA Review Assistant*
- The system shall identify deviations from the company's standard NDA template in any uploaded vendor NDA
- The system shall categorize deviations as: (a) acceptable standard variation, (b) non-standard requiring attorney review, (c) non-standard requiring negotiation
- The system shall produce a structured issues list ordered by materiality
- The system shall not generate legal advice or recommend acceptance or rejection of any provision
- The system shall indicate which standard template clause corresponds to each identified deviation

*FR-02: Contract Metadata Extraction*
- The system shall extract and structure the following 22 metadata fields from any uploaded contract
- Accuracy requirement: ≥ 99% on unambiguous fields (party names, dates, governing law, contract value); ≥ 95% on interpretive fields (contract type, auto-renewal terms)
- The system shall flag fields where extraction confidence is below threshold for human verification
- The system shall populate extracted metadata directly into the DMS upon paralegal approval

*FR-03: Portfolio Search (Litigation Support)*
- The system shall accept a clause-type or concept query and return all contracts in the portfolio containing that clause type or concept
- The system shall rank results by relevance to the query
- Recall requirement: ≥ 95% of contracts containing the queried clause type must be returned
- The system shall provide a clause excerpt from each returned contract, with the relevant passage highlighted
- The system shall support Boolean combination queries (e.g., "indemnification AND IP ownership")

*FR-04: Checklist-Based Contract Review*
- The system shall apply a configurable checklist of review criteria to any uploaded contract
- The system shall return a structured assessment for each checklist item: present/absent/unclear/flagged
- The system shall provide the contract passage supporting each assessment
- The system shall not assess items on the checklist that require legal judgment (e.g., "is this limitation of liability cap commercially reasonable?") — those items shall be returned as "requires attorney review"

**Non-Functional Requirements**

*NFR-01: Data Residency and Privilege Protection*
- All contract data and AI processing must remain within the company's Azure tenant
- No contract data, attorney work product, or client information may be transmitted to external systems or third-party AI APIs
- The system must maintain an audit log of all data access, queries, and outputs
- Privilege protection: contracts subject to attorney-client privilege must be tagged and accessible only to authorized users; privilege tags must propagate through all AI-generated outputs

*NFR-02: Accuracy and Hallucination*
- The system must not generate legal citations, case references, or statutory citations unless those citations are retrieved from verified source documents in the system's knowledge base
- All legal propositions generated by the system must cite the specific contract passage or source document supporting them
- The system must flag any output where the supporting source document is not available in the knowledge base

*NFR-03: Attorney Oversight and Professional Responsibility*
- All AI-generated outputs must be labeled as AI-assisted and require attorney review before use
- The system must not represent itself as providing legal advice
- The system must maintain an audit trail demonstrating that attorney review occurred for each output used in legal work
- The system must make it easy, not merely possible, for an attorney to override, correct, or annotate any AI-generated output

*NFR-04: Explainability*
- For every flagged issue, deviation, or extracted field, the system must provide the specific contract passage supporting its output
- The system must not produce outputs without traceable supporting evidence from the contract under review
- "I don't know" and "this requires attorney review" are required valid outputs, not failure states

*NFR-05: Performance*
- NDA review: complete within 90 seconds of submission
- Metadata extraction: complete within 60 seconds per contract
- Portfolio search: return results within 30 seconds for a portfolio of up to 50,000 contracts

*NFR-06: Availability*
- System availability: ≥ 99.5% during business hours (M–F, 7 AM–10 PM local time)
- Degraded mode: if AI processing is unavailable, the document storage and retrieval functions must remain available

**Compliance Requirements**

*CR-01:* The system and its deployment must be consistent with ABA Model Rules 1.1 (competence), 1.6 (confidentiality), 1.15 (safeguarding client property), and 5.1/5.3 (supervisory obligations)
*CR-02:* The attorney oversight architecture must be reviewable by the company's professional responsibility counsel before deployment
*CR-03:* The system's AI-assistance disclosure mechanism must satisfy any applicable state bar rules on AI-assisted legal work (evaluated for all states where the company has admitted attorneys)
*CR-04:* Data handling practices must comply with the company's existing data classification policy, with contract data classified at Tier 1 (most sensitive)

---

## Requirements Conflicts and Resolution

Formal requirements documentation invariably surfaces conflicts — requirements that cannot simultaneously be satisfied. Identifying and resolving these conflicts before architecture begins is one of the highest-value functions of the Principal AI FDE requirements process.

**Conflict 1: Speed (NFR-05) vs. Comprehensive Review (NFR-04)**

FR-04 required that every checklist item be supported by a cited contract passage. For a 150-item review checklist on a complex 80-page contract, generating citations for every item drove processing time well above the 90-second target in NFR-05.

*Resolution:* The checklist was tiered. Tier 1 items (high-frequency, high-materiality: governing law, limitation of liability, IP ownership, termination for convenience) were processed first and returned immediately — target 45 seconds. Tier 2 items (important but lower frequency) were processed in a second pass — target 90–120 seconds. Tier 3 items (comprehensive coverage, lower materiality) were returned in a background job — target 5 minutes. Attorneys received a notification when all tiers were complete but could begin working from Tier 1 results immediately.

This satisfied both requirements through staged delivery: the speed requirement was met for the most-used items; the comprehensiveness requirement was met for the full checklist.

**Conflict 2: Recall (FR-03: ≥ 95%) vs. Precision (Alert Fatigue)**

Portfolio search required ≥ 95% recall — near-universal coverage of contracts containing the queried clause type. Achieving high recall typically requires a lower similarity threshold for retrieval, which increases false positives (contracts returned that don't actually contain the relevant clause). In litigation search, a large number of irrelevant results creates the same alert fatigue problem seen in the operational use cases.

*Resolution:* Tiered result presentation. The first result tier (top-10, high-confidence) was presented with full excerpt display for immediate review. A second tier ("Additional results — lower confidence") presented 10–50 more results in a collapsed view, accessible on demand. The recall target applied to the combination of both tiers; the precision target applied to the first tier only (≥ 85%). This gave litigation attorneys a fast, high-precision primary result set while preserving the recall coverage needed for comprehensive discovery work.

**Conflict 3: Accuracy (FR-02: ≥ 99% on unambiguous fields) vs. In-Scope Deployment Timeline**

The metadata extraction system required a 99% accuracy target on unambiguous fields. Achieving this on the existing contract portfolio — which included contracts drafted over 20+ years, some scanned from physical documents, some in non-English languages, and some with non-standard structures — would have required either a longer evaluation and remediation cycle than the deployment timeline allowed, or compromising the accuracy target.

*Resolution:* Scoped the ≥ 99% accuracy target to contracts processed after system deployment (newly ingested contracts). For the legacy portfolio backfill, a 95% accuracy target was established with a mandatory human verification step for the 5% flagged by the system as uncertain. The GC accepted this resolution after the tradeoff was presented: "We're not making the legacy extraction worse — we're making it better and flagging the uncertain ones for human review."

**Conflict 4: Privilege Protection (CR-04) vs. Portfolio Search Functionality (FR-03)**

Some contracts in the portfolio were subject to attorney-client privilege and could only be accessed by specific authorized users. Portfolio search needed to search across the full portfolio for litigation discovery purposes — but returning privileged documents to unauthorized searchers was a confidentiality violation.

*Resolution:* The privilege tag propagated through the retrieval layer. Portfolio search returned results from privileged documents only to users with the required authorization level. For unauthorized users, privileged documents appeared in the result count but with a placeholder: "1 additional result — access restricted (privilege). Contact [privilege custodian] for access authorization." This preserved the recall metric while enforcing privilege controls.

---

## AI Architecture Decisions

**Decision 1: Private deployment on Azure OpenAI / Claude API with enterprise terms**

NFR-01 (data residency, no external transmission) eliminated all consumer-grade AI APIs and required either a private cloud deployment or an enterprise API agreement with a contractual guarantee of data isolation. The team evaluated Azure OpenAI Service and Anthropic's enterprise API. Both met the data residency requirement. Claude was selected for the generation layer based on performance on legal document tasks in the evaluation benchmark (described below), with Azure OpenAI as a fallback.

**Decision 2: Hybrid architecture — structured extraction + RAG generation**

The six workflows had fundamentally different information extraction requirements:

- Metadata extraction (FR-02) required high-accuracy structured field extraction from defined fields — better served by a structured extraction approach than free-form generation
- Portfolio search (FR-03) required semantic similarity at scale across a large corpus — vector search
- NDA review and checklist review (FR-01, FR-04) required comparison of a document against a reference standard and generation of a structured issues list — RAG with template grounding

The architecture was therefore hybrid:

```
Document ingestion:
  All contracts → OCR pipeline (for scanned docs) → structured text
  → Metadata extraction model (fine-tuned, structured output, 22-field schema)
  → Clause segmentation (contract structure parser)
  → Clause embedding (text-embedding-3-large)
  → Vector store (Azure Cognitive Search)

NDA review workflow:
  Uploaded NDA → clause segmentation → clause embedding
  → Similarity search against standard NDA clause embeddings
  → Deviation detection (semantic difference scoring)
  → Classification (acceptable variation / non-standard / non-standard requiring negotiation)
    → Claude generation with deviation context and classification schema
  → Issues list with cited deviations

Portfolio search workflow:
  Query → query embedding → vector similarity search → re-ranking
  → Result tier assembly (high-confidence / lower-confidence)
  → Clause excerpt extraction from retrieved contracts

Checklist review workflow:
  Contract → clause segmentation → tiered parallel processing
  → Per-checklist-item: retrieval of relevant clause + assessment generation
  → Tier 1 immediate, Tier 2 90s, Tier 3 background
```

**Decision 3: Clause taxonomy co-design with attorneys**

The most consequential non-technical decision was the co-design of the clause taxonomy — the structured vocabulary used to classify contract clauses for both the checklist review and portfolio search systems.

An off-the-shelf legal clause taxonomy would have been faster to implement. It would also have used terminology that didn't match the legal department's actual practice or the company's risk framework. The Principal AI FDE commissioned a 3-day taxonomy co-design workshop with 4 attorneys (2 senior, 2 junior) and the Head of Contracts:

Day 1: Listed all contract clause types the team encountered. 140 items identified.
Day 2: Consolidated and hierarchically organized. Resolved disagreements about classification (e.g., is "limitation of liability" a subcategory of "risk allocation" or a top-level category?).
Day 3: For each clause type, defined: (a) what it is, (b) what a risky version looks like, (c) what a standard version looks like, (d) what "acceptable variation" means for this company's risk appetite.

The Day 3 output was the most valuable artifact of the engagement. It formalized the senior attorneys' tacit risk assessment framework into a specification that could be used for system evaluation, for training junior attorneys, and as the ground truth for accuracy measurement.

**Decision 4: No citation hallucination architecture**

The NFR-02 requirement (no citations without verified source) was enforced architecturally: the system prompt for all generation tasks explicitly prohibited the model from generating any legal citation, case name, statute reference, or regulatory citation that was not present in the retrieved context window.

```
SYSTEM PROMPT (all legal generation tasks):

You are a contract analysis assistant for [Company Name]. 
Your outputs will be reviewed by licensed attorneys.

STRICT PROHIBITION: You must never generate, infer, or fabricate:
- Case citations (Smith v. Jones, 2019)
- Statutory references (e.g., UCC §2-207, Cal. Civ. Code §1670.5)
- Regulatory citations
- Any legal authority not present verbatim in the context provided

If a legal principle is relevant but you do not have a source document citation 
in the provided context, do not mention the principle. Instead, write: 
"[Note for attorney: [describe the issue] — no source in current context]"

Every factual claim about the contract under review must include a verbatim 
excerpt from that contract as supporting evidence. If you cannot find a supporting 
excerpt, write "Passage not located — attorney verification required."
```

This prohibition was tested against 50 adversarial prompts designed to elicit citations during red-teaming. Pass rate: 98%. The 2 failures (one instance of a correctly stated but unsourced statutory principle, one hallucinated case name) were analyzed, and the system prompt was strengthened. Final red-team pass rate: 100% across 100 additional prompts.

---

## Evaluation Framework

**Benchmark construction:**

Working with the 4 pilot attorneys, assembled a benchmark of 200 contracts with manually verified ground truth:
- 80 NDAs (variety of vendor types, term lengths, deviations from standard)
- 60 supplier contracts (variety of industries, complexity levels)
- 40 customer contracts (MSAs, SOWs)
- 20 licensing agreements

For each contract, attorneys manually completed:
- Full metadata extraction (22 fields)
- NDA deviation list (for NDA subset)
- Checklist review against the co-designed taxonomy
- Portfolio search ground truth (tagged relevant provisions by clause type)

The benchmark was split 70/30 train/test. The 30% holdout was never used during development — only for final accuracy measurement.

**Accuracy results before deployment (holdout test set):**

| Workflow | Target | Achieved |
|---|---|---|
| Metadata extraction (unambiguous fields) | ≥ 99% | 98.4% |
| Metadata extraction (interpretive fields) | ≥ 95% | 94.1% |
| NDA deviation detection (recall) | ≥ 90% | 91.7% |
| NDA deviation classification accuracy | ≥ 85% | 86.2% |
| Portfolio search recall | ≥ 95% | 96.3% |
| Portfolio search precision (Tier 1) | ≥ 85% | 87.1% |
| Checklist item identification | ≥ 88% | 89.4% |
| Citation hallucination rate | 0% | 0% |

Metadata extraction missed the 99% target by 0.6 percentage points. The failures were analyzed: 8 of 11 errors were on contracts with non-standard date formats (dates embedded in body text rather than in standard positions). A targeted improvement to the date extraction module was made before deployment.

**Ongoing accuracy monitoring:**

Every AI output that was reviewed and modified by an attorney was logged with: the original AI output, the attorney's modification, and a required reason code (factual error / missed item / style preference / judgment call). This dataset served two purposes: ongoing accuracy measurement, and a continuous improvement signal for prompt and retrieval optimization.

---

## Pilot Design

**Phase 1 (Weeks 13–17):** 6 attorneys (2 senior associates, 4 junior associates), NDA review and metadata extraction only.

Week 2 finding: Junior associates were using the AI issues list as their complete review, not as a starting point. Senior attorney review of their work revealed that 3 of 12 reviewed NDAs had attorney modifications beyond what the AI had flagged — meaning the associates were not independently verifying AI outputs. This was not a system failure; it was an adoption behavior that violated NFR-03.

Response: The UI was modified to require a signed attestation from the reviewing attorney before the issues list could be submitted: "I confirm that I have independently reviewed this contract and that the issues list reflects my professional judgment, with AI assistance." The attestation was added as a required step, not an optional one. Attorney completion rate: 100% after implementation.

**Week 3 finding:** The Deputy GC (Litigation) was not in the pilot but asked to test the portfolio search tool informally. He ran a search for indemnification clauses across the full legacy portfolio of 38,000 contracts. The search returned results in 24 seconds. He found the operative indemnification clause in a disputed contract in 35 seconds total. His comment: "I spent 22 minutes doing this manually last week. I'm joining the pilot."

His voluntary entry into the pilot — and his specific comparison to the 22-minute manual task — became the most persuasive demonstration to the GC of the system's value.

---

## Governance and Professional Responsibility

Before deployment, the professional responsibility counsel reviewed the full requirements document, the system prompt, the attestation architecture, and the audit trail design. Her written sign-off:

"The system as designed is consistent with the company's professional responsibility obligations, provided that: (1) the attorney attestation requirement remains mandatory and non-bypassable, (2) the AI-assistance disclosure label is present on all outputs used in legal work, and (3) the audit log is retained per the company's standard matter file retention policy."

This written sign-off was archived as part of the deployment record. If a bar association or regulatory body ever questioned the legal department's use of AI, this document demonstrated that the use was reviewed by professional responsibility counsel before deployment.

---

## Outcomes (measured at 90 days post full deployment)

| Metric | Before | After |
|---|---|---|
| NDA first-pass review time | 1 hr 22 min avg | 18 min avg |
| Metadata extraction time per contract | 18 min (manual) | 2 min (AI + verification) |
| Portfolio search time (single clause type, full portfolio) | Hours/days (manual) | < 45 seconds |
| Junior associate confidence in review completeness | "~70%" (self-reported) | "~88%" (self-reported) |
| Senior attorney revision rate on associate NDA reviews | 34% of reviews required significant revision | 19% |
| Litigation discovery contract search backlog | 3,400 contracts (pending) | Completed in 4 days |
| Paralegal metadata entry error rate | 8.2% (sampled) | 1.4% (AI extraction + verification) |
| Citation hallucination incidents | N/A | 0 |
| Attorney attestation completion | N/A | 100% |

---

## Deep Dive: How Requirements Traceability Prevented Three Significant Errors

**Error prevented 1: Privilege exposure**

During development, an engineer proposed a "related contracts" feature — for any contract being reviewed, surface other contracts with the same counterparty. This would be useful for understanding the full relationship with a supplier or customer. The feature was technically straightforward.

Requirements traceability review: FR-03 (portfolio search) specified that privilege controls must propagate through all retrieval. The "related contracts" feature would retrieve documents without going through the privilege filter (it was a metadata-based retrieval, not the vector search pipeline that had privilege controls). A privileged contract between the company and an outside law firm could have appeared as a "related contract" in the results of any attorney.

The feature was rejected until privilege propagation could be implemented for the metadata retrieval path. It was added in a subsequent sprint after the fix was confirmed in testing.

**Error prevented 2: Confidentiality breach in AI prompts**

During prompt engineering, a developer included a sample contract in the system prompt as a few-shot example. The sample was a real contract — a major customer MSA — included from the test data set.

Requirements traceability review: NFR-01 required that no contract data be transmitted to external systems. The system prompt was transmitted to the AI API on every call. A real contract in the system prompt was being transmitted externally on every call.

The sample was replaced with a synthetic contract that contained no real party names, values, or terms. The incident was documented in the risk register and prompted a review of all test data handling to ensure no real contract data was used in development artifacts.

**Error prevented 3: Scope creep into legal advice**

A senior associate requested a feature: after flagging deviations, the system should recommend which deviations to "push back on" in negotiation. This was a reasonable business request.

Requirements traceability review: FR-01 explicitly stated "the system shall not generate legal advice or recommend acceptance or rejection of any provision." The recommendation feature was legal advice. NFR-03 required the system to "not represent itself as providing legal advice."

The feature was modified: instead of recommendations, the system provided a "comparable company positions" display — showing how the company had resolved similar deviations in previous contracts (retrieved from the historical contract database). This gave negotiators useful context without the system generating advice. It also created a new data product: a precedent database of the company's own negotiation history, which had not previously existed in structured form.

