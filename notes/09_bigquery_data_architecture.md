# 09 — BigQuery: Data Architecture Deep Dive

> **Why this matters for FDEs:** BigQuery is the cornerstone of every
> GCP data engagement. You must know it far beyond "run a SQL query" —
> you need to design for cost, performance, security, and scale. This
> file covers everything from storage architecture to cost optimization
> to real-time streaming.

---

## 1. BigQuery Architecture — How It Actually Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                    BIGQUERY ARCHITECTURE                           │
│                                                                     │
│  CLIENT (SQL query) ──────────────────────────────────────────────► │
│                                                                     │
│  QUERY PLANNER (Dremel)                                            │
│  ─────────────────────                                              │
│  - Parses SQL into a query plan                                     │
│  - Optimizes the plan (predicate pushdown, join reordering)         │
│  - Assigns work to thousands of worker slots                        │
│                                                                     │
│  COMPUTE (Dremel) ←──────────────────────────── separate from       │
│  ──────────────────                             storage!            │
│  - Thousands of parallel worker slots                               │
│  - Each slot reads its assigned data from Colossus                  │
│  - Shuffles data for joins/aggregations                             │
│  - Returns results to client                                        │
│                                                                     │
│  STORAGE (Colossus — Google's distributed file system)             │
│  ─────────────────────────────────────────────────────             │
│  - COLUMNAR storage (each column stored separately)                 │
│  - Compressed with ZSTD or Snappy                                   │
│  - Data organized into ROW GROUPS                                   │
│  - Partitioned tables: different files for each partition           │
│  - Clustered tables: data sorted within partitions                  │
└─────────────────────────────────────────────────────────────────────┘

KEY INSIGHT: BigQuery separates compute from storage.
You pay for STORAGE always (cheap: $0.02/GB/month).
You pay for COMPUTE only when running queries (expensive: $5/TB scanned).
Cost optimization = scan LESS data.
```

---

## 2. Storage Optimization — The Columnar Advantage

### Why Columnar Storage Changes Everything

```sql
-- Consider a table with 100 columns and 1 billion rows.
-- You want: SELECT order_id, amount FROM orders WHERE region = 'APAC'

-- ROW-BASED storage (PostgreSQL, MySQL):
-- Must read ALL 100 columns for ALL rows, then filter/project
-- → reads 100% of data even though you need 3 columns

-- COLUMNAR storage (BigQuery, Parquet):
-- Reads ONLY the 3 columns you need (order_id, amount, region)
-- → reads 3% of data
-- Then predicate pushdown: skip entire row groups where region ≠ 'APAC'
-- → reads even less

-- RESULT: SELECT with few columns from wide table = massive cost savings
-- This is why SELECT * is so expensive in BigQuery
```

### Partition Pruning — The #1 Cost Optimization
```sql
-- Without partitioning: every query scans the ENTIRE table
-- A 10TB table queried 100x/day = 1PB scanned/day = $5,000/day

-- WITH partitioning by date: each query scans only the relevant partitions
SELECT * FROM `project.dataset.orders`
WHERE DATE(order_date) = '2026-06-15'  -- scans 1 day's data only (~30GB)
-- Cost: ~$0.15 instead of $50

-- PARTITION TYPES:
-- 1. Ingestion time (automatic): partitioned by when data was loaded
--    CREATE TABLE ... PARTITION BY _PARTITIONDATE
--    Good for: append-only tables like logs, events

-- 2. Time-unit column: partition by a timestamp/date column in the data
--    CREATE TABLE ... PARTITION BY DATE(order_timestamp)
--    Best for: most business tables with a natural date field

-- 3. Integer range: partition by an integer column
--    CREATE TABLE ... PARTITION BY RANGE_BUCKET(user_id, GENERATE_ARRAY(0,1000000,10000))
--    Good for: user-sharded data where you typically filter by user range
```

### Clustering — Fine-Grained Pruning Within Partitions
```sql
-- Clustering sorts data within each partition by the cluster columns.
-- Queries that filter on cluster columns skip entire blocks.

CREATE TABLE `project.dataset.orders`
PARTITION BY DATE(order_date)
CLUSTER BY region, product_category, customer_tier
AS SELECT * FROM raw_orders;

-- This query benefits from BOTH partitioning AND clustering:
SELECT SUM(amount) FROM orders
WHERE DATE(order_date) = '2026-06-15'  -- partition pruning: reads 1 partition
AND region = 'APAC'                    -- clustering: skips non-APAC blocks
AND product_category = 'Electronics';  -- clustering: skips non-Electronics blocks
-- Reads << 1GB from a multi-TB table

-- CLUSTERING RULES:
-- Max 4 cluster columns
-- Order matters: put the highest-selectivity filter column first
-- Best for high-cardinality columns used in WHERE/GROUP BY
-- NOT good for columns rarely used in filters
```

---

## 3. BigQuery Pricing — Know This Cold

```
STORAGE PRICING:
  Active storage (tables modified in last 90 days): $0.02/GB/month
  Long-term storage (not modified > 90 days):       $0.01/GB/month
  ← Tables automatically convert to long-term pricing
  
  Practical: 10TB active storage = $200/month
             10TB long-term      = $100/month

QUERY PRICING (On-Demand):
  $5 per TB scanned (first 1TB/month free)
  Practical: 1TB query = $5, 100TB query = $500
  ← This is why partition/clustering matters enormously

QUERY PRICING (Reservations/Commitments):
  Buy "slots" (units of compute capacity) at flat monthly rate
  100 slots: ~$2,000/month
  Break-even vs. on-demand: >400TB queries/month
  ← Use reservations only when you have VERY predictable, high query volume

BIGQUERY ML:
  CREATE MODEL: charged as a BigQuery query (per byte processed)
  PREDICT: free if model already trained

STORAGE OPTIMIZATION TIPS:
  □ Partition expiration: DELETE old partitions automatically
  □ Time Travel: default 7 days (costs money) → reduce to 2 days if not needed
  □ Column pruning: SELECT only what you need
  □ EXPORT old data to GCS → cheaper long-term storage
```

---

## 4. BigQuery for AI — Loading Data for Vector Search and Vertex AI

### BigQuery + Vertex AI Integration
```sql
-- OPTION 1: BigQuery ML — run ML models directly in SQL

-- Create a remote LLM connection
CREATE OR REPLACE MODEL `project.dataset.text_embedding_model`
REMOTE WITH CONNECTION `us.my-bq-connection`
OPTIONS (ENDPOINT = 'textembedding-gecko@003');

-- Generate embeddings for documents stored in BigQuery
SELECT *
FROM ML.GENERATE_EMBEDDING(
    MODEL `project.dataset.text_embedding_model`,
    (SELECT doc_id, content AS content FROM `project.dataset.documents`),
    STRUCT(TRUE AS flatten_json_output)
);

-- Text generation using Gemini directly from BigQuery SQL
SELECT
    doc_id,
    ML.GENERATE_TEXT(
        MODEL `project.dataset.gemini_model`,
        PROMPT CONCAT('Summarize this document in 3 bullet points: ', content),
        STRUCT(
            0.2 AS temperature,
            500 AS max_output_tokens,
            TRUE AS flatten_json_output
        )
    ) AS summary
FROM `project.dataset.documents`;
```

### VECTOR SEARCH in BigQuery
```sql
-- BigQuery now supports native vector search
-- Store embeddings as FLOAT64 ARRAY columns

CREATE TABLE `project.dataset.document_embeddings` (
    doc_id      STRING,
    content     STRING,
    embedding   ARRAY<FLOAT64>  -- vector stored directly in BigQuery
);

-- Perform approximate nearest-neighbor (ANN) vector search
SELECT
    base.doc_id,
    base.content,
    distance
FROM VECTOR_SEARCH(
    TABLE `project.dataset.document_embeddings`,
    'embedding',                              -- the column containing vectors
    (SELECT embedding FROM ML.GENERATE_EMBEDDING(...) WHERE query = 'your search query'),
    top_k => 10,                              -- return top 10 nearest neighbors
    distance_type => 'COSINE',               -- cosine similarity
    options => '{"fraction_lists_to_search": 0.01}'  -- ANN parameter
);
```

---

## 5. BigQuery Security — Row-Level and Column-Level

### Row-Level Security
```sql
-- Restrict which rows different users/groups can see
-- Use case: multi-tenant data where each client only sees their own data

-- Create a row access policy
CREATE OR REPLACE ROW ACCESS POLICY customer_isolation
ON `project.dataset.orders`
GRANT TO ("group:client-acme@company.com")
FILTER USING (client_id = 'ACME');

CREATE OR REPLACE ROW ACCESS POLICY another_customer
ON `project.dataset.orders`
GRANT TO ("group:client-globex@company.com")
FILTER USING (client_id = 'GLOBEX');

-- Users in the ACME group see ONLY rows where client_id = 'ACME'
-- The filter is applied AUTOMATICALLY on every query — users can't bypass it
-- Data engineers with "dataOwner" role bypass all row access policies

-- CHECK existing policies:
SELECT * FROM `project.dataset.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`;
```

### Column-Level Security (Data Masking)
```sql
-- POLICY TAG approach: tag sensitive columns in Data Catalog
-- Users without the "Fine-Grained Reader" role see masked values

-- In BigQuery, columns with policy tags show as NULL to unauthorized users
-- Example: PII columns masked for analysts, visible to data engineers

-- After applying a policy tag in Data Catalog UI or via API:
-- Analyst (no masking exception):
SELECT customer_name, email FROM customers;
-- Returns: customer_name="JOHN DOE", email=NULL  ← masked

-- Data Engineer (has Fine-Grained Reader role):
SELECT customer_name, email FROM customers;
-- Returns: customer_name="JOHN DOE", email="john@example.com"  ← full value

-- For testing: set up a masking rule via SQL
-- (requires Data Catalog API to tag columns, then BQ enforces automatically)
```

### Authorized Views — Share Results Without Sharing Source Data
```sql
-- Create a view that filters sensitive columns
CREATE VIEW `project.analytics_dataset.orders_public`
AS SELECT
    order_id,
    order_date,
    total_amount,
    region,
    product_category
    -- NOTE: customer PII columns NOT included
FROM `project.raw_dataset.orders`;

-- Grant view access to analysts without granting access to raw table
GRANT `roles/bigquery.dataViewer`
ON TABLE `project.analytics_dataset.orders_public`
TO "group:data-analysts@company.com";

-- Analysts can query orders_public but cannot access raw_dataset.orders
-- The VIEW itself must be an "authorized view" to read the raw table
```

---

## 6. BigQuery Streaming — Real-Time Data Ingestion

```python
# Method 1: Storage Write API (recommended for production)
# Exactly-once delivery, ~$0.025 per 1GB written

from google.cloud import bigquery_storage_v1
from google.protobuf import descriptor_pool
import json

def stream_to_bigquery(rows: list, project_id: str, dataset: str, table: str):
    """
    Stream data to BigQuery using the Storage Write API.
    Faster and cheaper than the legacy insertAll() method.
    Supports COMMITTED (immediately visible) or BUFFERED (micro-batch) modes.
    """
    write_client = bigquery_storage_v1.BigQueryWriteClient()
    parent = write_client.table_path(project_id, dataset, table)

    # Create a write stream
    write_stream = write_client.create_write_stream(
        parent=parent,
        write_stream=bigquery_storage_v1.WriteStream(
            type_=bigquery_storage_v1.WriteStream.Type.COMMITTED
        )
    )

    # Serialize rows to protobuf (use your table's proto schema)
    # In practice, use the bigquery-storage library's append_rows method

# Method 2: Legacy insertAll() (simple but higher latency/cost)
from google.cloud import bigquery

def insert_rows_streaming(rows: list[dict], table_id: str):
    client = bigquery.Client()
    table = client.get_table(table_id)

    errors = client.insert_rows_json(table, rows)
    if errors:
        raise ValueError(f"BigQuery insert errors: {errors}")

    return len(rows)
```

### Pub/Sub → BigQuery Subscription (No-Code Streaming)
```bash
# Create a BigQuery-connected Pub/Sub subscription
# Messages are automatically written to BigQuery — no pipeline code needed

gcloud pubsub subscriptions create events-to-bq \
  --topic=my-events-topic \
  --bigquery-table=project:dataset.events_table \
  --use-topic-schema \        # use schema registered with the topic
  --write-metadata \          # include Pub/Sub metadata as columns
  --drop-unknown-fields       # don't fail on extra fields
```

---

## 7. BigQuery Administration — Day-to-Day Operations

### Cost Monitoring and Alerts
```sql
-- Monitor query costs over time
SELECT
    DATE(creation_time) AS query_date,
    user_email,
    COUNT(*) AS query_count,
    SUM(total_bytes_processed) / POW(1024, 4) AS total_tb_scanned,
    SUM(total_bytes_processed) / POW(1024, 4) * 5 AS estimated_cost_usd
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
AND statement_type != 'SCRIPT'
GROUP BY 1, 2
ORDER BY total_tb_scanned DESC
LIMIT 50;
-- Identify users running full-table scans and coach them on partitioning
```

### Slot Usage Analysis (for Reservations customers)
```sql
SELECT
    job_id,
    user_email,
    total_slot_ms / 1000 AS total_slot_seconds,
    total_bytes_processed / POW(1024,3) AS gb_scanned,
    start_time,
    end_time
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
ORDER BY total_slot_ms DESC
LIMIT 20;
```

### Table Health Checks
```sql
-- Check partition counts and sizes
SELECT
    table_name,
    partition_id,
    total_rows,
    total_logical_bytes / POW(1024,3) AS size_gb,
    last_modified_time
FROM `project.dataset.INFORMATION_SCHEMA.PARTITIONS`
WHERE table_name = 'orders'
ORDER BY partition_id DESC
LIMIT 30;

-- Find tables with no partition filter requirement (dangerous)
SELECT table_name, ddl
FROM `project.dataset.INFORMATION_SCHEMA.TABLES`
WHERE ddl NOT LIKE '%require_partition_filter%'
AND table_type = 'BASE TABLE';
```
