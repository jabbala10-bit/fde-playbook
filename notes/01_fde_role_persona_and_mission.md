# 01 — The FDE Role: Persona, Mission & Stack

> **What this file covers:** Everything you need to deeply understand the
> Forward Deployment Engineering role — what it is, how it differs from
> traditional SWE, what the day-to-day looks like, and the exact mindset
> shift required to succeed.

---

## 1. The Core Definition

A **Forward Deployed Engineer (FDE)** is a hybrid role — part Software
Engineer, part AI/Data Architect, part Strategic Consultant. FDEs are
embedded directly inside client organizations to bridge "The Delta":
the gap between what a product does out of the box and what a specific
client's messy real-world environment actually needs.

The term was pioneered by **Palantir** (see: "Dev vs. Delta" blog post),
but the pattern is now central to every enterprise AI company including
Google, Scale AI, Anthropic, Cohere, and dozens of others.

---

## 2. SWE vs. FDE — The Fundamental Difference

```
┌─────────────────────┬──────────────────────────────┬──────────────────────────────────┐
│ Dimension           │ Software Engineer (SWE)        │ Forward Deployed Engineer (FDE)  │
├─────────────────────┼──────────────────────────────┼──────────────────────────────────┤
│ User                │ Millions of anonymous users   │ High-stakes stakeholders:        │
│                     │                               │ CTOs, Generals, CEOs             │
├─────────────────────┼──────────────────────────────┼──────────────────────────────────┤
│ Environment         │ Controlled, uniform cloud     │ Hostile, legacy, air-gapped,     │
│                     │                               │ hybrid, or politically fraught   │
├─────────────────────┼──────────────────────────────┼──────────────────────────────────┤
│ Primary Goal        │ Scale and stability            │ Speed-to-value and problem-solving│
├─────────────────────┼──────────────────────────────┼──────────────────────────────────┤
│ Code Distribution   │ 90% Feature code              │ 50% Integration/Glue code        │
│                     │                               │ 50% Strategy/stakeholder work    │
├─────────────────────┼──────────────────────────────┼──────────────────────────────────┤
│ Success Metric      │ Uptime, latency, throughput   │ Business outcome achieved        │
│                     │                               │ (e.g., analyst saves 3hrs/day)   │
├─────────────────────┼──────────────────────────────┼──────────────────────────────────┤
│ Documentation       │ Internal wikis, RFCs          │ SOWs, PRDs, Executive Summaries  │
├─────────────────────┼──────────────────────────────┼──────────────────────────────────┤
│ Feedback Loop       │ Metrics dashboards, A/B tests │ Live client UAT, boardroom demos │
├─────────────────────┼──────────────────────────────┼──────────────────────────────────┤
│ Risk Profile        │ Technical debt, outages       │ Contract failure, trust erosion  │
└─────────────────────┴──────────────────────────────┴──────────────────────────────────┘
```

---

## 3. The "Delta" Concept — Your Core Mental Model

The **Delta (Δ)** is the engineering gap between:
- **Product Baseline:** What the software does for any generic customer
- **Client Reality:** What this specific client actually needs given their
  legacy systems, data formats, security requirements, and org structure

```
[Palantir/Google/Vendor Product]
        ↓ (The Delta = YOUR JOB)
[Client's Actual Working Solution]
```

**Examples of Delta work:**
- The product ingests JSON APIs. Client has COBOL batch files from 1987. 
  → You write the COBOL parser and adapter layer
- The product assumes clean data. Client has 40% null rates and no PKs.
  → You build the data quality pipeline
- The product runs on public cloud. Client is air-gapped DOD environment.
  → You architect the offline deployment with local container registry

---

## 4. The Modern FDE Stack — Memorize This

### Languages
```
Python  — Data pipelines, AI/ML, automation, scripting (90% of your work)
SQL     — Everything touching data. Window functions, CTEs, query tuning.
Go      — Infrastructure tooling, high-performance services, k8s operators
Bash    — Glue scripts, CI/CD, field automation
YAML    — Kubernetes manifests, Helm charts, Cloud Build pipelines
HCL     — Terraform for all GCP infrastructure
```

### Data Layer
```
dbt             — SQL transformation layer (the "software engineering for analytics")
DuckDB          — Fast local analysis of client CSVs/Parquets on a laptop
Apache Spark    — Distributed processing when data exceeds memory
BigQuery        — The GCP data warehouse for analytics at petabyte scale
Pub/Sub         — Real-time event streaming between client systems
Cloud Storage   — Landing zone for all raw data ingestion
```

### Infrastructure Layer
```
Terraform       — IaC to spin up the entire GCP landing zone reproducibly
Helm            — Kubernetes packaging (deploy agents as k8s workloads)
GKE             — Kubernetes on GCP (the standard runtime for production agents)
Cloud Run       — Serverless containers for lightweight APIs and integrations
Artifact Registry — Container image storage (critical for air-gapped deployments)
```

### AI/ML Layer
```
Vertex AI           — End-to-end ML platform (training, serving, evaluation)
Google ADK          — Multi-agent orchestration framework
Vertex AI Search    — Managed RAG engine with Google-quality retrieval
Vertex AI Agent Engine — Production runtime for ADK agents (auto-scaling)
LlamaParse          — Enterprise PDF/document extraction for RAG ingestion
LiteLLM             — Model-agnostic routing (GPT-4, Claude, Gemini via one API)
```

### Observability
```
Cloud Logging       — Centralized log aggregation (replaces your server SSH sessions)
Cloud Trace         — Distributed tracing for agent latency debugging
Prometheus          — Metrics collection (for GKE workloads)
Grafana             — Dashboards (metrics visualization)
LangSmith           — LLM/agent trace visualization and evaluation
```

---

## 5. The FDE Engagement Model — Chronological

### Week 1: Discovery & Trust Building
- Run the Site Survey (see File 13 and File 19)
- Data profiling audit on client source systems
- Stakeholder mapping: identify Champion, Blocker, Decision-Maker
- Technical constraint inventory: network, auth, compliance, quotas

### Week 2: Secure Landing Zone
- Provision GCP project with Terraform (see File 11)
- Set up VPC, IAM, VPC Service Controls (see Files 07, 10)
- First data ingestion: Bronze layer in Cloud Storage + BigQuery
- Quick Win: prove value with a simple query or search result on real data

### Weeks 3–4: The Delta Build
- Build the integration/adapter layer connecting client legacy system to GCP
- Construct data pipeline (Bronze → Silver → Gold via dbt)
- Prototype the AI component (agent, RAG, or prediction model)
- Daily check-ins with Champion; transparent blocker escalation

### Week 5+: Evaluation & Hardening
- Run inner-loop evaluation (ADK eval on golden datasets)
- Conduct UAT with actual end users (not just IT sponsors)
- Harden for production: encryption, least-privilege IAM, monitoring alerts
- Write the handoff documentation; train the client's "Run Team"

### Day 30: Horizon
- AutoSxS evaluation for production model
- Transition Day 2 operations to client internal team
- Executive Status Report showing measured business outcomes

---

## 6. The Three FDE Superpower Questions

Every skilled FDE asks these within the first 48 hours at a client site:

```
1. "What is the System of Record?"
   → Where is the ground truth data? If it's an Excel on someone's desktop,
     the project is already at risk. The answer tells you WHERE to build.

2. "What is the Cost of Inaction?"
   → If we don't build this, what happens per quarter/month? This defines
     the project's urgency, budget justification, and your leverage.

3. "What does Day 2 look like?"
   → Who maintains this once the FDE leaves? If no internal owner exists,
     the project will die after you leave. This tells you whether to build
     something simple they can maintain or escalate the staffing gap now.
```

---

## 7. FDE Red Flags — Escalate Immediately

These patterns reliably predict project failure. Surface them early.

```
🚩 "Data will be ready in 2 weeks."
   Reality: It never is. Get a data sample NOW, even if anonymized.
   Response: "Can we do a data profiling session today on a 1% sample?"

🚩 "We don't need a project manager on our side."
   Reality: The project will lose direction and the FDE becomes PM + Eng.
   Response: Escalate to your own account lead. Document this in the SOW.

🚩 "Can we just run this on-prem for now?"
   Reality: Deep distrust of cloud that will block every step.
   Response: Understand the root fear (security? cost? politics?). Address
   it directly with VPC SC + data residency controls, not by going on-prem.

🚩 "The data is all in SharePoint/email/PDFs."
   Reality: Unstructured data without a schema. Triple your time estimates.
   Response: LlamaParse + Vertex AI Search can handle this but scope carefully.

🚩 "Our IT team will handle the deployment."
   Reality: They will become the bottleneck and blame the FDE when it slips.
   Response: Get direct deployment access documented in the SOW from Day 1.
```

---

## 8. The FDE Trust Formula

From **The Trusted Advisor** (David Maister) — the most important
non-technical book for an FDE's career:

```
         Credibility + Reliability + Intimacy
Trust = ─────────────────────────────────────
                  Self-Orientation
```

- **Credibility:** You know your technical domain deeply
- **Reliability:** You do what you say you'll do, on time
- **Intimacy:** You understand the client's real fears and goals
- **Self-Orientation (minimize this):** Stop pushing your product's
  features; focus entirely on the client's outcome

**The FDE failure mode is high Self-Orientation** — pitching the
product instead of solving the problem. This destroys trust fast.

---

## 9. Productized Consulting — The Long Game

The ideal FDE engagement arc:

```
Month 1: Solve the specific client problem with custom glue code
Month 2: Observe which parts of the glue code OTHER clients would need
Month 3: Abstract the best glue into a product feature proposal
Result:  Your "custom work" becomes a core product feature, making the
         next 10 clients faster to onboard — this is "Productized Consulting"
```

This is how FDEs create leverage beyond their individual engagement.
Every custom piece of integration code should be written with this
question in mind: "Could this be parameterized and used by the next
client with a similar problem?"

---

## 10. Self-Assessment — Are You Ready for the Field?

Rate yourself 1–5 on each dimension. Any score below 3 is a preparation gap.

```
Technical Readiness:
  □ Can you explain a BigQuery EXPLAIN plan and identify a 10TB full scan?
  □ Can you provision a private GKE cluster with Workload Identity via Terraform?
  □ Can you build an ADK multi-agent system with tool-calling in < 2 hours?
  □ Can you set up VPC Service Controls for a BigQuery perimeter?
  □ Can you debug an agent's failed tool call using Cloud Trace?

Consulting Readiness:
  □ Can you run a discovery call and produce a Site Survey doc the same day?
  □ Can you say "that's out of scope, let me add it to the backlog" to a CEO?
  □ Can you turn a vague business problem into a Jira ticket with clear ACs?
  □ Can you write an Executive Status Report in under 30 minutes?
  □ Can you identify which stakeholder is the real decision-maker in 48 hrs?

Operational Readiness:
  □ Can you set up monitoring alerts for a new GCP deployment in < 1 hour?
  □ Can you write a runbook for the client's Run Team to handle common issues?
  □ Do you have a "break glass" plan for every critical dependency?
```
