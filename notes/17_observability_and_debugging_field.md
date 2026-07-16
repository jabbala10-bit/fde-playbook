# 17 — Observability & Debugging in the Field

> **Why this matters for FDEs:** You will not have a senior DevOps engineer
> next to you when something breaks at 11pm before a client demo. You need
> to find the root cause of any GCP/Kubernetes/AI system failure yourself,
> fast. This file is your field debugging playbook.
>
> **Scope note:** this file covers the application/GCP layer (logs,
> metrics, traces, events). For anything self-hosting a model on GPUs,
> [notes/21_hardware_gpu_inference_and_observability.md](./21_hardware_gpu_inference_and_observability.md)
> adds the fifth signal — GPU utilization, memory, power, temperature —
> plus the hardware decision-making and troubleshooting that sits below
> this layer.

---

## 1. The Observability Stack — Four Signals

```
┌─────────────────────────────────────────────────────────────────────┐
│               THE FOUR OBSERVABILITY SIGNALS                       │
│                                                                     │
│  LOGS           METRICS          TRACES           EVENTS           │
│  ─────          ───────          ──────           ──────           │
│  What happened  How many/fast    Where did time   What changed     │
│  (discrete      (continuous      go?              (deploys,        │
│  events)        measurements)    (latency         config changes,  │
│                                  breakdown)       alerts)          │
│                                                                     │
│  Cloud Logging  Cloud Monitoring Cloud Trace      Cloud Deploy     │
│  BigQuery       Prometheus       LangSmith        Audit Logs       │
│  Application    Grafana          Jaeger                            │
│  logs                                                               │
│                                                                     │
│  GCP IMPLEMENTATION:                                               │
│  All 4 signals → Cloud Logging → BigQuery Log Sink → Analytics     │
│  Metrics → Cloud Monitoring → Alerting Policies → PagerDuty/Slack  │
│  Traces → Cloud Trace → Latency Analysis                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Cloud Logging — Your First Stop for Every Issue

```bash
# ── ESSENTIAL LOG QUERIES (Cloud Console → Logging → Log Explorer) ──────────

# 1. Find all ERROR logs in the last hour
severity>=ERROR
timestamp>="2026-06-15T10:00:00Z"

# 2. Find logs from a specific GKE pod
resource.type="k8s_container"
resource.labels.namespace_name="ai-agents"
resource.labels.container_name="customer-support-agent"
severity>=WARNING

# 3. Find BigQuery job failures
resource.type="bigquery_resource"
protoPayload.status.code!=0
timestamp>"2026-06-15T00:00:00Z"

# 4. Find VPC SC violations (data exfiltration attempts)
protoPayload.metadata."@type"="type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata"

# 5. Find Vertex AI API errors
resource.type="aiplatform.googleapis.com/Endpoint"
severity=ERROR

# 6. Find slow Cloud Run requests (> 5 seconds)
resource.type="cloud_run_revision"
httpRequest.latency>"5s"

# 7. Find agent tool call failures (custom log field)
resource.type="k8s_container"
jsonPayload.event_type="tool_call_failed"
```

### Python: Structured Logging (Do This in Every App)
```python
import logging
import json
import time
from google.cloud import logging as cloud_logging
from google.cloud.logging.handlers import CloudLoggingHandler

def setup_structured_logging(service_name: str):
    """
    Set up structured JSON logging that Cloud Logging can parse and index.
    ALWAYS use structured logging in production — it enables log-based metrics
    and efficient querying.
    """
    client = cloud_logging.Client()
    handler = CloudLoggingHandler(client)

    # Create a logger that produces structured JSON
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return logger

# Usage: always include context fields for easy filtering
logger = setup_structured_logging("rag-pipeline")

def log_agent_event(event_type: str, session_id: str,
                    user_id: str, details: dict = None):
    """Log a structured event from the agent system."""
    logger.info(
        f"Agent event: {event_type}",
        extra={
            "json_fields": {
                "event_type": event_type,
                "session_id": session_id,
                "user_id": user_id,
                "service": "agent-system",
                "environment": "production",
                **(details or {})
            }
        }
    )

# Log tool calls for debugging and audit
def log_tool_call(tool_name: str, args: dict, result: dict,
                  duration_ms: float, session_id: str):
    logger.info(
        "Tool call executed",
        extra={
            "json_fields": {
                "event_type": "tool_call",
                "tool_name": tool_name,
                "args": args,
                "success": result.get("error") is None,
                "duration_ms": duration_ms,
                "session_id": session_id,
            }
        }
    )
```

---

## 3. Cloud Monitoring — Metrics and Alerting

### Creating Alerting Policies
```python
from google.cloud import monitoring_v3
from google.protobuf import duration_pb2

def create_agent_error_rate_alert(project_id: str, notification_channel_id: str):
    """
    Alert when agent error rate exceeds 5% over 5 minutes.
    Creates alert via the Cloud Monitoring API.
    """
    client = monitoring_v3.AlertPolicyServiceClient()

    alert_policy = monitoring_v3.AlertPolicy(
        display_name="Agent Error Rate > 5%",
        documentation=monitoring_v3.AlertPolicy.Documentation(
            content="The agent system error rate has exceeded 5%. "
                    "Check Cloud Logging for error details: "
                    "resource.type='k8s_container' severity=ERROR"
        ),
        conditions=[
            monitoring_v3.AlertPolicy.Condition(
                display_name="Error rate > 5%",
                condition_threshold=monitoring_v3.AlertPolicy.Condition.MetricThreshold(
                    filter='resource.type="k8s_container" '
                           'AND metric.type="logging.googleapis.com/user/agent_errors"',
                    comparison=monitoring_v3.ComparisonType.COMPARISON_GT,
                    threshold_value=0.05,  # 5%
                    duration=duration_pb2.Duration(seconds=300),  # 5 minutes
                    aggregations=[
                        monitoring_v3.Aggregation(
                            alignment_period=duration_pb2.Duration(seconds=60),
                            per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_RATE,
                        )
                    ],
                ),
            )
        ],
        notification_channels=[
            f"projects/{project_id}/notificationChannels/{notification_channel_id}"
        ],
        alert_strategy=monitoring_v3.AlertPolicy.AlertStrategy(
            auto_close=duration_pb2.Duration(seconds=86400),  # auto-close after 24h
        ),
    )

    created = client.create_alert_policy(
        name=f"projects/{project_id}",
        alert_policy=alert_policy
    )
    print(f"Created alert policy: {created.name}")
    return created.name
```

### Essential Alerting Policies Checklist
```
FOR EVERY PRODUCTION DEPLOYMENT, CREATE THESE ALERTS:

GKE / Container:
□ Pod restart rate > 3/hour (CrashLoopBackOff indicator)
□ Pod CPU > 85% sustained (throttling risk)
□ Pod Memory > 90% (OOMKill risk)
□ HPA at max replicas (need to increase max or scale infrastructure)
□ Node pool > 80% allocated (cluster autoscaler may not keep up)

AI Agent System:
□ Error rate > 5% over 5 minutes
□ P95 latency > 10 seconds (user experience degrading)
□ Agent tool call failure rate > 10%
□ Max turns reached (agent stuck in loop)
□ Session creation failures > 1%

Data Pipeline:
□ dbt job failure
□ BigQuery daily data load 0 rows (pipeline stopped)
□ Data freshness > 2x expected interval
□ Query cost anomaly > 200% of daily average

BigQuery:
□ Query bytes billed > $100/day per project (runaway query)
□ Failed queries > 5% of total

Vertex AI:
□ Quota utilization > 80% (risk of rate limiting)
□ Model endpoint latency > 5s P95
```

---

## 4. Cloud Trace — Debugging Latency Problems

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

def setup_tracing(service_name: str):
    """
    Set up OpenTelemetry tracing that exports to Cloud Trace.
    Add this to every service to enable end-to-end latency debugging.
    """
    provider = TracerProvider()
    exporter = CloudTraceSpanExporter()
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    return trace.get_tracer(service_name)

# In your application code:
tracer = setup_tracing("rag-pipeline")

async def query_with_tracing(user_query: str, session_id: str) -> dict:
    """RAG query with full distributed tracing."""

    with tracer.start_as_current_span("rag_query") as root_span:
        root_span.set_attribute("session_id", session_id)
        root_span.set_attribute("query_length", len(user_query))

        # Step 1: Embed query
        with tracer.start_as_current_span("embed_query") as embed_span:
            start = time.time()
            query_embedding = embed_query(user_query)
            embed_span.set_attribute("duration_ms", (time.time() - start) * 1000)

        # Step 2: Vector retrieval
        with tracer.start_as_current_span("vector_retrieval") as retrieval_span:
            start = time.time()
            candidates = retrieve_chunks(query_embedding, top_k=20)
            retrieval_span.set_attribute("candidates_returned", len(candidates))
            retrieval_span.set_attribute("duration_ms", (time.time() - start) * 1000)

        # Step 3: Reranking
        with tracer.start_as_current_span("rerank") as rerank_span:
            start = time.time()
            top_chunks = rerank(user_query, candidates, top_n=5)
            rerank_span.set_attribute("duration_ms", (time.time() - start) * 1000)

        # Step 4: LLM generation
        with tracer.start_as_current_span("llm_generation") as gen_span:
            start = time.time()
            result = generate_answer(user_query, top_chunks)
            gen_span.set_attribute("output_tokens", len(result["answer"].split()))
            gen_span.set_attribute("duration_ms", (time.time() - start) * 1000)

        return result

# Now in Cloud Trace you can see a waterfall:
# rag_query (total: 4.2s)
#   ├── embed_query (0.3s)
#   ├── vector_retrieval (0.8s)    ← bottleneck!
#   ├── rerank (0.4s)
#   └── llm_generation (2.7s)     ← largest contributor
```

---

## 5. The FDE Debugging Playbook — Production Incidents

### Incident Response Sequence
```bash
# WHEN SOMETHING BREAKS — FOLLOW THIS SEQUENCE:

# 1. TRIAGE (2 minutes): What is the scope?
#    - Is this affecting ALL users or some users?
#    - Which component is failing (UI, API, pipeline, database)?
#    - Is it a complete outage or degraded performance?

kubectl get pods --all-namespaces | grep -v Running  # find non-running pods
gcloud monitoring dashboards list --filter="displayName:Production"  # check dashboards

# 2. IDENTIFY ROOT CAUSE (5-10 minutes):
# Check recent changes FIRST — 80% of incidents are caused by recent changes
gcloud container clusters describe my-cluster --format="value(createTime)"
kubectl rollout history deployment/customer-support-agent -n ai-agents

# Check logs around the time of failure
gcloud logging read \
  'severity>=ERROR AND timestamp>="2026-06-15T10:00:00Z"' \
  --project=my-project --limit=50 --format=json | python3 -m json.tool

# 3. CONTAIN (immediate):
# If a recent deployment is causing it: ROLLBACK
kubectl rollout undo deployment/customer-support-agent -n ai-agents
# Verify rollback worked:
kubectl rollout status deployment/customer-support-agent -n ai-agents

# 4. COMMUNICATE:
# Send a status message to the client within 10 minutes of detection:
# "We are investigating an issue affecting [feature]. 
#  Estimated impact: [X users/queries affected].
#  Next update: 30 minutes."

# 5. FIX & VERIFY:
# Apply fix → test → deploy → monitor for 15 minutes
# Confirm metrics return to normal

# 6. POST-INCIDENT:
# Write a blameless postmortem within 24 hours (see File 12)
```

### The Most Common GCP/AI Issues and Their Fixes

```
ISSUE: Vertex AI 429 Resource Exhausted
  Symptom: All LLM calls failing with 429 quota errors
  Diagnosis: gcloud monitoring metrics list --filter="resource.type=aiplatform.googleapis.com"
  Fix 1: Implement exponential backoff with jitter in LLM call wrapper
  Fix 2: Distribute load across multiple regions (us-central1 + us-east1)
  Fix 3: Request quota increase in GCP Console → Quotas → Vertex AI
  Code fix:
    import time, random
    def call_with_retry(fn, max_retries=5):
        for attempt in range(max_retries):
            try:
                return fn()
            except Exception as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(wait)
                else:
                    raise

ISSUE: BigQuery query scanning too much data (cost explosion)
  Symptom: Cloud Monitoring alert: daily spend > $500, single query > $50
  Diagnosis: Check INFORMATION_SCHEMA.JOBS for expensive queries
  Fix 1: Add partition filter to the query
  Fix 2: Add clustering on filter columns
  Fix 3: Set max bytes billed on query job:
    query_job = client.query(sql, job_config=bigquery.QueryJobConfig(
        maximum_bytes_billed=10 * 1024**3  # fail if would scan > 10GB
    ))

ISSUE: GKE pod OOMKilled
  Symptom: Pod status = OOMKilled, restarts frequently
  Diagnosis: kubectl describe pod [pod-name] | grep -A5 "Last State"
  Fix: Increase memory limit:
    kubectl set resources deployment my-app --limits=memory=4Gi
  Root cause check: add memory profiling (see File 05 Python profiling)
  
ISSUE: dbt model failure
  Symptom: Daily data pipeline fails, Gold tables not updated
  Diagnosis: Check Airflow/Cloud Composer logs for dbt error
  Fix: Run locally to see exact error:
    dbt run --select failing_model --target prod 2>&1
  Common causes:
    - Source table missing (upstream pipeline failed)
    - Schema change in source (new/removed column)
    - Data quality test failure (new nulls/invalid values)
    - BigQuery quota hit during model materialization

ISSUE: Vector search returns irrelevant results
  Symptom: RAG answers poor quality, wrong documents retrieved
  Diagnosis: Run retrieval quality test on golden set
  Fix 1: Check embedding model - use task_type="RETRIEVAL_DOCUMENT" for docs,
          "RETRIEVAL_QUERY" for queries (different embeddings!)
  Fix 2: Check chunk size - too large = diluted embeddings
  Fix 3: Add metadata filter to narrow retrieval scope
  Fix 4: Verify documents re-indexed after content update

ISSUE: Agent stuck in loop (calls same tool repeatedly)
  Symptom: High token usage, slow response, agent doesn't terminate
  Diagnosis: Check Cloud Trace for repeated tool calls in same span
  Fix: Add max_turns limit to LlmAgent:
    agent = LlmAgent(name="...", max_turns=8, ...)
  Fix: Improve tool error messages (agent retries when confused by error)
  Fix: Add explicit stopping instruction to agent prompt
```

---

## 6. Monitoring Dashboard — Build This on Day 5

Every engagement should have a unified monitoring dashboard in Cloud Monitoring.

```python
from google.cloud import monitoring_dashboard_v1

def create_fde_monitoring_dashboard(project_id: str) -> str:
    """
    Create a standard FDE monitoring dashboard.
    Shows the essential metrics in one place.
    """
    client = monitoring_dashboard_v1.DashboardsServiceClient()

    dashboard = {
        "display_name": "FDE Production Dashboard",
        "grid_layout": {
            "columns": 2,
            "widgets": [
                # Row 1: Agent health
                {
                    "title": "Agent Error Rate (5min avg)",
                    "xy_chart": {
                        "data_sets": [{
                            "time_series_query": {
                                "time_series_filter": {
                                    "filter": 'metric.type="logging.googleapis.com/user/agent_errors"',
                                    "aggregation": {
                                        "alignment_period": {"seconds": 60},
                                        "per_series_aligner": "ALIGN_RATE"
                                    }
                                }
                            }
                        }],
                        "chart_options": {"mode": "COLOR"},
                        "thresholds": [{"value": 0.05, "label": "Error Rate Threshold"}]
                    }
                },
                {
                    "title": "Agent P95 Latency",
                    "xy_chart": {
                        "data_sets": [{
                            "time_series_query": {
                                "time_series_filter": {
                                    "filter": 'metric.type="run.googleapis.com/request_latencies"',
                                    "aggregation": {
                                        "alignment_period": {"seconds": 60},
                                        "per_series_aligner": "ALIGN_PERCENTILE_95"
                                    }
                                }
                            }
                        }]
                    }
                },
                # Row 2: Data pipeline
                {
                    "title": "BigQuery Bytes Billed (Daily)",
                    "scorecard": {
                        "time_series_query": {
                            "time_series_filter": {
                                "filter": 'metric.type="bigquery.googleapis.com/storage/stored_bytes"',
                            }
                        },
                        "thresholds": [{"value": 1e12, "label": "$5 Threshold"}]
                    }
                },
                {
                    "title": "GKE Pod Restart Count",
                    "xy_chart": {
                        "data_sets": [{
                            "time_series_query": {
                                "time_series_filter": {
                                    "filter": 'metric.type="kubernetes.io/container/restart_count"',
                                }
                            }
                        }]
                    }
                }
            ]
        }
    }

    created = client.create_dashboard(
        parent=f"projects/{project_id}",
        dashboard=dashboard
    )
    return created.name
```

---

## 7. Logging Best Practices — Field Reference

```
DO:
✓ Use structured JSON logging (not plain text) — enables log-based metrics
✓ Include session_id, user_id, request_id in every log line
✓ Log every tool call: input, output, duration, success/failure
✓ Log every external API call with response code and latency
✓ Use severity levels correctly:
    DEBUG: verbose detail (disable in production)
    INFO: normal operation events ("pipeline completed 50K rows")
    WARNING: non-fatal issues that need attention ("high latency detected")
    ERROR: failures that affect a single request/user
    CRITICAL: failures that affect the entire system

DON'T:
✗ Log PII (names, emails, SSNs, credit card numbers)
✗ Log secrets or API keys
✗ Log raw user queries without sanitization
✗ Log at DEBUG level in production (volume/cost)
✗ Use print() — use logger.info() instead

COST CONTROL:
  Cloud Logging charges per GB after the free tier.
  At scale, logs can cost more than compute.
  Set a log exclusion filter for noisy, low-value logs:
  
  gcloud logging sinks create low-value-logs-exclusion \
    logging.googleapis.com/projects/[PROJECT]/logs/noisy-service \
    --log-filter="severity<WARNING" \
    --description="Exclude sub-WARNING logs from noisy service"
```
