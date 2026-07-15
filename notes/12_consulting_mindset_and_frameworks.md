# 12 — Consulting Mindset & Frameworks

> **Why this matters for FDEs:** Technical skill gets you in the door.
> Consulting skill keeps you there. The FDE who can only code is a
> contractor. The FDE who can also frame problems, communicate up,
> manage scope, and navigate politics becomes a trusted advisor —
> and gets invited back for the next engagement.

---

## 1. The McKinsey/BCG Problem-Solving Frameworks — Adapted for FDE

### The MECE Principle (Mutually Exclusive, Collectively Exhaustive)

When you analyze a problem or present options, your categories must:
- **Mutually Exclusive:** No overlap between categories
- **Collectively Exhaustive:** Together they cover all possibilities

```
NON-MECE (bad): 
  "The data quality issues are caused by the ETL pipeline, 
   the source system, and data entry errors."
  ← ETL pipeline and source system OVERLAP (ETL reads from source)
  ← "Data entry errors" could be in source system (not exhaustive separation)

MECE (good):
  "Data quality issues originate at one of three distinct layers:
   1. Source system layer (data captured incorrectly at origin)
   2. Transport layer (data corrupted/lost during extraction/loading)
   3. Transformation layer (data incorrectly processed in our pipeline)"
  ← No overlap. Exhaustive. Immediately actionable (check each layer).

FDE USE: Use MECE when structuring a discovery report, a root cause
analysis, or a presentation of solution options to a client.
```

### The Pyramid Principle — How to Structure Every Document

```
BOTTOM-UP THINKING (how you discover):
  Facts → Analysis → Insights → Recommendations

TOP-DOWN COMMUNICATION (how you present):
  Recommendation → Supporting Arguments → Evidence

EXAMPLE:
  DON'T:
  "We analyzed 3 months of data. We found 40% null rates in customer_id.
   We also found duplicate orders in 12% of records. The ETL job was
   found to have a bug introduced in the October release. We also
   discovered the source system has no PK enforcement. Therefore,
   we recommend..."
  
  DO (Pyramid Principle):
  "We recommend a 3-week data remediation sprint before building the AI layer.
   
   Our analysis identified two root causes:
   1. Source system: No PK enforcement → 12% duplicate orders
   2. ETL pipeline: October bug → 40% null customer_ids
   
   Evidence: [3 data quality charts here]
   
   Impact of not fixing: any AI model trained on this data will have
   misleading accuracy metrics and fail in production."
```

### The 3 Cs Framework — Problem Structuring
```
CONTEXT: What is the situation? (facts, background, constraints)
COMPLICATION: What has changed or what is the problem? (the tension)
RESOLUTION: What should be done? (the answer/recommendation)

EXAMPLE:
  Context: "Acme Corp's analysts spend 4 hours/day manually extracting
            data from three disconnected systems to create weekly reports."
  
  Complication: "The manual process introduces errors in 1 in 5 reports,
                 and two senior analysts have resigned, citing this work
                 as their primary frustration."
  
  Resolution: "Automating this workflow with our data pipeline and
               AI-assisted analysis will eliminate the manual work,
               reduce errors to near-zero, and save 80 analyst-hours
               per week — roughly $200K/year in productivity gains."
```

---

## 2. Stakeholder Management — The FDE Power Map

Every client engagement has a political landscape. Map it in the first 48 hours.

```
THE POWER/INTEREST MATRIX:

               LOW INTEREST        HIGH INTEREST
HIGH POWER  │  KEEP SATISFIED   │  MANAGE CLOSELY        │
            │  (executive        │  (Champion, Decision-  │
            │  sponsors who      │  Maker: weekly updates,│
            │  approved budget   │  seek alignment before │
            │  but aren't day-   │  major milestones)     │
            │  to-day involved)  │                        │
──────────────────────────────────────────────────────────
LOW POWER   │  MONITOR           │  KEEP INFORMED         │
            │  (peripheral       │  (End users, technical │
            │  stakeholders;     │  implementers: demo    │
            │  minimal effort)   │  progress regularly,   │
            │                    │  gather their feedback)│
```

### The Four Stakeholder Archetypes
```
THE CHAMPION (high power, high interest, ADVOCATE):
  → Your primary relationship. Invest the most time here.
  → Keep them ahead of information — never surprised in front of their peers
  → Arm them with talking points to defend the project internally
  → Warning sign: champion goes quiet → something political happened

THE BLOCKER (high power, variable interest, SKEPTIC):
  → Often IT Security, Legal, or a CIO who didn't choose this vendor
  → Never argue. Ask questions: "What would need to be true for this to
    meet your requirements?"
  → Address their specific concern directly. Get it in writing.
  → If blockers can't be resolved technically, escalate to your own AE.

THE SKEPTIC (low power, high interest):
  → Usually an analyst or engineer who preferred a competitor solution
  → Win them with technical depth: get into the code with them
  → If they become an ally, they become the strongest internal advocate
  → If they stay hostile, don't fight them — work around them

THE SHADOW INFLUENCER (low formal power, high informal influence):
  → The CFO's analyst, the CTO's EA, the "unofficial technical lead"
  → Often the most dangerous stakeholder to overlook
  → Find them by asking: "Who does [exec] typically listen to on tech decisions?"
  → Brief them the same way you'd brief the exec
```

---

## 3. The 5-Minute Briefing — Executive Communication

Executives give you 5 minutes, not 50. Structure accordingly.

```
THE FDE EXECUTIVE BRIEFING TEMPLATE:

1. STATUS (30 seconds)
   "We are ON TRACK / SLIGHTLY DELAYED / AT RISK for the [milestone]."
   One sentence. No ambiguity.

2. WHAT WE ACCOMPLISHED (60 seconds)
   "This week we completed:
    - Data pipeline now processing 500K records/day (previously 0)
    - AI agent correctly answers 87% of test questions (target: 85%)
    - Security review completed with no critical findings"
   Concrete. Measurable. Business-language, not tech-language.

3. WHAT'S NEXT (30 seconds)
   "Next week we will:
    - Complete user acceptance testing with 5 pilot users
    - Finalize production deployment plan"

4. WHAT WE NEED FROM YOU (60 seconds — this is the WHOLE POINT)
   "To stay on track, we need your help with:
    - Approval to access the Salesforce production API by Thursday
    - Confirmation of which 5 users will be in the UAT pilot
   If we don't have these by Thursday, we risk a 1-week delay."

5. HEADLINE METRIC (30 seconds)
   "The AI agent has now automated what previously took 3 hours/day.
   We're on track to deliver the projected $180K/year time savings."

TOTAL: 3-4 minutes. Leave 1-2 minutes for their questions.
```

---

## 4. Scope Management — The Contracts That Protect You

### The Statement of Work (SOW) — What to Include
```
A weak SOW is an FDE's worst enemy. When scope creep happens (it always does),
a well-written SOW is what protects both you and the client.

REQUIRED SECTIONS:
1. Project Objectives
   Specific, measurable: "Deliver an AI-powered document Q&A system capable
   of answering 85%+ of test questions from a curated golden set."
   NOT: "Improve the client's AI capabilities."

2. Scope of Work (detailed)
   What IS included — explicit bullet list
   What IS NOT included — equally explicit list
   Example not-in-scope: "Custom integrations with legacy Salesforce
   instance beyond the standard REST API; mobile app development;
   model fine-tuning on proprietary data beyond the agreed dataset."

3. Deliverables
   List every artifact: code repository, documentation, runbooks,
   training session, go-live deployment, 30-day support period.

4. Success Criteria (CRITICAL)
   "The project is considered successfully complete when:
   □ AI agent achieves ≥85% accuracy on the golden test set
   □ System handles 100 concurrent users at < 3s P95 response time
   □ All GCP infrastructure is provisioned via Terraform
   □ Client IT team has completed the 4-hour operations training
   □ All critical and high severity items from security review resolved"

5. Client Responsibilities
   What the CLIENT must provide:
   - Data access granted by Week 1, Day 3
   - Designated technical POC available for daily 30-min sync
   - UAT participants confirmed by Week 3
   - Security review process initiated by Week 1

6. Timeline with Milestones
   Week 1: Discovery complete; GCP landing zone provisioned
   Week 2: Data pipeline operational (Bronze + Silver layers)
   Week 3: AI agent prototype on real data
   Week 4: UAT and security hardening
   Week 5: Production deployment and handoff

7. Change Control Process
   "Any change to scope, timeline, or deliverables requires a written
   Change Request signed by [client name] and [vendor name] before work
   begins on the change."
```

### The Change Request Template
```markdown
CHANGE REQUEST #[n]
Date: [date]
Project: [project name]
Requested by: [client name]

PROPOSED CHANGE:
[Describe the new requirement or scope change]

RATIONALE:
[Why this change is needed]

IMPACT ANALYSIS:
- Schedule impact: +[X] business days
- Effort impact: +[Y] person-hours
- Cost impact: $[Z] (if applicable)
- Risk impact: [describe any new risks introduced]

REVISED DELIVERABLES:
[List any deliverables that change]

APPROVAL:
Client signature: _________________ Date: _______
Vendor signature: _________________ Date: _______
```

---

## 5. The Discovery-to-Proposal Workflow

```
DAY 1-2: ACTIVE LISTENING DISCOVERY
  □ Run a structured discovery call (see File 13 for questions)
  □ Shadow a user doing the manual process you're automating
  □ Ask to see the actual data (even one sample row)
  □ Map the stakeholder landscape (power/interest matrix above)
  □ Identify the "quick win" opportunity

DAY 3: SYNTHESIS
  □ Write up what you heard (draft Site Survey doc)
  □ Identify the top 3 constraints (technical, political, timeline)
  □ Identify the key assumptions that could break the project
  □ Define the MVP scope (smallest thing that proves value)

DAY 4: PROPOSAL STRUCTURE
  Use the 3Cs: Context → Complication → Resolution
  Show: current state → desired state → your proposed path
  Include: timeline, resource requirements, success metrics
  End with: "If we proceed, here's exactly what happens next week."

DAY 5: ALIGNMENT MEETING
  □ Present to Champion + Decision-Maker
  □ Walk through scope explicitly (especially what's NOT included)
  □ Get verbal confirmation of client responsibilities
  □ Ask: "What would make this proposal stronger?"
  □ Set a date for written approval/SOW signature
```

---

## 6. Communication Styles — Reading the Room

```
EXECUTIVE (C-suite, VP level):
  → Business outcomes, dollars, risks, and timelines ONLY
  → Never go below 3 levels of abstraction from the technology
  → "The AI system will reduce analyst time by 40%" not
    "The vector database retrieves semantically similar chunks"
  → If they ask a technical question: answer at one level deeper,
    then STOP and ask "Is that the level of detail you need?"

TECHNICAL MANAGER (Director/Senior Manager of Engineering):
  → Architecture, scalability, security, maintainability
  → Wants to know: "Will my team be able to maintain this?"
  → Show the system diagram. Explain the technology choices.
  → "We chose BigQuery over Postgres because at 10TB scale,
    BigQuery is 100x cheaper to query and requires no server ops"

INDIVIDUAL CONTRIBUTOR (Engineer, Data Analyst, Data Scientist):
  → Implementation details, code quality, APIs, documentation
  → Most critical validators: they will test your assumptions
  → Engage them early. Be willing to go deep.
  → "Here's the GitHub repo. Here's the README. Let me walk you
    through the architecture so you can own this after we leave."

THE FINANCE STAKEHOLDER (CFO, budget owner):
  → ROI, total cost of ownership, cost comparison vs. alternatives
  → Build a simple ROI model: current cost vs. projected cost
  → Address: licensing, infrastructure, maintenance, training costs
  → "The full 2-year TCO is $340K; current manual process costs
    $480K in loaded salary cost over the same period."
```

---

## 7. Handling Difficult Situations

```
SITUATION: Client says "We don't need your security recommendations."
  DON'T: Comply silently. You're now liable if there's a breach.
  DO: "I want to document in writing that I've flagged [specific risk]
       and the recommendation has been deferred at your direction.
       Can I send a follow-up email confirming this decision?"
  WHY: Creates a paper trail. Often causes the client to reconsider
       when they see the formal risk in writing.

SITUATION: Scope creep mid-project ("Can you also add X?")
  DON'T: Say yes to keep the relationship smooth.
  DON'T: Say no abruptly.
  DO: "I can absolutely add that. Let me understand the impact:
       adding X would push our current deadline by ~[N] days and
       require us to defer [existing feature]. Would you like to
       proceed with that trade-off, or should we log X in the
       backlog for a follow-on phase?"

SITUATION: Project is failing due to client-side delays
  DON'T: Wait and hope. Silence = complicity.
  DO: Write a formal "project risk notice" email:
      "I'm writing to formally flag that [specific blocker] has
       delayed us [N] days from the original schedule. If resolved
       by [date], we can still meet the [milestone]. If not resolved
       by [date], we will need to discuss a timeline revision."
  WHY: Creates urgency. Shifts accountability visibly to the right party.

SITUATION: Technical approach isn't working
  DON'T: Keep trying the same thing for 3 days hoping it'll work.
  DO: Flag it on Day 1 of knowing. "I've been trying [approach] and
      hit [specific blocker]. I have two alternative approaches —
      let me walk you through the trade-offs."
  WHY: Clients respect transparency and problem-solving. They don't
       respect being surprised by a failed approach at the last minute.
```
