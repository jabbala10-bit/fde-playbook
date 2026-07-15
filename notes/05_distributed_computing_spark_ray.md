# 05 — Distributed Computing: Spark & Ray

> **Why this matters for FDEs:** When client data exceeds single-machine
> memory (typically > 50GB), you need distributed computing. Spark is the
> battle-tested standard for batch ETL. Ray is the modern choice for
> distributed AI/ML workloads. Both run on GKE or Dataproc on GCP.

---

## 1. When Do You Need Distributed Computing?

```
DO NOT use Spark/Ray for:
  ✗ Data that fits in BigQuery (< 1TB analytical queries) → use BigQuery
  ✗ Data that fits in pandas (< 5GB) → use pandas or DuckDB locally
  ✗ Simple SQL transformations → use dbt on BigQuery

USE Spark when:
  ✓ Processing terabytes of raw log/event data before loading to BigQuery
  ✓ Complex multi-step transformations that BigQuery can't express efficiently
  ✓ Streaming + batch unified pipeline (Spark Structured Streaming)
  ✓ Client has an existing Spark/Hadoop investment to leverage

USE Ray when:
  ✓ Distributed ML training (fine-tuning LLMs, training large models)
  ✓ Parallel batch inference (scoring 100M rows with an ML model)
  ✓ Hyperparameter tuning at scale (Ray Tune)
  ✓ Distributed data preprocessing for ML (Ray Data)

GCP SERVICES:
  Dataproc     → Managed Spark/Hadoop (simplest for batch ETL)
  GKE          → Spark on Kubernetes (more control, better isolation)
  Vertex AI    → Managed Ray for ML workloads
  Dataflow     → Apache Beam (different model; better for streaming pipelines)
```

---

## 2. Spark Core Concepts

### The Lazy Evaluation Model
```python
# Spark does NOT execute until you call an ACTION
# Everything before an action is a TRANSFORMATION (lazy)

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder \
    .appName("FDE-ETL") \
    .config("spark.sql.adaptive.enabled", "true") \       # AQE: always enable
    .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
    .getOrCreate()

# TRANSFORMATIONS (lazy - nothing runs yet):
df = spark.read.parquet("gs://my-bucket/raw/events/")
df_filtered = df.filter(F.col("event_type") == "purchase")
df_enriched = df_filtered.withColumn(
    "total", F.col("quantity") * F.col("unit_price")
)
df_aggregated = df_enriched.groupBy("customer_id").agg(
    F.sum("total").alias("total_spend"),
    F.count("*").alias("event_count")
)

# ACTION (triggers actual computation):
df_aggregated.write.mode("overwrite").parquet("gs://my-bucket/silver/customer_spend/")
# ← Only NOW does Spark read the data, apply all transformations, and write output

# Other actions:
df.count()      # triggers full scan to count rows
df.show(20)     # triggers computation for first 20 rows
df.collect()    # brings ALL data to driver — DANGER on large datasets
df.first()      # triggers computation for first row only
```

### The DAG — Directed Acyclic Graph
```
Every Spark job is a DAG:
  Stage 1: Read parquet from GCS → Filter → Project
  Stage 2: Shuffle (for groupBy/join) → this is the expensive step
  Stage 3: Aggregate → Write output

THE SHUFFLE IS YOUR ENEMY:
  A shuffle moves data across the network between executors.
  Every groupBy, join, distinct, repartition triggers a shuffle.
  Minimize shuffles = optimize Spark performance.

How to see the DAG:
  spark.sparkContext.setLogLevel("INFO")
  Then check the Spark UI at localhost:4040 during job execution
  → Jobs → Stages → DAG Visualization
```

### Understanding Partitions
```python
# Spark splits data into PARTITIONS that are processed in parallel
# More partitions = more parallelism, but also more overhead

# Check current partition count:
df.rdd.getNumPartitions()  # default: often too high or too low

# REPARTITION: full shuffle, produces equal-sized partitions
df_repartitioned = df.repartition(200)  # good before a large join

# COALESCE: no shuffle, reduces partitions (merge existing)
df_small = df.coalesce(1)  # write a single output file (use sparingly)

# REPARTITION BY COLUMN: ensures same customer_id in same partition
df_partitioned = df.repartition(F.col("customer_id"))
# → subsequent operations on customer_id groups avoid shuffles

# THE RULE: 
# aim for partition size of 100-200MB each
# total_data_size_bytes / 150MB = ideal partition count
```

---

## 3. PySpark Patterns for FDE Work

### Pattern 1: Deduplicate Large Datasets
```python
from pyspark.sql import Window
from pyspark.sql import functions as F

# Keep latest record per natural key (same as SQL ROW_NUMBER pattern)
window = Window.partitionBy("customer_id").orderBy(F.desc("updated_at"))

deduped = (
    df
    .withColumn("rn", F.row_number().over(window))
    .filter(F.col("rn") == 1)
    .drop("rn")
)

# Alternative: dropDuplicates (simpler but can't control WHICH duplicate to keep)
df.dropDuplicates(["customer_id"])  # keeps first occurrence only
```

### Pattern 2: Handle Null Values Defensively
```python
# Profile nulls before any transformation
null_counts = {
    col: df.filter(F.col(col).isNull()).count()
    for col in df.columns
}
# Print a null report
for col, count in sorted(null_counts.items(), key=lambda x: -x[1]):
    pct = round(count / df.count() * 100, 2)
    if pct > 0:
        print(f"  {col}: {count} nulls ({pct}%)")

# Safe type casting (returns NULL instead of crashing on bad data)
df = df.withColumn("amount", F.col("amount_str").cast("double"))
# vs. unsafe: df.withColumn("amount", df["amount_str"].astype(float))
# ← the unsafe version raises an exception on bad data

# Fill nulls with defaults
df = df.fillna({
    "region": "Unknown",
    "discount_pct": 0.0,
    "is_active": True
})
```

### Pattern 3: Large-Table Joins (Avoiding OOM)
```python
# BROADCAST JOIN: if one table is small (< 10MB), broadcast it to all executors
# This avoids a shuffle entirely — massive performance win

from pyspark.sql.functions import broadcast

# Small lookup table (< 10MB):
country_codes = spark.read.csv("gs://bucket/reference/country_codes.csv", header=True)

# Large fact table (> 100GB):
events = spark.read.parquet("gs://bucket/raw/events/")

# BROADCAST the small table — no shuffle needed
enriched = events.join(
    broadcast(country_codes),
    on="country_code",
    how="left"
)

# For joining two LARGE tables: repartition both on the join key first
orders_repartitioned = orders.repartition(200, "customer_id")
customers_repartitioned = customers.repartition(200, "customer_id")
result = orders_repartitioned.join(customers_repartitioned, on="customer_id")
# → same partitions hold same customer_ids → no cross-partition shuffle needed
```

### Pattern 4: Reading Client Data Formats
```python
# CSV with messy headers (common from legacy systems)
df = spark.read.csv(
    "gs://bucket/raw/legacy_export.csv",
    header=True,
    inferSchema=False,      # NEVER infer schema in production — it's slow and wrong
    nullValue="NULL",       # treat "NULL" strings as actual nulls
    nanValue="N/A",
    sep="|",                # pipe-delimited (common in mainframe exports)
    encoding="ISO-8859-1",  # Latin-1 (common in old European ERP exports)
    multiLine=True          # handle newlines inside quoted fields
)

# Define schema explicitly (always do this for production)
from pyspark.sql.types import *
schema = StructType([
    StructField("customer_id", StringType(), nullable=False),
    StructField("order_date", StringType(), nullable=True),  # parse as string first
    StructField("amount", StringType(), nullable=True),       # then cast safely
    StructField("region_code", StringType(), nullable=True),
])
df = spark.read.csv("gs://bucket/raw/orders.csv", schema=schema, header=True)

# Parquet (ideal format — preserve this in your Bronze layer)
df = spark.read.parquet("gs://bucket/raw/events/year=2026/month=06/")

# JSON (common from APIs and NoSQL exports)
df = spark.read.json("gs://bucket/raw/api_responses/")
# Note: JSON schema inference is expensive; define schema explicitly for large files

# Avro (common in Kafka/Pub-Sub outputs)
df = spark.read.format("avro").load("gs://bucket/raw/pubsub_export/")
```

### Pattern 5: Windowed Aggregations (Time-Series)
```python
# Calculate 7-day rolling average per customer
window_7d = (
    Window
    .partitionBy("customer_id")
    .orderBy(F.col("event_date").cast("long"))          # must order by numeric or timestamp
    .rangeBetween(-6 * 86400, 0)                         # 7 days in seconds
)

df_rolling = df.withColumn(
    "rolling_7d_spend",
    F.avg("daily_spend").over(window_7d)
)
```

---

## 4. Spark Performance Optimization

### Adaptive Query Execution (AQE) — Always Enable
```python
spark = SparkSession.builder \
    .config("spark.sql.adaptive.enabled", "true") \
    .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
    .config("spark.sql.adaptive.skewJoin.enabled", "true") \        # handle data skew
    .config("spark.sql.adaptive.localShuffleReader.enabled", "true") \
    .getOrCreate()

# AQE automatically:
# - Merges small shuffle partitions (avoids thousands of tiny files)
# - Handles data skew in joins by splitting skewed partitions
# - Converts sort-merge joins to broadcast joins when one side becomes small
```

### Data Skew — The Silent Killer
```python
# SYMPTOM: Most tasks finish in 5 seconds, but one task takes 10 minutes
# CAUSE: One partition has 100x more data than others (e.g., one customer_id
#        has millions of rows while others have hundreds)

# DETECT skew:
df.groupBy("customer_id").count().orderBy(F.desc("count")).show(20)

# FIX 1: Salting (for joins with skewed keys)
import random

# Add a random "salt" to distribute the skewed key
df_salted = df.withColumn(
    "salted_key",
    F.concat(F.col("customer_id"), F.lit("_"), (F.rand() * 5).cast("int").cast("string"))
)
# Now join on salted_key instead of customer_id
# → spreads one skewed key across 5 partitions

# FIX 2: AQE Skew Join (automatic if enabled above)
# No code changes needed — Spark detects and splits skewed partitions automatically
```

### Caching — Strategic, Not Liberal
```python
# Cache a DataFrame that's used MULTIPLE TIMES in the same job
customer_lookup = spark.read.parquet("gs://bucket/silver/customers/")
customer_lookup.cache()  # or .persist(StorageLevel.MEMORY_AND_DISK)

# Use it multiple times without re-reading from GCS each time:
enriched_orders = orders.join(customer_lookup, "customer_id")
enriched_returns = returns.join(customer_lookup, "customer_id")

# ALWAYS unpersist when done to free executor memory:
customer_lookup.unpersist()

# MISTAKE: caching everything — cache only if DataFrame is REUSED
# Caching a 100GB DataFrame that's only used once wastes memory
```

---

## 5. Ray — Distributed AI/ML on GCP

### When to Use Ray Instead of Spark
```
Spark strengths: SQL-like transformations, large-scale ETL, structured data
Ray strengths:   Python-native ML, fine-tuning, batch inference, flexibility

Choose Ray when:
✓ Running batch inference (score millions of rows with a PyTorch/TF model)
✓ Fine-tuning an LLM (Ray Train + DeepSpeed or FSDP)
✓ Hyperparameter optimization (Ray Tune)
✓ Building custom distributed pipelines in pure Python
✓ The team is more Python/ML than Data Engineering
```

### Ray Batch Inference — FDE Pattern
```python
import ray
from ray.data import Dataset

# The most common FDE use case: score millions of documents with an LLM/model

ray.init()  # connects to the cluster (or starts locally)

# 1. Load data as a Ray Dataset
ds = ray.data.read_parquet("gs://bucket/silver/documents/")

# 2. Define the scoring class (instantiated ONCE per worker)
class DocumentScorer:
    def __init__(self):
        # Heavy init happens once per worker, not per row
        from transformers import pipeline
        self.classifier = pipeline(
            "text-classification",
            model="google/bert-base-uncased-finetuned",
            device=0  # use GPU if available
        )

    def __call__(self, batch: dict) -> dict:
        # batch is a dict of column_name → list of values
        texts = batch["document_text"]
        results = self.classifier(texts, batch_size=32)
        batch["predicted_label"] = [r["label"] for r in results]
        batch["confidence"] = [r["score"] for r in results]
        return batch

# 3. Apply scorer across all data in parallel
scored_ds = ds.map_batches(
    DocumentScorer,
    concurrency=4,           # 4 workers (actors) running in parallel
    num_gpus=1,              # each worker gets 1 GPU
    batch_size=64            # rows per batch passed to __call__
)

# 4. Write results back to GCS
scored_ds.write_parquet("gs://bucket/gold/scored_documents/")
```

### Ray on Vertex AI
```python
# GCP provides managed Ray clusters via Vertex AI
# This is the recommended production deployment for Ray on GCP

from google.cloud import aiplatform

# Create a Ray cluster on Vertex AI
aiplatform.init(project="my-project", location="us-central1")

cluster = aiplatform.preview.create_ray_cluster(
    head_node_type=aiplatform.preview.resources.Resources(
        machine_type="n1-standard-8",
        accelerator_type="NVIDIA_TESLA_T4",
        accelerator_count=1
    ),
    worker_node_types=[aiplatform.preview.resources.Resources(
        machine_type="n1-standard-8",
        accelerator_type="NVIDIA_TESLA_T4",
        accelerator_count=1,
        node_count=4  # 4 worker nodes
    )],
    cluster_name="fde-ray-cluster"
)

# Connect to the cluster:
import ray
ray.init(address=cluster.ray_head_address)
```

---

## 6. Spark vs. BigQuery — The Decision Matrix

```
┌─────────────────────┬──────────────────────────┬──────────────────────────┐
│ Scenario            │ Use BigQuery              │ Use Spark (Dataproc/GKE) │
├─────────────────────┼──────────────────────────┼──────────────────────────┤
│ SQL analytics       │ ✓ Always                  │ ✗                        │
│ < 10TB data         │ ✓ Preferred               │ Only if Spark is cheaper │
│ > 100TB data        │ ✓ Still fine              │ ✓ Batch preprocessing    │
│ Complex Python logic│ ✗                         │ ✓ (PySpark UDFs)         │
│ ML preprocessing    │ ✓ BigQuery ML             │ ✓ More flexible          │
│ Streaming           │ ✓ via Pub/Sub+BQ          │ ✓ Spark Structured Stream│
│ Existing Spark jobs │ N/A                       │ ✓ Migrate incrementally  │
│ Ad-hoc exploration  │ ✓ Fastest iteration       │ ✗                        │
│ Custom file formats │ ✗                         │ ✓                        │
│ Cost (ad-hoc)       │ Pay per query             │ Pay per cluster-hour     │
│ Cost (batch daily)  │ Usually cheaper           │ Cheaper for > 100TB/day  │
└─────────────────────┴──────────────────────────┴──────────────────────────┘

FDE DEFAULT: Start with BigQuery. Only introduce Spark when BigQuery
can't do the job (Python logic, massive files, existing Spark codebase).
Every Spark cluster you introduce is infrastructure the client must maintain.
```

---

## 7. Dataproc: Managed Spark on GCP

```bash
# Create a Dataproc cluster with Terraform (see File 11 for full IaC)
gcloud dataproc clusters create my-spark-cluster \
  --region=us-central1 \
  --master-machine-type=n1-standard-4 \
  --worker-machine-type=n1-standard-4 \
  --num-workers=4 \
  --image-version=2.1-debian11 \
  --optional-components=JUPYTER \
  --enable-component-gateway \
  --properties="spark:spark.sql.adaptive.enabled=true,spark:spark.executor.memory=8g"

# Submit a PySpark job:
gcloud dataproc jobs submit pyspark gs://bucket/jobs/etl_pipeline.py \
  --cluster=my-spark-cluster \
  --region=us-central1 \
  -- gs://bucket/raw/input/ gs://bucket/silver/output/  # job arguments

# For production: use Dataproc Serverless (no cluster management)
gcloud dataproc batches submit pyspark gs://bucket/jobs/etl_pipeline.py \
  --region=us-central1 \
  --deps-bucket=gs://bucket/deps \
  --version=2.1 \
  -- gs://bucket/raw/input/ gs://bucket/silver/output/
```
