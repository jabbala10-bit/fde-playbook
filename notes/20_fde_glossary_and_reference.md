# 20 — FDE Glossary & Quick-Reference Cheat Sheets

> **How to use this file:** This is your field reference. When you hear
> an unfamiliar term in a client meeting, look it up here. When you need
> the exact gcloud command to connect to a cluster, it's in the cheat
> sheets. Print the cheat sheets and keep them accessible.

---

## PART A: GLOSSARY

### Data Engineering Terms

| Term | Definition | FDE Context |
|------|-----------|-------------|
| **Medallion Architecture** | Bronze (raw) → Silver (clean) → Gold (business-ready) layers | Standard pipeline pattern for every engagement |
| **Data Lineage** | Tracking the origin and transformation path of data | Use dbt's auto-generated lineage for client demos |
| **Schema Drift** | When the structure of incoming data changes unexpectedly | Build schema validation at Bronze ingestion |
| **Data Vault 2.0** | Scalable DW methodology using Hubs, Links, Satellites | Use for enterprises with many source systems and strict audit requirements |
| **SCD Type 2** | Slowly Changing Dimension: preserve history by closing old + inserting new rows | Standard for dimension tables that change over time |
| **Grain** | The level of detail each row in a fact table represents | Always define grain first when designing fact tables |
| **Fact Table** | Contains measurable events/transactions with foreign keys to dimensions | Dense with metrics (amount, quantity, duration) |
| **Dimension Table** | Contains descriptive context (who, what, where, when) | Relatively small and wide |
| **Idempotency** | Operation produces same result if run multiple times | Critical for pipeline reruns — always design idempotent ETL |
| **CDC (Change Data Capture)** | Capture row-level changes from a database transaction log | Enables near-real-time sync from operational databases |
| **ETL vs ELT** | ETL: transform before loading; ELT: load raw, transform in DW | Modern cloud DWs favor ELT (BigQuery can handle transformation at scale) |
| **Partitioning** | Dividing a table into segments by a column value (usually date) | Reduces query scan cost; essential in BigQuery |
| **Clustering** | Sorting data within partitions by specified columns | Secondary cost/performance optimization after partitioning |
| **Materialized View** | Precomputed query result stored as a table | Use for frequently-queried expensive aggregations |
| **Data Contract** | Formal agreement defining the schema, format, and quality of data exchanged | Use between source systems and consumers to prevent silent schema breaks |
| **OLTP** | Online Transaction Processing — row-oriented, write-optimized (MySQL, PostgreSQL) | Source systems typically OLTP |
| **OLAP** | Online Analytical Processing — column-oriented, read-optimized (BigQuery, Snowflake) | Analytics/AI layer always OLAP |
| **Surrogate Key** | System-generated ID (integer) to uniquely identify dimension rows | Needed for SCD Type 2; never use natural keys in dimension tables |
| **Natural/Business Key** | Real-world identifier (customer_id from CRM) | Use to join back to source systems |

---

### GCP Services Glossary

| Service | What It Does | When to Use It |
|---------|-------------|----------------|
| **BigQuery** | Serverless data warehouse — SQL analytics at petabyte scale | Default analytics layer for all client data |
| **Cloud Storage (GCS)** | Object storage — files, blobs, data lake files | Raw data landing zone; ML model artifacts; Terraform state |
| **Cloud Run** | Serverless container execution — stateless HTTP services | Lightweight APIs, webhooks, event handlers |
| **GKE** | Managed Kubernetes — container orchestration | Production AI agents, stateful workloads, GPU inference |
| **Vertex AI** | End-to-end ML platform (training, serving, evaluation) | Fine-tuning, model serving, AutoML, pipelines |
| **Vertex AI Search** | Managed semantic search with RAG capabilities | Document Q&A, knowledge base search |
| **Vertex AI Agent Engine** | Managed runtime for Google ADK agents | Production deployment of ADK multi-agent systems |
| **Pub/Sub** | Managed message queue — async event streaming | Event-driven architectures, real-time data ingestion |
| **Cloud Composer** | Managed Apache Airflow — workflow orchestration | Complex data pipeline DAGs with dependencies |
| **Dataflow** | Managed Apache Beam — stream + batch processing | Large-scale unified batch/stream ETL |
| **Dataproc** | Managed Spark + Hadoop clusters | Large-scale batch processing; existing Spark workload migration |
| **Cloud Functions** | Event-driven serverless functions | Simple triggers, lightweight transformations |
| **Secret Manager** | Secure secrets storage (API keys, passwords) | NEVER store secrets in code or env vars; always use Secret Manager |
| **Cloud KMS** | Key Management Service — manage encryption keys | CMEK for regulated industries (HIPAA, finance) |
| **Cloud Armor** | DDoS protection and WAF for load balancers | Protect public-facing endpoints |
| **IAP** | Identity-Aware Proxy — zero-trust access to GCP VMs | Secure SSH/RDP without public IPs |
| **VPC SC** | VPC Service Controls — data exfiltration prevention | Every regulated enterprise client |
| **Private Google Access** | Reach Google APIs without public IP | Enable on all subnets; required for private VMs |
| **Cloud NAT** | Network Address Translation — outbound internet from private VMs | Required when private VMs need internet access |
| **Artifact Registry** | Container and package registry | Store Docker images; required for air-gapped deployments |
| **Cloud Build** | CI/CD pipeline — build, test, deploy | Automate deployment of dbt, container builds |
| **Cloud Trace** | Distributed tracing — latency debugging across services | Debug slow AI pipelines and agent calls |
| **Cloud Logging** | Centralized log aggregation | First stop for debugging any GCP issue |
| **Cloud Monitoring** | Metrics, alerting, dashboards | Set up alerting policies on Day 5 of every engagement |
| **Workload Identity** | Allow GKE pods to authenticate as GCP service accounts | Replaces service account key files — use always |

---

### AI/ML Terms

| Term | Definition | FDE Context |
|------|-----------|-------------|
| **RAG** | Retrieval-Augmented Generation — answer questions by retrieving relevant documents before generating | Most common AI pattern in enterprise; see File 16 |
| **Embedding** | Dense vector representation of text capturing semantic meaning | Foundation of semantic search and RAG |
| **Vector Store / Vector Database** | Database optimized for similarity search on embeddings | Core component of RAG; options: Vertex AI Search, BigQuery, Qdrant |
| **Chunking** | Splitting documents into smaller pieces for embedding and retrieval | Strategy choice has high impact on RAG quality |
| **Semantic Chunking** | Splitting on topic boundaries (not character count) | Better coherence than fixed-size chunking |
| **Reranker / Cross-Encoder** | Second-stage model that scores (query, document) pairs for precision | Add after initial retrieval; significantly improves RAG precision |
| **Faithfulness** | Whether the generated answer is grounded in retrieved context | Key RAG metric; measures hallucination risk |
| **Hallucination** | LLM generating confident-sounding but factually wrong content | Major enterprise risk; mitigate with RAG + faithfulness checks |
| **Context Window** | Maximum tokens an LLM can process in one call | Gemini 1.5 Pro: 1M tokens; GPT-4o: 128K; use wisely |
| **Temperature** | Sampling randomness (0=deterministic, 1=creative) | Use 0.0-0.2 for factual/structured tasks; 0.7-1.0 for creative |
| **Tool Calling / Function Calling** | LLM requesting execution of a predefined function | Foundation of agentic systems |
| **Agentic AI** | AI that plans, takes actions, and observes results in a loop | Use for multi-step tasks that can't be predetermined |
| **Orchestrator Agent** | Top-level agent that routes tasks to specialist agents | Core of ADK multi-agent pattern |
| **Golden Dataset** | Curated set of question-answer pairs for evaluation | Build before building the model; minimum 50 examples |
| **LLM-as-Judge** | Using a strong LLM to evaluate another LLM's output | Scalable alternative to human evaluation |
| **AutoSxS** | Google's automated side-by-side model comparison service | Use for production model comparison before upgrades |
| **Fine-Tuning** | Further training a pretrained model on domain-specific data | Only use after prompting fails; requires 500+ quality examples |
| **LoRA / QLoRA** | Parameter-efficient fine-tuning methods | Standard methods for fine-tuning LLMs without full retraining |
| **Prompt Engineering** | Crafting optimal instructions and examples for LLMs | Try this before fine-tuning; faster and reversible |
| **Few-Shot Learning** | Providing examples in the prompt to guide behavior | Add 3-10 examples for format/style adaptation |
| **Chain of Thought (CoT)** | Prompting the model to show its reasoning before answering | Improves accuracy on complex reasoning tasks |
| **Training/Serving Skew** | Difference in feature computation between training and production | Prevented by using a feature store (Feast, Vertex AI Feature Store) |
| **Data Drift** | Production data distribution shifting from training distribution | Monitor with statistical tests (KS test, PSI) |
| **Concept Drift** | The relationship between features and target changes over time | Requires model retraining, not just input monitoring |

---

### Consulting Terms

| Term | Definition | FDE Context |
|------|-----------|-------------|
| **MECE** | Mutually Exclusive, Collectively Exhaustive — no overlap, nothing missing | Use when structuring any analysis or options set |
| **Pyramid Principle** | Start with the conclusion, then support it | Structure every document and presentation this way |
| **3Cs** | Context, Complication, Resolution — problem-solution framework | Use in proposals and executive briefings |
| **SOW** | Statement of Work — formal scope document | Write one for every engagement (see File 19) |
| **Change Request (CR)** | Formal document to add scope beyond SOW | Require this before any out-of-scope work begins |
| **Champion** | Internal client advocate who drives the project | Your most important relationship; protect their credibility |
| **RACI** | Responsible, Accountable, Consulted, Informed — decision matrix | Clarify roles to prevent accountability gaps |
| **UAT** | User Acceptance Testing — end-users validate the system | Required before go-live; not IT testing, actual users |
| **SLA** | Service Level Agreement — formal performance commitment | Define before go-live (e.g., P95 latency < 5s) |
| **KPI** | Key Performance Indicator — business metric | Always tie AI outputs to a business KPI |
| **TCO** | Total Cost of Ownership — full cost over time | Include infrastructure, maintenance, and personnel in TCO |
| **POC** | Proof of Concept — lightweight prototype to validate feasibility | Week 1-2 quick win; should use real data |
| **MVP** | Minimum Viable Product — smallest deliverable with real value | Scope this explicitly in discovery |
| **Run Team** | Client employees who operate the system after FDE leaves | Identify and train them early; build for their skill level |

---

## PART B: CHEAT SHEETS

### GCP Command-Line Cheat Sheet

```bash
# ── AUTHENTICATION ─────────────────────────────────────────────────────────
gcloud auth login                           # browser-based login
gcloud auth application-default login       # for SDK/Terraform auth
gcloud config set project [PROJECT_ID]      # set active project
gcloud config get-value project             # confirm active project
gcloud auth list                            # show active accounts

# ── GKE ────────────────────────────────────────────────────────────────────
# Connect to cluster
gcloud container clusters get-credentials [CLUSTER] \
  --region=[REGION] --project=[PROJECT]

# Pod operations
kubectl get pods --all-namespaces           # all pods
kubectl get pods -n ai-agents              # pods in namespace
kubectl describe pod [POD] -n [NS]         # pod details
kubectl logs [POD] -n [NS]                 # pod logs
kubectl logs [POD] -n [NS] --previous      # logs of crashed pod
kubectl exec -it [POD] -n [NS] -- /bin/sh  # shell into pod
kubectl top pods -n [NS]                   # resource usage
kubectl rollout restart deployment/[NAME] -n [NS]  # restart deployment
kubectl rollout undo deployment/[NAME] -n [NS]     # rollback deployment
kubectl scale deployment [NAME] --replicas=5 -n [NS]  # scale up

# ── BIGQUERY ───────────────────────────────────────────────────────────────
# Run a query
bq query --use_legacy_sql=false "SELECT COUNT(*) FROM \`project.dataset.table\`"

# Copy a table
bq cp project:dataset.source project:dataset.destination

# List datasets
bq ls --project_id=[PROJECT]

# Show table schema
bq show --format=prettyjson project:dataset.table | python3 -m json.tool

# Load data from GCS
bq load --source_format=PARQUET \
  project:dataset.table \
  gs://bucket/path/*.parquet

# ── CLOUD STORAGE ──────────────────────────────────────────────────────────
gsutil ls gs://[BUCKET]/                   # list bucket contents
gsutil cp local_file gs://bucket/path/     # upload file
gsutil cp gs://bucket/path/file .          # download file
gsutil rsync -r local_dir gs://bucket/dir/ # sync directory
gsutil du -sh gs://bucket/                 # bucket size
gsutil rm gs://bucket/path/file            # delete file

# ── LOGGING ────────────────────────────────────────────────────────────────
# Read recent error logs
gcloud logging read \
  'severity>=ERROR AND timestamp>="[ISO_TIMESTAMP]"' \
  --project=[PROJECT] --limit=50

# Stream logs in real-time (like tail -f)
gcloud logging tail \
  'resource.type="k8s_container" AND resource.labels.namespace_name="ai-agents"' \
  --project=[PROJECT]

# ── SECRET MANAGER ─────────────────────────────────────────────────────────
# Create a secret
echo -n "my-secret-value" | \
  gcloud secrets create MY_SECRET --data-file=- --project=[PROJECT]

# Add a new version
echo -n "new-value" | \
  gcloud secrets versions add MY_SECRET --data-file=- --project=[PROJECT]

# Read a secret
gcloud secrets versions access latest --secret=MY_SECRET --project=[PROJECT]

# ── TERRAFORM ──────────────────────────────────────────────────────────────
terraform init -backend-config="bucket=[PROJECT]-tfstate"
terraform validate
terraform fmt -recursive
terraform plan -var-file="[ENV]/terraform.tfvars" -out=tfplan
terraform apply tfplan
terraform state list
terraform import [RESOURCE_TYPE].[NAME] [ID]
```

---

### Python Quick Reference for FDE Work

```python
# ── BIGQUERY ───────────────────────────────────────────────────────────────
from google.cloud import bigquery
client = bigquery.Client(project="my-project")

# Run a query
df = client.query("SELECT * FROM `project.dataset.table` LIMIT 100").to_dataframe()

# Load DataFrame to BigQuery
client.load_table_from_dataframe(
    df, "project.dataset.table",
    job_config=bigquery.LoadJobConfig(
        write_disposition="WRITE_APPEND",  # or WRITE_TRUNCATE, WRITE_EMPTY
        schema=[
            bigquery.SchemaField("col1", "STRING"),
            bigquery.SchemaField("col2", "INTEGER"),
        ]
    )
).result()

# ── CLOUD STORAGE ──────────────────────────────────────────────────────────
from google.cloud import storage
client = storage.Client()

# Upload
client.bucket("my-bucket").blob("path/to/file.csv").upload_from_filename("/local/file.csv")

# Download
client.bucket("my-bucket").blob("path/to/file.csv").download_to_filename("/local/file.csv")

# List blobs
for blob in client.list_blobs("my-bucket", prefix="data/2026/"):
    print(blob.name)

# ── VERTEX AI LLM CALL ─────────────────────────────────────────────────────
import vertexai
from vertexai.generative_models import GenerativeModel

vertexai.init(project="my-project", location="us-central1")
model = GenerativeModel("gemini-2.0-flash-exp")

response = model.generate_content(
    "Your prompt here",
    generation_config={"temperature": 0.1, "max_output_tokens": 1024}
)
print(response.text)

# ── VERTEX AI EMBEDDINGS ────────────────────────────────────────────────────
from vertexai.language_models import TextEmbeddingModel

model = TextEmbeddingModel.from_pretrained("text-embedding-004")
embeddings = model.get_embeddings([
    {"content": "Text to embed", "task_type": "RETRIEVAL_DOCUMENT"}
])
vector = embeddings[0].values  # list of ~768 floats

# ── SECRET MANAGER ─────────────────────────────────────────────────────────
from google.cloud import secretmanager

def get_secret(secret_id: str, project_id: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

# ── RETRY WITH BACKOFF ──────────────────────────────────────────────────────
import time, random

def retry_with_backoff(fn, max_retries=5, base_delay=1.0):
    """Exponential backoff for Vertex AI quota errors."""
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            if "429" in str(e) or "quota" in str(e).lower():
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                print(f"Rate limited. Waiting {delay:.1f}s (attempt {attempt+1}/{max_retries})")
                time.sleep(delay)
            else:
                raise  # non-quota errors: fail immediately
```

---

### SQL Quick Reference for Common FDE Patterns

```sql
-- ── DE-DUPLICATION ──────────────────────────────────────────────────────────
-- Keep the most recent record per natural key
SELECT * EXCEPT(rn)
FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY natural_key ORDER BY updated_at DESC) AS rn
    FROM table
) WHERE rn = 1;

-- ── PERIOD-OVER-PERIOD COMPARISON ────────────────────────────────────────────
SELECT
    week,
    revenue,
    LAG(revenue) OVER (ORDER BY week) AS prev_week_revenue,
    ROUND((revenue - LAG(revenue) OVER (ORDER BY week)) /
          NULLIF(LAG(revenue) OVER (ORDER BY week), 0) * 100, 2) AS wow_pct_change
FROM weekly_revenue;

-- ── ROLLING AVERAGE ───────────────────────────────────────────────────────────
SELECT date, value,
       AVG(value) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS rolling_7day
FROM daily_metrics;

-- ── UNPIVOT WIDE TABLE TO TALL ────────────────────────────────────────────────
SELECT id, metric_name, metric_value
FROM wide_table
UNPIVOT(metric_value FOR metric_name IN (col1, col2, col3));

-- ── PIVOT TALL TABLE TO WIDE ──────────────────────────────────────────────────
SELECT id,
       MAX(IF(metric_name='revenue', value, NULL)) AS revenue,
       MAX(IF(metric_name='orders', value, NULL)) AS orders
FROM tall_table
GROUP BY id;

-- ── CROSS-SYSTEM RECONCILIATION ───────────────────────────────────────────────
-- Rows in system A but not system B
SELECT a.* FROM system_a a LEFT JOIN system_b b ON a.id = b.id WHERE b.id IS NULL;
-- Rows in both but with different values
SELECT a.id, a.amount AS amount_a, b.amount AS amount_b
FROM system_a a JOIN system_b b ON a.id = b.id
WHERE a.amount != b.amount;

-- ── NULL PROFILING ────────────────────────────────────────────────────────────
SELECT
    COUNTIF(col1 IS NULL) / COUNT(*) AS col1_null_pct,
    COUNTIF(col2 IS NULL) / COUNT(*) AS col2_null_pct
FROM table;

-- ── SESSION ANALYSIS (user journey) ──────────────────────────────────────────
WITH session_boundaries AS (
    SELECT user_id, event_time,
           TIMESTAMP_DIFF(event_time,
               LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time),
               MINUTE) > 30 AS is_new_session
    FROM events
),
sessions AS (
    SELECT *, SUM(CAST(is_new_session AS INT64))
               OVER (PARTITION BY user_id ORDER BY event_time) AS session_num
    FROM session_boundaries
)
SELECT user_id, session_num,
       MIN(event_time) AS session_start, MAX(event_time) AS session_end,
       COUNT(*) AS event_count
FROM sessions GROUP BY 1, 2;
```

---

## PART C: FDE Pre-Engagement Checklist

Use this before your first day at every new client.

```
TECHNICAL PREPARATION:
□ GCP access confirmed: can log into console.cloud.google.com for the project
□ gcloud configured: gcloud config set project [PROJECT_ID]
□ kubectl configured: gcloud container clusters get-credentials ...
□ dbt configured: profiles.yml pointing to the right BigQuery project
□ Terraform initialized: terraform init with correct GCS backend
□ GitHub/GitLab access: push access to the project repository
□ Slack/Teams access: added to relevant channels

DATA PREPARATION:
□ Obtained at least a schema for each source system
□ Sample data (even 10 rows) obtained or scheduled for Day 1
□ Data profiling script ready to run immediately on first access

DOCUMENTS PREPARED:
□ Site Survey template ready (File 13)
□ Data Contract template ready (File 13)
□ SOW template reviewed (File 19) — or existing SOW re-read
□ ADR template ready (File 19)

STAKEHOLDER PREPARATION:
□ Champion identified and first 1:1 scheduled for Day 1
□ IT contact identified for infrastructure questions
□ Security review contact identified and intro email sent
□ Daily 30-minute standup invited to client calendar

PERSONAL READINESS:
□ Read all available documentation about the client's business
□ Understand the client's industry (key terms, regulations, competitors)
□ Know the answer to: "What does success look like in 30 days?"
□ Know the answer to: "What's the most important quick win?"
□ Have the 3 FDE Superpower Questions memorized (File 01)
```
