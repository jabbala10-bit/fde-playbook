# 18 — Interview Blackbook: Case Studies & Answer Frameworks

> **Why this matters:** FDE interviews test three things simultaneously:
> technical depth, consulting judgment, and communication clarity.
> A great answer to "design a RAG system" shows architecture AND
> tradeoffs AND how you'd explain it to a non-technical executive.
> This file contains worked examples for every question type.

---

## 1. The FDE Interview Structure

```
ROUND 1: Technical Screen (45 min)
  - SQL/Python coding (1-2 problems)
  - Data modeling question
  - Basic GCP architecture question

ROUND 2: System Design (60 min)
  - "Design an AI system for [business problem]"
  - Expected: architecture diagram + component choices + tradeoffs
  - Tests: breadth of knowledge + ability to handle ambiguity

ROUND 3: Consulting/Behavioral (45 min)
  - "Tell me about a time you..."
  - "You're at a client and [difficult scenario]. What do you do?"
  - Tests: communication, judgment, stakeholder management

ROUND 4: Technical Deep Dive (60 min)
  - Deep technical questions on your background area
  - Live coding or debugging session
  - Architecture critique: "What's wrong with this design?"

ROUND 5: Case Study (sometimes)
  - Given a client scenario, present a solution recommendation
  - Tests: structured thinking, end-to-end problem solving
```

---

## 2. System Design Questions — Worked Examples

### "Design an Enterprise RAG System for a Legal Firm"

**The WRONG approach:** Jump straight to "We'd use LangChain with ChromaDB and GPT-4..."

**The RIGHT approach:**

```
STEP 1: CLARIFY REQUIREMENTS (first 5 minutes)
  Ask:
  - "What type of documents? Contracts, case law, internal briefs?"
  - "What are the latency requirements? Real-time Q&A or async?"
  - "What does 'accurate' mean here? Legal work requires precision."
  - "Who are the users? Lawyers, paralegals, or clients?"
  - "What compliance requirements? Attorney-client privilege? Data residency?"
  - "Current scale? How many documents? How many queries/day?"

Assumed answers:
  - Documents: contracts + case briefs + regulatory docs (~500K pages)
  - Users: 200 lawyers, real-time Q&A during casework
  - Accuracy: very high (wrong answer = malpractice risk)
  - Compliance: attorney-client privilege, data must not leave US
  - Scale: 5,000 queries/day peak

STEP 2: CONSTRAINTS FROM REQUIREMENTS
  These requirements imply:
  ✓ Private GCP deployment (US only) — no data to external LLMs
  ✓ Gemini via Vertex AI (stays in GCP) OR on-premise model
  ✓ Very high accuracy bar → reranker + citation + faithfulness checks
  ✓ Latency budget: < 5 seconds (lawyers can't wait 30s mid-call)
  ✓ Access control: lawyer A cannot see lawyer B's client files
  ✓ Audit trail: every query + response logged for liability

STEP 3: ARCHITECTURE WALKTHROUGH

  INGESTION PATH:
  [Legal Docs in GCS]
    → LlamaParse (handles complex legal PDF formatting)
    → Hierarchical chunking (preserve clause structure)
    → text-embedding-gecko@003
    → Vertex AI Search (managed, enterprise-grade)
    → BigQuery metadata store (for access control + audit)

  Why LlamaParse? Legal documents have complex table-of-contents,
  numbered clauses, cross-references. Generic chunking destroys structure.

  Why Vertex AI Search vs. BigQuery VECTOR_SEARCH?
  Vertex AI Search = managed, better retrieval quality, less infra to manage
  BigQuery VECTOR_SEARCH = more control, better if you need SQL joins
  For this client: Vertex AI Search (no infra burden; Google's ranking)

  QUERY PATH:
  [Lawyer's question]
    → Input guardrails (check for prompt injection)
    → Query embedding
    → Row-level security check (can this user access these documents?)
    → Vertex AI Search (top-20 candidates)
    → Cross-encoder reranker (ms-marco or Cohere Rerank)
    → Parent document fetcher (top-5 chunks → full clause context)
    → Gemini 1.5 Pro (large context, strong instruction following)
    → Citation enforcer (every claim must have [source: doc, clause])
    → Faithfulness checker (LLM-as-judge: is answer supported by context?)
    → Response to user

  ACCESS CONTROL:
  BigQuery row-level access policies per matter (case):
  - Lawyer on Case XYZ → can only retrieve chunks from Case XYZ docs
  - Implemented as metadata filter in Vertex AI Search call
  - All queries logged with user_id + matter_id for audit

STEP 4: TRADEOFFS AND ALTERNATIVES

  "I chose Gemini 1.5 Pro over Gemini Flash here because:
  - Legal work requires precision over speed
  - The client's error tolerance is very low (malpractice risk)
  - The extra 2 seconds per query is acceptable; a wrong answer is not
  
  If cost becomes a concern at scale, I'd implement a 2-tier approach:
  - Simple factual lookups: Gemini Flash + exact quote from context
  - Complex multi-document reasoning: Gemini 1.5 Pro
  
  I did NOT recommend fine-tuning here because:
  - The firm's specific documents can't be baked into model weights
  - Fine-tuning would help with style, not with retrieval accuracy
  - Better ROI from improving chunking and reranking than from fine-tuning"

STEP 5: PRODUCTION READINESS
  "Before go-live, I'd need:
  - 100-item golden dataset reviewed by a senior partner (domain expert)
  - Target: 90%+ pass rate on faithfulness + completeness
  - Load test: 5,000 concurrent queries for 10 minutes
  - Security review: VPC SC perimeter, pen test on prompt injection
  - Lawyer training: 2-hour session + documentation"
```

---

### "Design a Data Pipeline for a Retail Client with 10TB/day"

```
CLARIFYING QUESTIONS:
  - Source systems? (POS, eCommerce, ERP, CRM)
  - Downstream consumers? (BI dashboards, ML models, executive reports)
  - Latency requirements? (real-time inventory? T+1 daily analytics?)
  - Data quality confidence? (any known issues?)
  - Existing GCP footprint?

ARCHITECTURE:

  INGESTION (Bronze Layer):
  [POS → Pub/Sub → BigQuery Streaming Insert]  ← real-time transactions
  [eCommerce API → Cloud Functions (hourly) → GCS → BQ External Table]
  [ERP batch → SFTP → GCS → BQ External Table]  ← nightly batch

  Why Pub/Sub for POS? Real-time inventory accuracy.
  Why Cloud Functions for eCommerce? Lightweight; no cluster to manage.
  Why SFTP for ERP? Legacy system; this is the integration surface they offer.

  TRANSFORMATION (Silver Layer via dbt):
  dbt models: stg_pos__transactions, stg_ecommerce__orders, stg_erp__inventory
  Key Silver work: deduplication, type casting, NULL handling, standardization

  SERVING (Gold Layer):
  gold.sales.daily_revenue        ← BI dashboards (Looker)
  gold.inventory.stock_levels     ← inventory management app
  gold.ml.customer_features       ← ML feature store for recommendation model

  ORCHESTRATION:
  Cloud Composer (managed Airflow):
    00:00 UTC: ERP batch arrives → ingest Bronze
    01:00 UTC: dbt Silver transformation
    02:00 UTC: dbt Gold transformation
    02:30 UTC: Data quality checks (Great Expectations)
    03:00 UTC: BI dashboards refreshed; ML features available
    Alert: if any step fails → PagerDuty + client Slack

  DATA QUALITY GATES:
  Before Silver: expect_column_values_not_null on transaction_id
  Before Gold: row count check (alert if > 20% variance from prior day)

TRADEOFFS:
  "I chose Cloud Composer over Cloud Workflows here because:
  - Airflow gives us a visual DAG view the client team can understand
  - Easier to onboard the client's team to manage it after we leave
  - Downside: more expensive (~$300/mo) vs. Cloud Workflows (~$0)
  - Acceptable: client has $2M/year data budget

  For the 10TB daily volume, BigQuery handles this natively.
  I wouldn't introduce Spark/Dataproc here — it adds ops complexity
  without benefit when BigQuery can process 10TB in minutes at this cost."
```

---

## 3. Behavioral Questions — The STAR Framework

**S**ituation, **T**ask, **A**ction, **R**esult

### "Tell me about a time you had to push back on a client."

```
SITUATION:
"At [company], I was deployed to a healthcare insurance client who wanted
to build an AI system to automatically deny claims based on diagnosis codes."

TASK:
"I was asked to design and build the automated denial system within 3 weeks."

ACTION:
"After reviewing their use case, I identified two serious problems:
First, claims denial without human review violated CMS guidelines and exposed
them to significant regulatory risk — potential $1M+ fines.
Second, the training data they showed me was biased against specific diagnosis
categories, which would have compounded the fairness problem.

I scheduled a meeting with the CTO, the Chief Medical Officer, and the legal
team — not just the IT sponsor who hired me — to explain the risk.
I came prepared with:
  - The specific CMS regulation that would be violated (42 CFR 405.971)
  - Three recent enforcement actions from similar companies
  - A proposed alternative: AI-assisted review that flags claims for human
    decision (the AI supports the human, not replaces them)
  - A rough ROI showing the alternative still saves 60% of manual review time

The CTO initially pushed back — 'we're paying for AI automation, not AI-assisted.'
I held firm: 'I'm not able to build a system that exposes you to regulatory action
of this magnitude. Here's the alternative that delivers 80% of the value with
none of the legal risk. I'd rather have this conversation now than have your
legal team involved after a CMS audit.'"

RESULT:
"The CMO agreed with my risk assessment immediately. The CTO came around when
legal confirmed the regulation. We built the AI-assisted review system instead.
Three months post-launch, they reduced claim review time by 65% with zero
regulatory incidents. The CMO became our strongest internal advocate for the
next phase of AI work."

WHY THIS ANSWER WORKS:
- Shows principled pushback with specific facts (not just "gut feeling")
- Shows stakeholder escalation skill (went above the immediate client)
- Shows business judgment (proposed alternative, not just rejection)
- Shows resilience (held position when pushed back on)
- Shows measurable outcome
```

---

### "Describe a technically complex project you led."

```
SITUATION:
"I led the deployment of a multi-agent AI system for a pharmaceutical
company's regulatory document review process."

TASK:
"They needed an AI that could read new clinical trial protocols and
automatically cross-reference them against their existing library of
10,000 regulatory submissions to identify potential compliance conflicts.
Target: reduce their 3-week manual review process to under 2 hours."

ACTION:
"The technical challenge was three-fold:
1. Document parsing: clinical trial protocols are notoriously complex PDFs
   with statistical tables, references, and nested clauses. Standard chunking
   failed badly — we lost table context entirely.
   
   Solution: LlamaParse with pharmaceutical-specific parsing instructions,
   followed by hierarchical chunking that preserved table-as-unit integrity.
   We tested against 20 protocols manually extracted by a pharmacist.

2. The multi-agent architecture: a single LLM couldn't handle both the
   semantic search AND the regulatory interpretation logic well.
   
   Solution: ADK-based system with:
   - Document Retrieval Agent (Vertex AI Search over 10K submissions)
   - Conflict Analysis Agent (Gemini 1.5 Pro with 200K context — needed for
     long regulatory documents)
   - Summary Writer Agent (Gemini Flash — speed matters here)
   Orchestrator routes the protocol to all three; outputs are merged.

3. Accuracy validation: in pharma, a missed compliance conflict could delay
   a drug submission by 18 months and cost $100M+. Required 99% recall
   (we cannot miss real conflicts, even if it means more false positives).
   
   Solution: We built a 50-item golden dataset with the client's regulatory
   team. We tuned the retrieval top-K and reranking threshold until we hit
   99.2% recall at 87% precision — the client accepted this tradeoff.
   All flagged conflicts go to human review (AI-assisted, not AI-decided)."

RESULT:
"First document review completed in 23 minutes vs. 3 weeks manual.
99.2% recall confirmed on the golden set (vs. estimated ~80% for manual
review due to human error). The system is now in production, reviewed
their entire pipeline backlog of 200 protocols in the first 2 weeks.
Estimated ROI: $2.1M/year in analyst time plus faster-to-market timeline."
```

---

## 4. Technical Screening Questions — Rapid-Fire Answers

### SQL
```
Q: "What's the difference between RANK() and DENSE_RANK()?"
A: "RANK() leaves gaps after ties — 1,1,3,4. DENSE_RANK() has no gaps — 1,1,2,3.
    Use DENSE_RANK() when you want continuous ranking for things like
    'top 3 products' where you want exactly 3 distinct positions."

Q: "How would you find the second-highest salary in a table?"
A: "SELECT MAX(salary) FROM employees WHERE salary < (SELECT MAX(salary) FROM employees)
    Or more robustly: 
    SELECT salary FROM (SELECT salary, DENSE_RANK() OVER (ORDER BY salary DESC) AS dr FROM employees) WHERE dr = 2
    The window function version handles ties correctly and is more flexible."

Q: "What's the difference between WHERE and HAVING?"
A: "WHERE filters BEFORE aggregation — operates on individual rows.
    HAVING filters AFTER aggregation — operates on grouped results.
    Example: WHERE customer_tier = 'Gold' (filters rows) → GROUP BY region
    → HAVING SUM(revenue) > 100000 (filters aggregated groups)"
```

### Python/Data Engineering
```
Q: "What's the difference between map(), filter(), and reduce()?"
A: "map() applies a function to each element: map(lambda x: x*2, [1,2,3]) → [2,4,6]
    filter() keeps elements where function returns True: filter(lambda x: x>2, [1,2,3]) → [3]
    reduce() accumulates: reduce(lambda acc, x: acc+x, [1,2,3]) → 6
    In data engineering, I'd prefer list comprehensions or pandas/Spark operations
    over these built-ins for readability and performance at scale."

Q: "When would you use a generator vs. a list?"
A: "Generator when: processing large datasets that don't fit in memory,
    streaming data, or when you don't need all results at once.
    A generator yields one item at a time (lazy evaluation).
    List when: you need random access, need to iterate multiple times,
    or the dataset is small.
    Example: reading a 100GB CSV file — use generator to process line by line
    rather than loading the whole file into memory."

Q: "What is DataFrame partitioning in Spark and why does it matter?"
A: "Partitions are the unit of parallelism in Spark — one partition per task.
    Too few partitions: executors are underutilized (can't parallelize)
    Too many partitions: overhead from task scheduling exceeds compute benefit
    Target: 100-200MB per partition.
    Skewed partitions (one has 100x more data than others) = one task takes
    10x longer than all others — the 'straggler' problem. Fix with salting
    or AQE skew join handling."
```

### GCP Architecture
```
Q: "When would you use Cloud Run vs. GKE?"
A: "Cloud Run: stateless workloads, variable/spiky traffic, simple HTTP APIs,
    event-driven functions. I want zero ops overhead and auto-scale to zero.
    GKE: stateful workloads, GPU requirements, complex multi-container apps,
    when I need fine-grained control over networking or scheduling.
    For most FDE AI deployments: Cloud Run for lightweight APIs and webhooks,
    GKE for production agents with persistent connections and GPU inference."

Q: "Explain the difference between Pub/Sub and Cloud Tasks."
A: "Pub/Sub: publish-subscribe messaging. One publisher, potentially many subscribers.
    Best for fan-out (one event triggers multiple consumers), streaming, event-driven
    architectures. At-least-once delivery. No guaranteed ordering (by default).
    
    Cloud Tasks: task queue with explicit HTTP dispatch. One producer, one target.
    Best for rate-limited API calls, retry control, scheduled future execution.
    You control exactly when each task is executed and can limit concurrency.
    
    Example: ingest event → Pub/Sub → trigger RAG pipeline (Pub/Sub)
             Rate-limit Vertex AI API calls → Cloud Tasks (controls concurrency)"
```

---

## 5. The "What Would You Do?" Scenarios

### Scenario: "Day 3 at a client — data access still not granted"
```
WRONG ANSWER: "I'd keep waiting and work on other things."

RIGHT ANSWER:
"First, I'd clarify the blocking reason: is it technical (no credentials yet),
procedural (waiting on an IT ticket), or political (someone blocking it)?

If technical: I'd work with the IT contact directly to provision access,
offering to write the Terraform for the IAM bindings myself.

If procedural: I'd ask the Champion to expedite the ticket with a specific
business justification — 'Day 3 delay means we can't hit the Week 2 milestone
the CMO committed to the board.'

Meanwhile, I wouldn't sit idle:
- Set up the GCP landing zone (doesn't need data access)
- Build the schema and dbt models based on documentation + schemas
- Create synthetic data that mirrors the production schema structure
- Write data quality test definitions ready to run when access arrives

And I'd send a formal written status update to the project record:
'Data access is currently blocked, currently estimated at Day [X].
This creates a risk to the Week 2 milestone. Mitigation: working on
infrastructure provisioning and synthetic data pipeline in parallel.
Please confirm data access by [date] to preserve the project schedule.'"
```

### Scenario: "The client wants to use a competitor's product for one component"
```
WRONG ANSWER: "We should convince them to use our entire stack."

RIGHT ANSWER:
"My job as an FDE is to solve the client's problem, not to sell our product.
If a competitor has a genuinely better tool for a specific component, I should:

1. Understand WHY they want the competitor tool. Often it's familiarity or a
   prior relationship, not a technical superiority assessment.

2. Do an honest comparison:
   - What does the competitor do better for THIS specific use case?
   - What integration complexity does mixing stacks add?
   - What does the client's team already know and can maintain?

3. Present the tradeoffs honestly:
   - 'The competitor's tool has better [specific feature]. Our equivalent
     has [different strength]. For your use case specifically, here's how
     I'd evaluate them...'

4. If the competitor tool is genuinely better: recommend it.
   My credibility with the client is worth more than any single product sale.
   A client who trusts me will bring us back for the next project.
   A client who feels pushed into the wrong tool will not.

5. Document the recommendation in writing so the decision is explicit."
```

---

## 6. Questions to Ask the Interviewer

These questions signal senior thinking. Ask 2-3 at the end.

```
ABOUT THE ROLE:
"What does a successful first 90 days look like for this FDE role?"
"What's the most technically complex client situation an FDE here has faced?"
"How do you balance FDE time between customer-specific work and productizing insights?"

ABOUT THE CULTURE:
"How does the FDE team share knowledge across engagements?"
"When an FDE identifies a product gap from a client, what's the path to influencing the roadmap?"
"What's the biggest thing an FDE can do to accelerate their career here?"

ABOUT THE TEAM:
"What's the ratio of FDEs to SEs on a typical engagement?"
"How is the FDE assigned to a client — by industry, by geography, by technology?"
"What technical training is provided for new FDEs?"
```
