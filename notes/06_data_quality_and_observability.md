# 06 — Data Quality & Observability

> **Why this matters for FDEs:** Bad data is the #1 cause of AI project
> failure. Not bad models. Not bad infrastructure. Bad data. An FDE who
> ships a beautiful agent on top of unvalidated data has built a liability,
> not a solution. This file covers every layer of data quality — from
> ingestion-time validation to production anomaly detection.

---

## 1. The Four Dimensions of Data Quality

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DATA QUALITY DIMENSIONS                             │
│                                                                         │
│  COMPLETENESS    VALIDITY       CONSISTENCY    TIMELINESS              │
│  ────────────    ────────       ───────────    ──────────              │
│  Are required    Are values     Do values      Is data                 │
│  fields present? in expected    agree across   fresh enough            │
│  What % of       range/format?  systems?       for its use?            │
│  rows have nulls?              Are there       SLA: when               │
│                  e.g. email     contradictions? must it                │
│  Measure:        format valid,  e.g. order     arrive?                 │
│  null_rate       date not       count in CRM                           │
│  per column      future, age    != ERP?         Measure:               │
│                  between 0-150                  lag_minutes            │
└─────────────────────────────────────────────────────────────────────────┘
```

### A 5th Dimension for AI: REPRESENTATIVENESS
```
Is the data REPRESENTATIVE of what the model will see in production?

This is the training/serving skew problem:
- Training data = 2019-2022 (pre-pandemic behaviors)
- Production data = 2026 (post-pandemic behaviors)
→ Model confidently wrong on current data

FDE Checklist for AI:
□ When was the training data collected?
□ Has the data distribution shifted since then?
□ Are the edge cases in the production distribution covered in training data?
□ Is the client's specific language/terminology in the training data?
```

---

## 2. Great Expectations — The Standard Framework

**Great Expectations (GX)** is the industry standard for data validation.
It defines "expectations" (assertions about your data) that run as tests.

### Setup on GCP
```python
import great_expectations as gx
from great_expectations.datasource.fluent import BatchRequest

# Initialize a GX context (stores configs in GCS for production)
context = gx.get_context(
    context_root_dir="gs://my-project-gx/great_expectations/"
)

# Add a BigQuery data source
datasource = context.sources.add_or_update_bigquery(
    name="bigquery_source",
    project="my-gcp-project",
    dataset="silver_crm",
)

# Create a data asset (points to a BigQuery table)
asset = datasource.add_table_asset(
    name="customers",
    table_name="customers"
)
```

### Defining Expectations — The Full Vocabulary
```python
# Get a validator for the batch of data
batch_request = asset.build_batch_request()
validator = context.get_validator(batch_request=batch_request)

# ── COMPLETENESS ──────────────────────────────────────────────────────
validator.expect_column_values_to_not_be_null("customer_id")
validator.expect_column_values_to_not_be_null(
    "email",
    mostly=0.95  # 95% of values must be non-null (5% null allowed)
)

# ── UNIQUENESS ────────────────────────────────────────────────────────
validator.expect_column_values_to_be_unique("customer_id")
validator.expect_compound_columns_to_be_unique(["email", "tenant_id"])

# ── VALIDITY ──────────────────────────────────────────────────────────
# Value range
validator.expect_column_values_to_be_between(
    "age", min_value=0, max_value=150
)
validator.expect_column_values_to_be_between(
    "order_amount", min_value=0.01  # amounts must be positive
)

# Allowed categorical values
validator.expect_column_values_to_be_in_set(
    "customer_tier", {"Gold", "Silver", "Bronze", "Unknown"}
)

# Regex pattern matching
validator.expect_column_values_to_match_regex(
    "email", r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)

# Date format
validator.expect_column_values_to_match_strftime_format(
    "created_date", "%Y-%m-%d"
)

# No future dates
validator.expect_column_values_to_be_between(
    "created_date",
    max_value=str(datetime.date.today())
)

# ── REFERENTIAL INTEGRITY ─────────────────────────────────────────────
# All order customer_ids must exist in the customers table
validator.expect_column_values_to_be_in_set(
    "customer_id",
    value_set=set(df_customers["customer_id"].tolist())
)

# ── ROW COUNT ANOMALY DETECTION ───────────────────────────────────────
validator.expect_table_row_count_to_be_between(
    min_value=10000,   # alert if fewer than expected
    max_value=5000000  # alert if suspiciously large (possible duplication)
)

# ── STATISTICAL DISTRIBUTION ─────────────────────────────────────────
validator.expect_column_mean_to_be_between(
    "order_amount", min_value=50, max_value=500
)
validator.expect_column_stdev_to_be_between(
    "order_amount", min_value=10, max_value=1000
)

# Save the expectation suite
validator.save_expectation_suite("customers_suite")
```

### Running Validations in a Pipeline
```python
# Run checkpoint (validation + data docs generation)
checkpoint_config = {
    "name": "customers_daily_checkpoint",
    "validations": [{
        "batch_request": batch_request,
        "expectation_suite_name": "customers_suite"
    }],
    "action_list": [
        {
            "name": "store_validation_result",
            "action": {"class_name": "StoreValidationResultAction"}
        },
        {
            "name": "send_slack_notification",
            "action": {
                "class_name": "SlackNotificationAction",
                "slack_webhook": "https://hooks.slack.com/...",
                "notify_on": "failure"
            }
        },
        {
            "name": "update_data_docs",
            "action": {"class_name": "UpdateDataDocsAction"}
        }
    ]
}

checkpoint = context.add_or_update_checkpoint(**checkpoint_config)
result = checkpoint.run()

if not result.success:
    # Quarantine the bad data - do NOT let it proceed to Silver
    raise ValueError(f"Data quality check failed: {result.statistics}")
```

---

## 3. The Quarantine Pattern — Fail Safe, Not Fail Hard

Instead of crashing the pipeline when bad data arrives, quarantine it:

```python
# The Quarantine Pattern — used in every production FDE pipeline

from pyspark.sql import functions as F

def apply_quality_rules(df):
    """Apply validation rules and tag each row as PASS or QUARANTINE."""
    return df.withColumn(
        "dq_status",
        F.when(F.col("customer_id").isNull(), "QUARANTINE:null_customer_id")
        .when(F.col("email").isNull(), "QUARANTINE:null_email")
        .when(
            ~F.col("email").rlike(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
            "QUARANTINE:invalid_email_format"
        )
        .when(F.col("order_amount") <= 0, "QUARANTINE:non_positive_amount")
        .otherwise("PASS")
    )

df_validated = apply_quality_rules(df_raw)

# Split into good and bad
df_good = df_validated.filter(F.col("dq_status") == "PASS").drop("dq_status")
df_quarantine = df_validated.filter(F.col("dq_status") != "PASS")

# Write good data to Silver
df_good.write.mode("append").parquet("gs://bucket/silver/customers/")

# Write quarantined data to a separate location for investigation
df_quarantine.write.mode("append").parquet("gs://bucket/quarantine/customers/")

# Alert on quarantine rate
total = df_validated.count()
quarantine_count = df_quarantine.count()
quarantine_rate = quarantine_count / total * 100

if quarantine_rate > 5:  # Alert if > 5% of data is quarantined
    send_alert(
        f"⚠️ High quarantine rate: {quarantine_rate:.1f}% of customers "
        f"({quarantine_count} rows). Check gs://bucket/quarantine/customers/"
    )
```

---

## 4. dbt Tests — Integrated Quality Gates

In the dbt pipeline (see File 04), quality tests are built directly
into the transformation layer:

```yaml
# models/silver/_models.yml
models:
  - name: stg_crm__customers
    tests:
      # Table-level tests
      - dbt_utils.equal_rowcount:
          compare_model: ref('raw_customers')  # staging should have same rows as source
    columns:
      - name: customer_id
        tests:
          - not_null
          - unique
      - name: email
        tests:
          - not_null:
              severity: warn  # warn but don't fail the pipeline
              config:
                where: "customer_tier = 'Gold'"  # only Gold customers must have email
          - dbt_expectations.expect_column_values_to_match_regex:
              regex: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
      - name: order_amount
        tests:
          - dbt_expectations.expect_column_values_to_be_between:
              min_value: 0.01
              max_value: 1000000
      - name: customer_tier
        tests:
          - accepted_values:
              values: ['Gold', 'Silver', 'Bronze', 'Unknown']
```

### dbt Freshness Checks
```yaml
# In your _sources.yml - monitor when data last arrived
sources:
  - name: crm
    tables:
      - name: raw_customers
        loaded_at_field: _ingested_at  # dbt checks this timestamp
        freshness:
          warn_after: {count: 12, period: hour}   # warn if data > 12h old
          error_after: {count: 24, period: hour}  # fail if data > 24h old
```

---

## 5. Data Observability — Monte Carlo Approach

Beyond static tests, **data observability** continuously MONITORS production
data for anomalies using statistical methods — like APM for your data.

### Building a Lightweight In-House Observability System

```sql
-- BigQuery: Create a data quality metrics table
CREATE TABLE monitoring.dq_metrics (
    check_time    TIMESTAMP,
    table_name    STRING,
    metric_name   STRING,
    metric_value  FLOAT64,
    is_anomaly    BOOL,
    threshold     FLOAT64
)
PARTITION BY DATE(check_time);

-- Daily metrics collection job (run via Cloud Scheduler + Cloud Functions)
INSERT INTO monitoring.dq_metrics
SELECT
    CURRENT_TIMESTAMP() AS check_time,
    'silver.crm.customers' AS table_name,
    'row_count' AS metric_name,
    COUNT(*) AS metric_value,
    -- Z-score anomaly detection: flag if > 3 standard deviations from rolling mean
    ABS(COUNT(*) - AVG(COUNT(*)) OVER w) / NULLIF(STDDEV(COUNT(*)) OVER w, 0) > 3
        AS is_anomaly,
    AVG(COUNT(*)) OVER w + 3 * STDDEV(COUNT(*)) OVER w AS threshold
FROM silver.crm.customers
CROSS JOIN (
    SELECT 1  -- just to make the aggregation work with the window
)
WINDOW w AS (
    ORDER BY CURRENT_DATE()
    ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING  -- 30-day rolling baseline
);
```

### The 5 Observability Metrics Every Pipeline Must Track

```python
# Run these as daily monitoring checks on every critical table

MONITORING_SUITE = {
    "row_count": """
        SELECT COUNT(*) AS value
        FROM `{table}`
        WHERE DATE(_ingested_at) = CURRENT_DATE() - 1
    """,

    "null_rate_critical_cols": """
        SELECT
            COUNTIF(customer_id IS NULL) / COUNT(*) AS customer_id_null_rate,
            COUNTIF(order_amount IS NULL) / COUNT(*) AS amount_null_rate
        FROM `{table}`
        WHERE DATE(_ingested_at) = CURRENT_DATE() - 1
    """,

    "schema_change": """
        -- Compare current schema to expected schema
        SELECT column_name, data_type
        FROM `{project}.{dataset}.INFORMATION_SCHEMA.COLUMNS`
        WHERE table_name = '{table_name}'
        ORDER BY ordinal_position
    """,

    "distribution_shift": """
        -- Check if mean/stddev shifted significantly vs. 7-day baseline
        SELECT
            AVG(order_amount) AS mean_today,
            STDDEV(order_amount) AS stddev_today
        FROM `{table}`
        WHERE DATE(order_date) = CURRENT_DATE() - 1
    """,

    "freshness": """
        SELECT MAX(_ingested_at) AS last_loaded,
               TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(_ingested_at), HOUR) AS hours_stale
        FROM `{table}`
    """
}
```

---

## 6. Data Lineage — Tracing the Impact of Changes

Every FDE engagement needs data lineage: the ability to trace data from
its source through every transformation to its final output.

### dbt Lineage (Automatic)
```bash
# Generate lineage documentation
dbt docs generate
dbt docs serve  # opens a browser with the full lineage DAG

# Command line lineage inspection
dbt ls --select "+fct_sales"      # everything UPSTREAM of fct_sales
dbt ls --select "fct_sales+"      # everything DOWNSTREAM of fct_sales
dbt ls --select "+fct_sales+"     # everything in both directions
```

### Impact Analysis — "What breaks if I change this?"
```bash
# Before modifying stg_crm__customers, check what it affects:
dbt ls --select "stg_crm__customers+"
# Output:
# model.my_project.stg_crm__customers
# model.my_project.int_customers_enriched
# model.my_project.dim_customer
# model.my_project.fct_sales           ← this Gold table is affected!
# model.my_project.mrt_campaign_attribution  ← and this marketing table

# Before running a potentially destructive change:
dbt run --select "stg_crm__customers+" --full-refresh
# This rebuilds ONLY the affected downstream models
```

---

## 7. Client Data Profiling — First-Week Protocol

Run this profiling script on every client dataset within the first 48 hours.
The output becomes the "Data Discovery Report" deliverable.

```python
import pandas as pd
import numpy as np
from google.cloud import bigquery

def profile_bigquery_table(project: str, dataset: str, table: str) -> dict:
    """
    Comprehensive data profiling for a BigQuery table.
    Returns a report dict to be formatted into the Data Discovery Report.
    """
    client = bigquery.Client(project=project)
    full_table = f"`{project}.{dataset}.{table}`"

    report = {"table": full_table, "checks": {}}

    # 1. Basic stats
    stats = client.query(f"""
        SELECT
            COUNT(*) AS row_count,
            COUNT(*) / (1024*1024*1024) * 8  AS estimated_gb  -- rough estimate
        FROM {full_table}
    """).result().to_dataframe()
    report["row_count"] = int(stats["row_count"][0])

    # 2. Column profiles
    schema_query = f"""
        SELECT column_name, data_type, is_nullable
        FROM `{project}.{dataset}.INFORMATION_SCHEMA.COLUMNS`
        WHERE table_name = '{table}'
        ORDER BY ordinal_position
    """
    columns = client.query(schema_query).result().to_dataframe()

    col_profiles = []
    for _, col in columns.iterrows():
        col_name = col["column_name"]
        profile = client.query(f"""
            SELECT
                '{col_name}' AS column_name,
                COUNT(*) AS total_rows,
                COUNTIF(`{col_name}` IS NULL) AS null_count,
                ROUND(COUNTIF(`{col_name}` IS NULL) * 100.0 / COUNT(*), 2) AS null_pct,
                COUNT(DISTINCT `{col_name}`) AS distinct_count,
                ROUND(COUNT(DISTINCT `{col_name}`) * 100.0 / COUNT(*), 2) AS distinct_pct
            FROM {full_table}
        """).result().to_dataframe()
        col_profiles.append(profile)

    report["columns"] = pd.concat(col_profiles)

    # 3. Flag issues
    issues = []
    for _, row in report["columns"].iterrows():
        if row["null_pct"] > 50:
            issues.append(f"HIGH NULL RATE: {row['column_name']} = {row['null_pct']}%")
        if row["distinct_count"] == 1:
            issues.append(f"CONSTANT VALUE: {row['column_name']} has only 1 unique value")
        if row["distinct_pct"] > 95 and row["null_pct"] == 0:
            issues.append(f"POTENTIAL PK: {row['column_name']} is nearly unique")

    report["issues"] = issues
    return report
```
