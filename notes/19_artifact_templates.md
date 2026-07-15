# 19 — Artifact Templates

> **Why this matters for FDEs:** Your artifacts outlive your engagement.
> A well-written SOW protects you from scope creep. A clear runbook
> enables the client to operate independently. A polished status report
> gets you invited back for the next project. These templates are
> production-ready — copy, fill in the blanks, and customize.

---

## ARTIFACT 1: Statement of Work (SOW)

```markdown
# STATEMENT OF WORK
**Project:** [Project Name]
**Client:** [Client Organization]
**Vendor:** [Your Company]
**FDE Lead:** [Your Name]
**Version:** 1.0
**Date:** [Date]

---

## 1. Project Overview

### 1.1 Background
[2-3 sentences describing the client's current situation and why this
project is being initiated. Reference the business problem, not the
technology solution.]

Example:
"Acme Corp's loan origination team currently spends an average of 4 hours
per loan application manually reviewing supporting documents against their
compliance checklist. This manual process results in a 3-business-day
average review cycle, limiting monthly loan capacity to 500 applications."

### 1.2 Project Objective
[One or two sentences defining the specific outcome this project will achieve.]

Example:
"This project will deliver an AI-assisted document review system that
reduces average review time to under 30 minutes while maintaining 100%
compliance checklist coverage, enabling a target capacity of 2,000
applications per month."

---

## 2. Scope of Work

### 2.1 In Scope
The following deliverables and activities are included in this engagement:

**Phase 1: Discovery & Infrastructure (Week 1)**
- [ ] Conduct technical discovery sessions with client data, IT, and business teams
- [ ] Complete and deliver Site Survey document
- [ ] Provision GCP project with Terraform-managed infrastructure:
  - VPC with Private Google Access
  - IAM service accounts with least-privilege roles
  - BigQuery datasets (Bronze, Silver, Gold layers)
  - GCS buckets for raw data and artifacts
  - GKE cluster (n2-standard-4, 2-10 nodes autoscaling)
  - VPC Service Controls perimeter (dry-run mode)
- [ ] Establish CI/CD pipeline in Cloud Build

**Phase 2: Data Pipeline (Weeks 2-3)**
- [ ] Build document ingestion pipeline:
  - LlamaParse integration for PDF/DOCX extraction
  - Chunking and embedding pipeline
  - Vertex AI Search datastore population
- [ ] Build Bronze → Silver → Gold medallion architecture via dbt
- [ ] Implement data quality checks (Great Expectations)
- [ ] Deliver Data Dictionary document

**Phase 3: AI System Build (Weeks 3-4)**
- [ ] Design and implement multi-agent system using Google ADK:
  - Document search agent (Vertex AI Search)
  - Compliance checklist agent (structured output)
  - Orchestrator agent (routing and synthesis)
- [ ] Implement RAG pipeline with citation grounding
- [ ] Build evaluation framework with 100-item golden dataset
- [ ] Achieve ≥85% pass rate on golden dataset evaluation

**Phase 4: Hardening & Go-Live (Week 5)**
- [ ] Security review: resolve all Critical and High findings
- [ ] Enforce VPC Service Controls perimeter
- [ ] Performance testing: 50 concurrent users, P95 latency < 5 seconds
- [ ] Conduct User Acceptance Testing (UAT) with 5 designated pilot users
- [ ] Produce all handoff artifacts (Runbook, Architecture Doc, Admin Guide)
- [ ] Deliver 2-hour operations training to client Run Team
- [ ] Production deployment and go-live support

**Ongoing (30 days post go-live)**
- [ ] Monitor system health and respond to P1/P2 incidents
- [ ] Weekly check-in calls with client technical POC
- [ ] Address up to 10 bug reports from UAT/production

### 2.2 Explicitly Out of Scope
The following are NOT included in this engagement:

- Mobile application development
- Integration with [specific system not listed above]
- Fine-tuning or training custom AI models
- Data migration from legacy systems not identified during discovery
- Ongoing managed services beyond the 30-day post go-live period
- Changes to client's existing authentication systems
- Development of custom reporting dashboards beyond the standard monitoring
  dashboard included in deliverables

### 2.3 Assumptions
This SOW is based on the following assumptions. Changes to these assumptions
may require a Change Request:

1. Client will provide data access as specified in Section 4 by the dates listed
2. The document corpus for AI ingestion does not exceed 100,000 documents
3. Documents are in English language
4. Client has an active GCP Organization with billing configured
5. Client's IT team will complete security review within 10 business days
6. A designated technical POC is available for daily 30-minute syncs

---

## 3. Deliverables

| # | Deliverable | Format | Due |
|---|-------------|--------|-----|
| 1 | Site Survey Document | Google Doc | Week 1, Day 3 |
| 2 | GCP Landing Zone (Terraform) | GitHub Repository | Week 1, Day 5 |
| 3 | Data Dictionary | Google Sheets | Week 2, Day 3 |
| 4 | Data Pipeline (dbt project) | GitHub Repository | Week 3, Day 5 |
| 5 | AI Agent System (ADK) | GitHub Repository | Week 4, Day 5 |
| 6 | Golden Dataset & Evaluation Report | Google Doc + JSONL | Week 4, Day 5 |
| 7 | Architecture Decision Record | Google Doc | Week 5, Day 2 |
| 8 | Operations Runbook | Google Doc | Week 5, Day 3 |
| 9 | Admin Guide (for client IT team) | Google Doc | Week 5, Day 3 |
| 10 | Security Review Findings & Remediation | Google Doc | Week 5, Day 4 |
| 11 | Production-Deployed System | GCP Project | Week 5, Day 5 |
| 12 | Monitoring Dashboard | Cloud Monitoring | Week 5, Day 5 |

---

## 4. Client Responsibilities

The following items are the client's responsibility. Delays in these items
may impact the project timeline and will be tracked as risks.

| Item | Owner | Required By | Impact if Late |
|------|-------|-------------|----------------|
| GCP project access (Owner role for FDE SA) | [IT Director] | Day 1 | Blocks all infrastructure work |
| Document corpus access (read access to SharePoint) | [IT Team] | Day 2 | Blocks ingestion pipeline |
| Salesforce API credentials | [Sales Ops] | Day 3 | Blocks CRM integration |
| Security review completion | [CISO Team] | Week 4, Day 5 | Blocks production deployment |
| 5 UAT pilot users confirmed | [Business Lead] | Week 3 | Delays go-live |
| 2-hour availability for operations training | [Run Team] | Week 5 | Delays handoff |
| Data Processing Agreement signed | [Legal] | Day 5 | Blocks data ingestion |

---

## 5. Success Criteria

This project is considered COMPLETE when all of the following are met:

**Technical Criteria:**
- [ ] AI system achieves ≥85% overall pass rate on 100-item golden dataset
- [ ] P95 latency < 5 seconds at 50 concurrent users (load test evidence required)
- [ ] Zero Critical or High security findings unresolved at go-live
- [ ] All infrastructure managed as Terraform code in version control
- [ ] Data pipeline executes daily with < 1% quarantine rate
- [ ] VPC Service Controls enforced (not just dry-run) at go-live

**Operational Criteria:**
- [ ] Client Run Team has completed operations training
- [ ] All runbooks reviewed and accepted by client IT team
- [ ] Monitoring dashboard deployed with alerting policies configured
- [ ] On-call escalation path documented and tested

**Business Criteria:**
- [ ] At least 3 of 5 UAT pilot users confirm system is "ready for production"
- [ ] Average document review time reduced by ≥50% in UAT testing

---

## 6. Timeline

| Week | Key Activities | Milestones |
|------|---------------|------------|
| 1 | Discovery, Infrastructure | GCP Landing Zone live |
| 2 | Data Pipeline build begins | Bronze ingestion running |
| 3 | AI Agent build begins | Silver + Gold layers complete |
| 4 | Evaluation, UAT preparation | Agent passes golden dataset |
| 5 | Security hardening, go-live | Production deployment |
| 6-10 | Post go-live support | [Ongoing] |

---

## 7. Change Control

Any request to change the scope, timeline, or deliverables of this SOW
requires a written Change Request (CR) agreed and signed by both parties
before work on the change begins. CR template available in File 12.

---

## 8. Assumptions and Risks

| Risk | Likelihood | Impact | Owner | Mitigation |
|------|-----------|--------|-------|------------|
| Data access delayed | High | High | Client IT | SOW requires access by Day 2; FDE builds with synthetic data in parallel |
| Security review > 10 days | Medium | High | CISO | Start security review prep in Week 1; provide pre-filled questionnaire |
| Data quality worse than estimated | High | Medium | FDE | Build quarantine layer; scope includes 1-week data remediation buffer |
| Scope creep requests | High | Medium | Both | Written CR required before any out-of-scope work begins |

---

## 9. Signatures

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Client Project Sponsor | | | |
| Client Technical Lead | | | |
| Vendor FDE Lead | | | |
| Vendor Account Executive | | | |
```

---

## ARTIFACT 2: Executive Status Report

```markdown
# EXECUTIVE STATUS REPORT
**Project:** [Project Name] — Week [N] of [Total]
**Prepared by:** [FDE Name]
**Report Date:** [Date]
**Distribution:** [Executive Sponsor, CTO, Project Champion]

---

## 🟢 Overall Status: ON TRACK | 🟡 AT RISK | 🔴 DELAYED
[Choose one — be honest]

---

## This Week's Accomplishments
- **Data Pipeline:** Bronze ingestion now processing 45,000 documents/day
  from all 3 source systems (100% of target volume)
- **AI Agent:** Document search agent correctly answers 89% of test questions
  from our golden dataset (target: 85%) ✅
- **Security:** Completed architecture review with client security team;
  0 Critical findings, 2 High findings (both in remediation)

## What's Happening Next Week
- Complete remediation of 2 High security findings
- Begin User Acceptance Testing with 5 pilot users
- Performance load test (50 concurrent users)
- Finalize operations runbook for client IT team

## Metrics This Week
| Metric | This Week | Target | Status |
|--------|-----------|--------|--------|
| Documents ingested | 45,000 | 45,000 | ✅ |
| AI accuracy (golden set) | 89% | ≥85% | ✅ |
| Security findings (Critical) | 0 | 0 | ✅ |
| Security findings (High) | 2 | 0 | 🟡 |
| Days until go-live | 8 | 10 | ✅ |

## Risks & Issues

### 🟡 RISK: Security remediation timeline
**Impact:** If High security findings not resolved by [date], go-live
delays by 3 business days.
**Mitigation:** [IT Security contact] has committed to completing
remediation by [date]. FDE monitoring daily.
**Action needed from you:** None currently — will escalate if timeline slips.

### ✅ RESOLVED: Data access delay (from last week)
Salesforce API credentials received Monday. Full ingestion pipeline now running.

## Key Decisions Needed
1. **UAT Pilot Users:** Please confirm the 5 users for UAT by [date].
   We need them scheduled for next week or go-live delays by 1 week.
   **Owner:** [Business Lead Name]

---
*Next status report: [Date] | Questions: [FDE email/Slack]*
```

---

## ARTIFACT 3: Operations Runbook

```markdown
# OPERATIONS RUNBOOK
**System:** [System Name]
**Version:** 1.0
**Last Updated:** [Date]
**Owner (Client):** [Name, Role]
**Escalation (Vendor):** [FDE Name, email, phone]

---

## 1. System Overview

### What This System Does
[2 sentences. Plain English. What problem does it solve?]

### Architecture Summary
[Paste architecture diagram here]

**Key Components:**
| Component | GCP Resource | Purpose |
|-----------|-------------|---------|
| AI Agent | GKE: ai-agents/customer-support-agent | Handles user queries |
| Data Pipeline | Cloud Composer: fde-composer | Runs nightly dbt + ingestion |
| Knowledge Base | Vertex AI Search: enterprise-knowledge | Stores indexed documents |
| Database | BigQuery: gold_analytics | Stores business data |
| Monitoring | Cloud Monitoring Dashboard: Production | System health |

**Access the system:**
- Production URL: https://[domain]/agent
- Monitoring Dashboard: [Cloud Monitoring URL]
- Cloud Logging: [URL with pre-built filter]
- GCP Console: [URL to project]

---

## 2. Daily Health Checks

Run these every morning before 9 AM:

```bash
# 1. Check pipeline ran successfully last night
gcloud composer environments run fde-composer \
  --location=us-central1 -- dags list-runs --dag-id=daily_pipeline \
  | head -5
# Expected: Most recent run shows "success" status

# 2. Check agent pods are running
kubectl get pods -n ai-agents
# Expected: All pods show "Running" status, 0 restarts

# 3. Check today's data arrived
bq query --use_legacy_sql=false \
  "SELECT COUNT(*) as rows_today FROM \`project.gold_analytics.fct_sales\`
   WHERE DATE(created_at) = CURRENT_DATE()"
# Expected: rows_today > 0 (alert if 0)
```

**If health checks fail:** See Section 5 (Troubleshooting).

---

## 3. Common Administrative Tasks

### Add a New Document to the Knowledge Base
```bash
# 1. Upload document to GCS
gsutil cp /path/to/document.pdf gs://[project]-raw/documents/

# 2. Trigger re-indexing (runs automatically every 6 hours, or trigger manually)
gcloud scheduler jobs run document-indexer --location=us-central1

# 3. Verify document appears in search (after ~10 minutes)
# Go to Vertex AI Search console → [datastore name] → Documents
# Search for the document by name
```

### Restart the AI Agent (for maintenance or after config change)
```bash
kubectl rollout restart deployment/customer-support-agent -n ai-agents
kubectl rollout status deployment/customer-support-agent -n ai-agents
# Wait until: "deployment/customer-support-agent successfully rolled out"
```

### Update an Agent Prompt
```bash
# Prompts are stored in Secret Manager
# DO NOT edit directly — follow this process:

# 1. Get current prompt
gcloud secrets versions access latest --secret="agent-system-prompt"

# 2. Edit the prompt text
# Save as /tmp/new_prompt.txt

# 3. Upload new version
gcloud secrets versions add agent-system-prompt --data-file=/tmp/new_prompt.txt

# 4. Restart agent to pick up new prompt
kubectl rollout restart deployment/customer-support-agent -n ai-agents

# 5. Verify: run 3 test queries and confirm behavior is correct before
#    informing users of the update
```

---

## 4. Incident Response

### Severity Definitions
| Severity | Definition | Response Time | Escalation |
|----------|-----------|---------------|------------|
| P1 | System completely down; all users affected | 15 minutes | Vendor immediately |
| P2 | Major feature unavailable; >50% users affected | 1 hour | Vendor within 30 min |
| P3 | Minor degradation; workaround exists | 4 hours | Vendor next business day |
| P4 | Cosmetic issue or question | Next business day | Create ticket |

### Incident Response Steps
```
1. DETECT (< 5 minutes)
   - Cloud Monitoring alert fires, OR user reports issue
   - Check monitoring dashboard: is there a spike in errors or latency?

2. ASSESS (5-10 minutes)
   - How many users affected?
   - Is there a workaround? (direct users to manual process if needed)
   - What's the severity? (P1-P4 per table above)

3. COMMUNICATE (within 15 minutes of P1/P2 detection)
   - Notify internal stakeholders via [Slack channel: #system-status]
   - Message template:
     "🚨 [System Name] Incident — [Time]
      Status: Investigating
      Impact: [describe user impact]
      Next update: 30 minutes"

4. DIAGNOSE (see Section 5 for specific issues)
   - Check Cloud Logging for error messages
   - Check recent deployments (was anything changed recently?)
   - Check external dependencies (Vertex AI, BigQuery status pages)

5. RESOLVE
   - Apply fix
   - Test the fix in staging if possible
   - Deploy and verify resolution

6. POST-INCIDENT
   - Send resolution notification to stakeholders
   - Write incident summary (what happened, why, how resolved, how prevented)
   - Create ticket for any follow-up work
```

---

## 5. Troubleshooting Guide

### Issue: Agent returns "I couldn't find information" for everything
```
Likely cause: Vertex AI Search index is stale or empty
Check:
  gcloud alpha discovery-engine documents list \
    --data-store=enterprise-knowledge --location=us
  → If 0 documents: re-run the indexing pipeline (Section 3)
  → If documents present: check if query language matches document language
```

### Issue: Data pipeline showing "failed" in Airflow
```
Check:
  1. Cloud Composer UI → DAGs → daily_pipeline → Last 5 runs
  2. Click the failed task → View Log
  3. Common causes:
     a. Source system down: "ConnectionError to [source]"
        Fix: Check source system status; retry manually when available
     b. BigQuery quota: "Quota exceeded"
        Fix: Wait 60 minutes; check for runaway query in BQ console
     c. dbt test failure: "X test(s) failed"
        Fix: Check data quality (unusual null rates or invalid values)
             Contact vendor FDE if failure persists
```

### Issue: High latency (> 10 seconds for responses)
```
Check:
  1. Cloud Monitoring Dashboard: which service is slow?
  2. If Vertex AI Search: check quota utilization
     gcloud alpha monitoring metrics list --filter="resource.type=discoveryengine.googleapis.com"
  3. If GKE agent: check pod resources
     kubectl top pods -n ai-agents
     → If CPU/memory near limits: scale up
       kubectl scale deployment customer-support-agent --replicas=5 -n ai-agents
```

---

## 6. Escalation Contacts

| Situation | Contact | How | Availability |
|-----------|---------|-----|-------------|
| P1 Production outage | [FDE Name] | Phone: [number] | 24/7 during 30-day support period |
| P2 Major degradation | [FDE Name] | Slack: @[handle] | Business hours + 2h response off-hours |
| GCP billing issues | [GCP Account Manager] | Email: [email] | Business hours |
| Security incident | [CISO name] + [FDE Name] | Email + Phone | Immediate |
| General questions | [FDE Name] | Slack | Business hours |

**Vendor Support Portal:** [URL]
**GCP Support Portal:** [URL]

---

## 7. Scheduled Maintenance Windows

| Task | Schedule | Duration | Impact |
|------|----------|----------|--------|
| Data pipeline | Daily 00:00-02:30 UTC | 2.5 hours | No user impact (pipeline only) |
| GKE node auto-upgrade | Sundays 02:00-04:00 UTC | Up to 2 hours | Brief pod restarts; auto-recovers |
| Vertex AI Search reindex | Every 6 hours | 10 minutes | Slight latency increase |
```

---

## ARTIFACT 4: Architecture Decision Record (ADR)

```markdown
# ADR-001: Vector Store Selection

**Date:** [Date]
**Status:** ACCEPTED
**Deciders:** [FDE Name], [Client Technical Lead]

## Context
We need to store and retrieve document embeddings for the RAG system.
The solution must handle 500K documents (estimated 10M chunks), support
< 1 second retrieval, and operate within the GCP VPC perimeter.

## Decision
We selected **Vertex AI Search** as the vector store.

## Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| Vertex AI Search | Managed; Google ranking; VPC SC compatible; no infra | Less control over indexing; vendor lock-in |
| BigQuery VECTOR_SEARCH | SQL joins possible; existing BQ investment | Higher latency (~800ms vs ~200ms); less mature |
| Pinecone | Industry-leading performance | External service; VPC SC incompatible; additional vendor |
| Qdrant on GKE | Full control; open source | Additional infrastructure; ops burden on client team |

## Rationale
1. **VPC SC compatibility** is non-negotiable (client compliance requirement)
2. **Client's Run Team** has no Kubernetes expertise; managed service reduces ops burden
3. **Retrieval quality** tested on 100 queries: Vertex AI Search 87% relevance vs.
   BigQuery VECTOR_SEARCH 79% relevance
4. **Cost**: Vertex AI Search pricing comparable to self-managed at this scale

## Consequences
- Positive: Zero infrastructure management; integrated with Google's enterprise search ranking
- Negative: Vendor lock-in to Google; limited control over chunking/indexing strategy
- Risk: If Google changes pricing/feature set, migration would require re-ingestion

## Review Date
Reconsider if: document count exceeds 5M, or if latency SLA tightens below 500ms.
```
