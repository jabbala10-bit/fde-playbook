# 13 — Discovery Checklist & Scoping Artifacts

> **Why this matters for FDEs:** Discovery is the highest-leverage phase
> of any engagement. An hour of good discovery prevents a week of wrong
> work. This file gives you the exact questions, checklists, and document
> templates you need to run discovery like a seasoned FDE from Day 1.

---

## 1. The Site Survey — Your First Deliverable

The **Site Survey** is a structured discovery document completed in the
first 48 hours. It captures technical constraints, stakeholder landscape,
and project risks. It becomes the foundation of your SOW.

```markdown
# SITE SURVEY — [Client Name] — [Date]

## Project Overview
**Objective:** [One sentence business goal]
**Timeline:** [Target go-live date]
**FDE:** [Your name]
**Primary Contact:** [Name, title, email]

---

## 1. Data Landscape

### Source Systems
| System | Type | Owner | Access Method | Data Format | Volume | Freshness |
|--------|------|-------|---------------|-------------|--------|-----------|
| Salesforce CRM | SaaS | Sales Ops | REST API + OAuth2 | JSON | 2M records | Real-time |
| Legacy ERP | On-prem MSSQL | IT | VPN + SQL | Tabular | 50GB | Nightly batch |
| SharePoint | Microsoft 365 | HR | Graph API | DOCX/PDF | 10K docs | On-change |

### Data Quality Assessment (Initial)
| System | Est. Null Rate | Known Issues | PII Present | DPA Required |
|--------|---------------|--------------|-------------|--------------|
| Salesforce | ~5% | Duplicate contacts | Yes (email) | Yes |
| ERP | ~15% | No PK on orders | No | No |
| SharePoint | N/A | Inconsistent naming | Yes (names) | Yes |

### Data Access Status
- [ ] Data access credentials received
- [ ] Sample data (even 100 rows) obtained for profiling
- [ ] Data retention/deletion policies reviewed
- [ ] GDPR/CCPA/HIPAA applicability confirmed: **[Yes/No/Unknown]**

---

## 2. Technical Infrastructure

### GCP Environment
- **GCP Project ID:** [or "TBD — to be provisioned"]
- **Organization:** [org domain]
- **Existing GCP Services:** [list what's already deployed]
- **GCP Billing Account:** [confirmed/pending]

### Network Constraints
- **VPN required for GCP access:** [Yes/No]
- **Air-gapped requirement:** [Yes/No/Partial]
- **Data residency requirement:** [None/US only/EU only/specific region]
- **Outbound internet allowed from GCP:** [Yes/No/Restricted]

### Authentication/Identity
- **Identity Provider:** [Google Workspace/Azure AD/Okta/Other]
- **SSO available:** [Yes/No]
- **MFA enforced:** [Yes/No]
- **Service account key policy:** [Allowed/Restricted — Workload Identity preferred?]

### Approved Technology Stack
| Category | Client Approved | Client Prohibited | Notes |
|----------|----------------|-------------------|-------|
| LLM Provider | Vertex AI (Gemini) | OpenAI | Data policy restriction |
| Container Registry | Artifact Registry | Docker Hub | Security policy |
| Secrets | Secret Manager | Env vars in code | Compliance requirement |
| Monitoring | Cloud Monitoring | External SaaS | Cost control |

---

## 3. Security & Compliance

### Compliance Requirements
- [ ] SOC 2 Type II required: [Yes/No]
- [ ] HIPAA covered entity: [Yes/No]
- [ ] PCI-DSS in scope: [Yes/No]
- [ ] FedRAMP required: [Yes/No]
- [ ] GDPR/UK GDPR applies: [Yes/No]
- [ ] Industry-specific regulation: [FFIEC/NERC/ITAR/etc.]

### Security Review Process
- **Security review owner:** [Name/Team]
- **Estimated review timeline:** [X weeks]
- **Required security artifacts:**
  - [ ] Architecture diagram
  - [ ] Data flow diagram
  - [ ] Vendor security questionnaire
  - [ ] Penetration test results
  - [ ] SOC 2 report
- **Approved cloud providers list exists:** [Yes/No — where?]
- **Change management process:** [Ticket system, approver, SLA]

---

## 4. Stakeholder Map

| Name | Title | Role in Project | Interest | Power | Notes |
|------|-------|----------------|----------|-------|-------|
| [Name] | VP Engineering | Champion | High | High | Drives the project |
| [Name] | CISO | Security Approver | Low | High | Will approve/block |
| [Name] | Data Analyst | End User | High | Low | Key validator |
| [Name] | IT Director | Infrastructure Owner | Med | Med | Controls GCP access |

**Decision Maker (final go/no-go):** [Name, Title]
**Budget Owner:** [Name, Title]
**Day-to-day Technical POC:** [Name, Title, email, Slack handle]

---

## 5. Project Risks (Initial Assessment)

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Data access not granted by Week 1 | High | High | Escalate to Champion on Day 1; document in SOW as client responsibility |
| Security review takes > 4 weeks | Medium | High | Start security review process this week; begin with existing approved components |
| Source data quality worse than estimated | High | Medium | Build quarantine layer; scope includes data remediation sprint |
| Key client contact unavailable (travel, PTO) | Medium | Medium | Identify backup POC; get 30-min daily sync on calendar immediately |
| Scope creep (new features requested mid-project) | High | Medium | Written change request process in SOW; parking lot for future work |

---

## 6. Quick Win Identified
**What:** [e.g., "Automate the daily Salesforce → BigQuery sync that currently takes 2 hours/day manually"]
**Why it's quick:** [e.g., "Data already accessible via API; straightforward pipeline; delivers visible value in Week 1"]
**Timeline:** Day 3-5 of engagement
**Owner:** FDE + Client Data Analyst

---

## 7. Outstanding Items (Blockers)
1. [ ] GCP project access — **Owner:** [IT Director] — **Needed by:** [Date]
2. [ ] Salesforce API credentials — **Owner:** [Sales Ops] — **Needed by:** [Date]
3. [ ] Data Processing Agreement signed — **Owner:** [Legal] — **Needed by:** [Date]
4. [ ] Security review timeline confirmed — **Owner:** [CISO] — **Needed by:** [Date]

---
*Site Survey completed by: [FDE Name] | Last updated: [Date]*
```

---

## 2. The 50-Question Discovery Bank

Use these in discovery calls. You don't ask all 50 — you choose the
relevant ones and sequence them naturally in conversation.

### Business & Problem Understanding
```
1.  "Walk me through a day in the life of the person this AI will help."
2.  "What does success look like for this project in 90 days?"
3.  "What would it cost you (in dollars, time, risk) if this project
     delivered nothing after 3 months?"
4.  "Who pushed for this project? Who would prefer it didn't happen?"
5.  "What have you tried before that didn't work? What did you learn?"
6.  "What decision will you make differently once the AI is working?"
7.  "Who is the user? Who is the buyer? Are they the same person?"
8.  "What is the process today — step by step — that we're automating?"
9.  "What are the acceptable error rates? A wrong answer is worse than
     no answer for which use cases?"
10. "What does 'done' look like? What happens the day after go-live?"
```

### Data & Technical Discovery
```
11. "Can you show me the actual data — even 5 rows from production?"
12. "Where does the data live today? Who owns it?"
13. "How does data get into those systems? Manual entry? API? Batch?"
14. "How fresh does the data need to be for this use case to work?"
15. "What's the average quality of this data? Any known issues?"
16. "Is there a data dictionary or schema documentation anywhere?"
17. "What happens to data that's wrong or missing today?"
18. "Are there multiple systems with the 'same' data? Which is the source of truth?"
19. "Have you run a data quality assessment recently?"
20. "What data access controls exist? Row-level? Column-level?"
```

### Infrastructure & Security
```
21. "Is there a GCP project already set up, or are we starting from scratch?"
22. "Who manages GCP today? Is there an internal cloud team?"
23. "What does the network topology look like? VPN? Direct Connect?"
24. "Is data allowed to leave the country/region for processing?"
25. "Are there approved/prohibited cloud services on your security policy?"
26. "What does the security review process look like? Timeline?"
27. "Who do I talk to for firewall changes? IAM changes? DNS changes?"
28. "Are there any air-gapped requirements for this project?"
29. "What's the change management process? Can I deploy to prod directly?"
30. "What compliance frameworks apply to this data? HIPAA? PCI? GDPR?"
```

### Stakeholders & Politics
```
31. "Who has the final say on whether this project succeeds?"
32. "Who has the authority to stop this project if they wanted to?"
33. "Is there an internal team that wanted to build this themselves?"
34. "What other vendors did you evaluate? Why did you choose us?"
35. "Who are the end users? How do we involve them in testing?"
36. "Does anyone need to approve the architecture before we build it?"
37. "What happened to the last technology project that failed here?"
38. "Are there any political sensitivities I should know about?"
39. "Who needs to be kept informed even if they're not actively involved?"
40. "What's the best way to communicate progress to the executive sponsor?"
```

### Timeline & Constraints
```
41. "Is the deadline fixed or flexible? What's driving it?"
42. "Are there any blackout periods where changes can't be deployed?"
43. "When is your next board presentation / fiscal year end / audit?"
44. "What resources can the client team dedicate to this project?"
45. "Is there budget confirmed for cloud infrastructure costs?"
46. "What happens if we're 2 weeks late? 4 weeks late?"
47. "What external dependencies could delay us? (Legal, procurement, IT)"
48. "Do you have a parallel project that might conflict with this one?"
49. "Has headcount for running this post-go-live been approved?"
50. "If we had to cut scope to hit the deadline, what would you cut first?"
```

---

## 3. The Technical Discovery Checklist

Run this checklist on every client technical system before building anything.

```bash
# DATA DISCOVERY CHECKLIST

□ Obtained sample data (even 100 rows) for each source system
□ Profiled null rates on all critical columns
□ Verified data types match documentation (dates are actually dates, not strings)
□ Identified primary keys (or confirmed they don't exist)
□ Estimated row counts and growth rates
□ Confirmed access credentials work from the GCP project
□ Documented all data formats (JSON, CSV, Parquet, fixed-width, XML, EDI)
□ Confirmed data encoding (UTF-8? Latin-1? ASCII?)
□ Identified PII columns and their masking/encryption requirements
□ Confirmed data refresh frequency (real-time? hourly? daily? weekly?)

# GCP ENVIRONMENT CHECKLIST

□ GCP project ID confirmed
□ Billing account linked and budget alerts set
□ APIs enabled: BigQuery, GCS, Compute, GKE, Vertex AI, Secret Manager
□ Terraform state bucket created
□ VPC/subnet CIDR ranges confirmed (no conflicts with on-prem)
□ Private Google Access enabled on subnets
□ Organization policies applied (no external IPs, resource location)
□ IAM: service accounts created with least-privilege roles
□ Workload Identity configured for GKE
□ Cloud KMS key ring created (if CMEK required)
□ VPC SC perimeter in dry-run mode

# NETWORK CONNECTIVITY CHECKLIST

□ Connectivity from GCP to each source system confirmed
□ DNS resolution working (can resolve internal DNS from GCP)
□ Port/firewall rules documented and approved
□ VPN or Cloud Interconnect configured if needed
□ NAT Gateway operational (for outbound internet from private VMs)
□ Data exfiltration path tested (confirm data CAN move where expected)
```

---

## 4. The Data Contract Template

Use this to formalize what data the client will provide and when.

```markdown
# DATA CONTRACT — [Client Name] — [Project Name]

## What We Need
| Dataset | Source System | Format | Access Method | Refresh | Owner |
|---------|--------------|--------|---------------|---------|-------|
| Customer Master | Salesforce | REST API | OAuth2 Service Account | Real-time | John Smith |
| Order History | ERP Oracle DB | JDBC | VPN + SQL credentials | Nightly batch | Jane Doe |
| Product Catalog | SharePoint | MS Graph API | Service Principal | On-change | IT Team |
| Support Tickets | Zendesk | REST API | API Key | Hourly | Support Ops |

## Minimum Viable Data for Prototype
To begin building by Week 2, we need:
- [ ] Customer Master: 1,000 rows sample (any anonymization acceptable)
- [ ] Order History: 3 months of data (2026 Q1 minimum)
- [ ] Product Catalog: Full export in any format
- [ ] Support Tickets: 6 months of history

## Data Quality Baseline
Client confirms that data quality baseline has been assessed and:
- Known issues are documented in the attached Data Quality Report
- Data remediation timeline for critical issues: [Date]
- Acceptable data quality threshold for go-live: [Metric and threshold]

## Access Provisioning Timeline
| Access Item | Owner | Target Date | Fallback |
|------------|-------|-------------|---------|
| Salesforce connected app credentials | John Smith | [Date] | Manual CSV export |
| GCP IAM access for FDE service account | IT Team | [Date] | Blocker — escalate |
| VPN access to ERP database | Network Team | [Date] | Blocker — escalate |

## Signatures
Client Data Owner: _________________ Date: _______
FDE Lead: _________________ Date: _______
```

---

## 5. Discovery Red Flags — What to Escalate

```
🚩 "We can't give you access to production data — use synthetic data."
   Reality: Synthetic data rarely captures real messiness. AI trained on
   synthetic data fails in production.
   Response: "For the prototype, anonymized or sampled production data
   is essential. Can we work with your security team on a DPA that
   allows anonymized sampling?"
   Escalate if: client refuses any access — this changes the project scope.

🚩 "The data will be ready in [2 weeks / next sprint / after the audit]."
   Reality: It's almost never ready when promised.
   Response: "Let's add 'data access by [specific date]' as a client
   dependency in the SOW with a schedule impact note."
   Action: Start building with any available data now. Don't wait.

🚩 "Our IT team will review the architecture before we can proceed."
   Reality: Unknown review timeline is the most common project killer.
   Response: "Can we schedule a working session with the IT review team
   this week? I'd like to understand their requirements upfront rather
   than submitting a design that needs multiple revision cycles."
   Action: Start security review documentation immediately (see File 07).

🚩 "We don't have anyone to maintain this after you leave."
   Reality: The project will die or become permanent FDE dependency.
   Response: "Let's add a knowledge transfer plan to the SOW. Who is the
   designated internal owner? What level of technical training do they need?"
   Escalate if: no owner can be identified — this is a project risk that
   may require scope change (build simpler solution, or extend engagement).
```
