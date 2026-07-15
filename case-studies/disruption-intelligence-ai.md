# Case Study 3: Agentic Disruption Intelligence for a Global Logistics Operator

## Engagement Context

**Client:** A global logistics company managing approximately 6,200 daily shipments across 42 countries, with a network of 800 carrier partners and annual gross revenue of $4.1B.

**Engagement trigger:** A post-mortem on the previous fiscal year estimated that supply chain disruptions — weather events, port congestion, geopolitical events, carrier failures — had caused $47M in customer penalty payments, expedite costs, and lost margin. A business intelligence team of 8 analysts was responsible for monitoring and responding to disruption signals. Their current process: manually monitoring weather feeds, news sources, carrier communications, and internal ETA alerts; synthesizing signals into briefings; escalating to operations managers. Their assessment: they were missing approximately 30% of disruptions until after operational impact had occurred, because no analyst could monitor all signal sources simultaneously.

**What the client asked for:** *"We want an AI that watches everything and tells us when something is about to go wrong before it goes wrong."*

**Timeline:** 20 weeks from architecture to production deployment.

**Team:** Principal AI FDE (architecture, agent design, evaluation framework), 2 FDEs (implementation), 1 data engineer (pipeline), client's VP of Operations Intelligence and Head of Carrier Relations as key counterparts.

**What makes this engagement technically distinct from the others:** This was not a Q&A system or a drafting assistant. It was an agentic system — a system that autonomously calls external tools, synthesizes information from multiple sources, and produces structured outputs requiring human action. Agentic systems introduce failure modes that non-agentic systems do not: compound errors (where one tool call's wrong output seeds the next), action boundary violations (the agent doing something it wasn't supposed to do), and unpredictable behavior in novel situations the system wasn't designed for.

The Principal AI FDE's first responsibility in an agentic engagement is to define the action boundary — precisely, contractually, and before any code is written.

---

## Initial Framing

The VP of Operations Intelligence's description was emotionally resonant but architecturally undefined. "Watch everything and tell us when something is about to go wrong" could mean:

- Monitor a fixed set of data sources and surface threshold violations (a rules engine, not AI)
- Monitor a fixed set of data sources and synthesize multiple signals into a natural language alert (AI for synthesis, but not agentic)
- Autonomously search for relevant information across open sources and internal systems, reason about impact, and generate recommendations (fully agentic, high complexity, high risk)
- All of the above, plus taking automated actions in the TMS (transportation management system) — rebooking shipments, notifying carriers, opening exception cases (agentic with real-world consequences)

Each option had dramatically different complexity, risk, and time-to-value. The initial framing assumed the most expansive version. The architecture needed to scope it appropriately.

---

## Discovery

**Stakeholder interviews (7 sessions):**

- VP Operations Intelligence: "An analyst's job is to spot patterns across 50 data sources simultaneously. No human can do that at scale. The AI doesn't have to be perfect — it has to be better than what we have."
- Head of Carrier Relations: "I need to know when a carrier is in trouble before they tell me. We always find out too late."
- Operations Manager, North America: "My team gets disruption alerts from the analyst team, usually by email. By the time I read it, 2 hours have passed. I need real-time."
- Analyst (Senior, 8 years): "I spend 3 hours every morning reading through overnight weather reports, news, and carrier advisories to build the morning briefing. Then something changes at 10 AM and I'm starting over."
- Analyst (Junior, 1 year): "I don't even know what half of these signals mean operationally. My senior colleagues have pattern recognition I don't have yet."
- TMS Administrator: "Automated actions in the TMS scare me. We had a rules engine that auto-rebooked shipments 3 years ago. It made decisions that cost us $2M before we noticed."
- Customer Success Lead: "Our biggest clients have SLAs on disruption notification. We're contractually obligated to notify them within 4 hours of a disruption that will affect their cargo. We're failing at that right now."

**Contextual inquiry (4 sessions including overnight shift observation):**

Session 1 (Morning analyst workflow): Observed the senior analyst building the morning briefing. Information sources used in 90 minutes: National Weather Service (US), Joint Typhoon Warning Center (Pacific), Lloyds List (shipping news), Port of Los Angeles congestion tracker (manual web check), internal TMS for exceptions in prior 24 hours, WhatsApp group with 3 carrier contacts for informal intel. No single tool. No automation. Pure manual synthesis.

Session 2 (Disruption response observation): A weather event (tropical storm developing off the Gulf Coast) was identified at 9:40 AM. The analyst spent 2.5 hours: identifying which shipments were affected (manual TMS query + Excel filter), estimating impact (manual calculation of delay ranges), drafting the disruption advisory (email written from scratch), and routing to operations managers. First notification sent at 12:15 PM — 2 hours 35 minutes after initial identification. Three SLA clients should have been notified within 4 hours.

Session 3 (Junior analyst observation): Asked to identify disruptions likely to affect shipments in the next 72 hours. Spent 45 minutes producing a 3-item list that the senior analyst later identified as missing 2 significant items. The senior analyst's explanation: "She doesn't have the mental map yet. She knows the sources but not which sources matter for which lanes."

Session 4 (Carrier relations team): Head of Carrier Relations maintained a personal spreadsheet tracking carrier financial health indicators. "I watch freight volume reports, fuel costs, Chapter 11 filings. When a carrier starts missing windows, I note it. But this is all personal knowledge — if I got hit by a bus tomorrow, this goes away."

**Key findings:**

1. The synthesis problem was real: analysts were manually integrating signals from 12+ sources that were not connected in any system. The value was entirely in the experienced analyst's pattern recognition — which was not scalable, not resilient to staff turnover, and not real-time.

2. The action latency was the business-critical failure: 2.5 hours from disruption identification to first notification was a contractual risk and an operational failure. The bottleneck was not information availability — it was synthesis and drafting time.

3. The junior analyst gap revealed the tacit knowledge problem: the senior analyst's value was not access to data (both had access to the same sources) — it was the pattern recognition built from 8 years of watching signals and outcomes. That pattern recognition was not documented and was not transferable.

4. The TMS administrator's fear of automated actions was well-founded and based on a real prior incident. Automated actions in the TMS were a firm boundary — the scope of the system would not include autonomous TMS actions, and this was a Principal AI FDE-level call, not a preference.

---

## AI Architecture Decisions

**Decision 1: Agentic boundaries — a precise definition of what the system would and would not do**

Before any technical architecture was specified, the Principal AI FDE produced a one-page action boundary document, reviewed and signed off by the VP Operations Intelligence and the TMS Administrator:

*In scope:*
- Monitor specified data sources (enumerated list)
- Synthesize signals into structured disruption alerts
- Identify affected shipments and estimate impact (read-only TMS queries)
- Draft disruption advisories for analyst review
- Prioritize alerts by estimated operational impact

*Out of scope (for this deployment):*
- Autonomous actions in the TMS (no rebooks, no exceptions opened, no carrier communications initiated without human approval)
- Monitoring of sources not on the approved list without explicit approval
- Sending external communications (customer notifications, carrier advisories) without analyst review and manual send
- Accessing systems outside the approved integration list

This document was the most important deliverable of the first two weeks. In agentic system design, the failure to define boundaries precisely is the equivalent of not having a schema in database design — the system will fill the undefined space with behavior you didn't intend.

**Decision 2: Multi-source grounding architecture**

Every alert the system produced had to be traceable to at least one verifiable source. Hallucinated disruption alerts — "tropical storm developing off the Gulf Coast" when there was no tropical storm — would cause the same alert fatigue problem seen in the manufacturing case study (Use Case 4 in the UX guide), but with $M consequences per event.

The grounding architecture:

```
Monitored data sources (ingestion layer):
  - NWS/NOAA weather APIs (10-minute refresh)
  - Lloyd's List RSS feed (real-time)
  - Port authority status APIs (15 configurable ports, hourly)
  - Internal TMS (shipment status, ETA alerts, exception flags)
  - Carrier EDI messages (parsed, structured)
  - Email monitoring (carrier relations inbox, flagged senders)

Signal processing:
  - Structured signals (APIs, EDI): direct ingestion → entity extraction → 
    vector embedding → similarity search against active shipment manifest
  - Unstructured signals (news, email): LLM extraction of: 
    event type, location, severity indicators, affected commodities, 
    estimated duration → structured format → same pipeline

Disruption alert generation:
  - Aggregator: cluster related signals by geography, time window, carrier
  - Impact scorer: join against active shipment manifest (read-only TMS query)
    to identify affected shipments and estimate delay/cost impact
  - Alert generator: structured JSON alert → narrative generation (Claude)
    with mandatory citation of source signals in output
  - Confidence scorer: based on signal count, source reliability, 
    consistency across sources
```

The citation requirement was architectural: the narrative generation prompt required the model to cite specific source signals for every factual claim in the alert. An alert that said "Typhoon Mawar is expected to reach Kaohsiung on Thursday" had to cite the specific JTWC advisory that supported that claim. Alerts with insufficient source grounding were flagged as "Low confidence — source verification required" rather than presented as authoritative.

**Decision 3: Agent tool design**

The system used a set of defined tools that the orchestrating LLM could call. Tool design is one of the highest-leverage decisions in an agentic system — poorly designed tools produce unpredictable agent behavior.

Tools provided to the agent:

```python
tool: search_weather_signals(geography: str, lookback_hours: int) → WeatherSignal[]
# Returns structured weather events for a geography, no free-text interpretation

tool: search_news_signals(query: str, max_results: int) → NewsSignal[]
# Returns news items with source, headline, body, and pre-extracted entities

tool: query_carrier_status(carrier_id: str) → CarrierStatus
# Returns structured carrier performance data: on-time rate, recent exceptions, 
# capacity utilization — read-only, no write access

tool: get_affected_shipments(geography: str, date_range: DateRange) → Shipment[]
# Read-only TMS query returning shipments in or transiting through geography
# Returns shipment IDs, origins, destinations, ETAs, client IDs — no PII

tool: draft_disruption_advisory(disruption: DisruptionSummary) → str
# Generates structured advisory text for analyst review
# Output is a draft — does not send or create any record

tool: flag_for_analyst_review(alert_id: str, priority: Literal['URGENT', 'HIGH', 'NORMAL'], reason: str) → None
# Routes the alert to the analyst queue with specified priority and reason
# This is the only "action" in the agent's tool set — routing a notification
```

The tool set was deliberately minimal. No tool could write to any external system. No tool could send communications. No tool could initiate carrier contacts. The agent's only external action was `flag_for_analyst_review` — routing an alert to a human. Everything else was read-only.

This constraint was the result of the TMS administrator's well-founded fear. The prior automated rebooking incident had cost $2M because the rules engine was given write access to the TMS without adequate boundary controls. The Principal AI FDE's response to that history: "The agent will never have write access to any transactional system in this deployment. Full stop. We can expand that scope in a future phase after we've established trust in the system's judgment."

**Decision 4: Confidence tiering for alerts**

Each alert produced by the system was assigned a confidence tier based on:
- Number of independent source signals supporting the event (more signals = higher confidence)
- Source reliability weights (NWS advisory > news article; EDI message > informal email)
- Cross-source consistency (do multiple sources agree on severity and location?)
- Geographic/temporal specificity (specific port, specific date = higher confidence; vague regional impact = lower)

Confidence tiers:
- **High confidence:** ≥ 3 independent sources, ≥ 2 primary sources, cross-source consistent. Presented to analysts with yellow urgency flag. Estimated to require 5–10 minutes of analyst review before action.
- **Medium confidence:** 2 independent sources, or 1 primary source + 1 secondary. Presented for analyst assessment. Estimated 10–20 minutes.
- **Low confidence / Signal only:** Single source, limited specificity, or model uncertainty. Presented in a "monitoring" queue. Analyst reviews at their discretion. Not escalated automatically.

This tiering directly addressed the alert fatigue risk: high-confidence alerts represented genuine synthesized disruption intelligence; low-confidence alerts were raw signal tracking that had not yet met the threshold for escalation.

**Decision 5: The tacit knowledge preservation architecture**

The senior analyst's pattern recognition was a critical organizational asset at risk. When she eventually left, 8 years of carrier-specific, lane-specific, season-specific disruption intuition would leave with her.

The system was designed to capture and formalize that knowledge through two mechanisms:

*Alert feedback:* Every alert the analyst acted on, modified, or dismissed included a structured feedback field: "Why was this significant?" (for acted alerts) or "Why was this not significant?" (for dismissed alerts). Over time, this feedback became training data for the alert prioritization model.

*Analyst annotation:* When the senior analyst modified a draft disruption advisory, the system captured the original draft and the edited version — creating a dataset of "what an experienced analyst improves about an AI-generated advisory." After 90 days of operation, this dataset was used to tune the advisory generation prompts to match the senior analyst's standard.

This was not fine-tuning the underlying model. It was prompt optimization informed by empirical evidence of expert preference — faster, cheaper, and more maintainable.

---

## Evaluation Framework

**Disruption detection precision and recall:**

Establishing ground truth for a disruption detection system required retrospective analysis. Using 6 months of historical disruption events (compiled from incident reports, customer claims, and operational logs), the team scored the system's performance in detection:

- *Precision:* Of all alerts the system generates, what fraction correspond to genuine disruptions? (Measures false positive rate)
- *Recall:* Of all genuine disruptions that occurred, what fraction did the system detect? (Measures false negative rate)

Target thresholds: Precision ≥ 80%, Recall ≥ 85%. (The recall target was higher than the precision target — a missed disruption was more costly than a false positive.)

Initial performance on the historical dataset: Precision 72%, Recall 79%. Below threshold on both.

Improvements:
- Tightened alert confidence thresholds (improved precision to 81%)
- Expanded carrier EDI monitoring to include 23 additional carriers previously not covered (improved recall to 86%)

**Time-to-alert measurement:**

Established an automated measurement of the time between the earliest detectable signal for a disruption and the moment an alert was routed to the analyst queue. Baseline from the historical dataset: 3.1 hours (senior analyst) to 6.8 hours (junior analyst). Target: < 30 minutes from earliest detectable signal.

**Alert fatigue rate:**

Defined as the percentage of alerts dismissed by analysts without action. High dismissal rate = low precision = alert fatigue risk. Monitored weekly.

**False negative audit:**

Monthly retrospective: were there disruptions that caused operational impact that the system did not alert on? If so, why — was the source not monitored, was the signal too weak, was the geographic specificity insufficient? Each false negative was an improvement signal.

---

## Pilot Design and Execution

**Phase 1 pilot (Weeks 9–14):** System deployed in parallel with the existing analyst process for the North America lane. The senior analyst ran her normal morning briefing workflow simultaneously with the AI system — allowing direct comparison of signals detected, time to detection, and advisory quality.

Week 1–2 finding: The system detected 94% of the events the senior analyst identified, plus 3 events she had not noticed (two weather events affecting secondary ports, one carrier congestion advisory that came in during her lunch hour). The senior analyst validated all 3 as genuine and significant. Recall above expectation.

Week 3 finding: The system generated a high-confidence alert for a port congestion event in the Gulf that the senior analyst assessed as "not actually relevant for our book — we don't have cargo going through that port this week." The alert was technically accurate but lacked the context of current shipment manifest. This was a precision gap: the system was correctly identifying disruption events but not adequately filtering for relevance to active shipments.

Response: Enhanced the `get_affected_shipments` tool integration — the alert scoring now required at least one active shipment affected (current or within 48-hour window) to escalate beyond "monitoring" tier. Precision improved from 72% to 81% within 2 weeks.

Week 5 finding: The junior analyst used the AI alerts as a learning tool — reading the source citations to understand why a signal was significant. Unplanned benefit: the tacit knowledge gap between senior and junior analysts was narrowing as the junior analyst's exposure to curated disruption patterns increased.

---

## Outcomes (measured at 90 days post full deployment)

| Metric | Before | After |
|---|---|---|
| Time from disruption detection to analyst notification | 3.1 hrs (senior) / 6.8 hrs (junior) | 22 minutes |
| SLA-breach notifications delivered within 4 hours | 61% | 94% |
| Disruption recall rate (vs. actual events) | ~70% estimated | 88% |
| Alert precision | N/A | 83% |
| Alert fatigue rate (dismissals without action) | N/A | 14% |
| Analyst morning briefing preparation time | 3.0 hrs/analyst | 45 min/analyst |
| Post-deployment disruption penalty costs (annualized run rate) | $47M baseline | $31M (−34%) |
| Junior analyst detection parity with senior analyst | Not achieved | 89% parity |

The most unexpected outcome: the 89% junior-to-senior analyst detection parity. The system was not designed to close the junior/senior gap — it was a byproduct of the alert architecture making the senior analyst's pattern recognition legible to the junior analyst through source citations and alert rationale.
