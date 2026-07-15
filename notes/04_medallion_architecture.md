# 04 — Medallion Architecture: Bronze → Silver → Gold

> **Why this matters for FDEs:** The Medallion Architecture is the standard
> data pipeline pattern you will deploy at virtually every engagement.
> It gives you a clear mental model to explain to clients, a reproducible
> structure for dbt projects, and a natural place for data quality gates.

---

## 1. The Three-Layer Mental Model

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        MEDALLION ARCHITECTURE                           │
│                                                                          │
│  SOURCE                BRONZE              SILVER              GOLD      │
│  SYSTEMS               (Raw)               (Cleaned)           (Business)│
│  ─────────             ─────────           ─────────           ─────────│
│  CRM API      ──────►  Exact copy of     Deduplicated       Fact tables  │
│  ERP DB       ──────►  source data       Normalized         Dimensions   │
│  CSV files    ──────►  No transforms     Type-cast          KPIs/metrics │
│  Kafka topics ──────►  Append-only       Validated          One Big Table│
│  IoT sensors  ──────►  Immutable         Standardized       ready for BI │
│                        Timestamped       Enriched           or AI        │
│                                                                          │
│  FREQUENCY:  Real-time / hourly         Hourly / daily       Daily / on-demand
│  OWNER:      Data Engineering           Data Engineering     Analytics Eng
│  ACCESS:     Restricted (raw PII)       Data team            All consumers
└──────────────────────────────────────────────────────────────────────────┘
```

### The Core Principle: Immutability at Bronze

**Bronze is ALWAYS a faithful copy of the source. No exceptions.**

The most common FDE mistake is transforming data in the Bronze layer.
When something breaks downstream, you need to re-run from Bronze.
If Bronze was transformed, you've lost your audit trail.

```
CORRECT Bronze ingestion:
  source_row → bronze_row (identical columns + 3 metadata columns added)

The 3 mandatory Bronze metadata columns:
  _ingested_at    TIMESTAMP   -- when the row arrived in our system
  _source_file    STRING      -- which file/API/topic this came from
  _source_offset  STRING      -- Kafka offset, file line number, or API cursor

NEVER in Bronze:
  ✗ Filtering rows (even nulls)
  ✗ Renaming columns
  ✗ Joining with other tables
  ✗ Business logic of any kind
```

---

## 2. GCP Implementation: What Goes Where

```
BRONZE LAYER → Cloud Storage (GCS) + External BigQuery Tables
  - Raw files land in GCS: gs://[project]-raw/source_name/YYYY/MM/DD/
  - BigQuery External Tables read directly from GCS (no data copy)
  - Alternatively: BigQuery native tables with append-only inserts
  - Partitioned by _ingested_at DATE
  - Access: restricted to DE team only

SILVER LAYER → BigQuery Native Tables (Clustered + Partitioned)
  - Managed via dbt models (see section 4)
  - schema: silver.[source_system].[entity]
  - e.g.: silver.crm.customers, silver.erp.orders
  - Full history preserved (SCD Type 2 or append-only)
  - Access: data team + approved analysts

GOLD LAYER → BigQuery Native Tables (materialized views or tables)
  - schema: gold.[domain].[view_name]
  - e.g.: gold.sales.daily_revenue, gold.product.inventory_health
  - Optimized for BI tools (Looker, Tableau) and AI consumption
  - Denormalized for query performance
  - Access: all consumers (BI, DS, ML teams)
```

---

## 3. dbt — The Transformation Engine

**dbt (data build tool)** is the standard way to manage the Silver and
Gold layers. It brings software engineering practices to SQL:
version control, testing, documentation, and incremental loads.

### dbt Project Structure
```
my_project/
├── dbt_project.yml          ← project configuration
├── profiles.yml             ← database connection (kept out of git)
├── models/
│   ├── staging/             ← direct map from Bronze (1:1 source)
│   │   ├── _sources.yml     ← declare your source tables here
│   │   ├── stg_crm__customers.sql
│   │   └── stg_erp__orders.sql
│   ├── intermediate/        ← business logic, joins (Silver)
│   │   ├── int_customers_enriched.sql
│   │   └── int_order_financials.sql
│   └── marts/               ← final output tables (Gold)
│       ├── finance/
│       │   ├── fct_sales.sql
│       │   └── dim_customer.sql
│       └── marketing/
│           └── mrt_campaign_attribution.sql
├── tests/
│   ├── generic/             ← reusable test definitions
│   └── singular/            ← one-off SQL tests
├── macros/
│   └── generate_surrogate_key.sql
└── seeds/
    └── country_codes.csv    ← small reference tables
```

### dbt Model: Staging Layer (Bronze → Silver)
```sql
-- models/staging/stg_crm__customers.sql
-- Convention: stg_[source]__[entity].sql (double underscore)

{{
    config(
        materialized = 'view',      -- staging models are usually views
        schema = 'staging'          -- placed in the staging schema
    )
}}

WITH source AS (
    -- reference the raw source table declared in _sources.yml
    SELECT * FROM {{ source('crm', 'raw_customers') }}
),

renamed AS (
    SELECT
        -- Rename to standard naming convention
        customer_id                         AS customer_id,
        TRIM(UPPER(customer_name))          AS customer_name,   -- normalize
        LOWER(TRIM(email_address))          AS email,            -- normalize
        SAFE_CAST(created_date AS DATE)     AS created_at,      -- type-cast safely
        SAFE_CAST(annual_revenue AS FLOAT64) AS annual_revenue,
        -- Standardize categorical values
        CASE
            WHEN UPPER(TRIM(customer_tier)) IN ('GOLD', 'G', '1') THEN 'Gold'
            WHEN UPPER(TRIM(customer_tier)) IN ('SILVER', 'S', '2') THEN 'Silver'
            WHEN UPPER(TRIM(customer_tier)) IN ('BRONZE', 'B', '3') THEN 'Bronze'
            ELSE 'Unknown'
        END AS customer_tier,
        -- Pass through audit fields
        _ingested_at,
        _source_file
    FROM source
    -- ONLY filter at staging level for structural impossibilities
    WHERE customer_id IS NOT NULL  -- rows without a PK are useless
)

SELECT * FROM renamed
```

### dbt Sources Declaration
```yaml
# models/staging/_sources.yml
version: 2

sources:
  - name: crm
    database: my-gcp-project
    schema: bronze_crm
    description: "Salesforce CRM raw data loaded via Fivetran"
    tables:
      - name: raw_customers
        description: "Customer records from Salesforce"
        loaded_at_field: _ingested_at   # dbt uses this for freshness checks
        freshness:
          warn_after: {count: 12, period: hour}
          error_after: {count: 24, period: hour}
        columns:
          - name: customer_id
            description: "Salesforce Account ID"
            tests:
              - not_null
              - unique
          - name: email_address
            tests:
              - not_null
```

### dbt Model: Intermediate Layer (Business Logic)
```sql
-- models/intermediate/int_order_financials.sql
-- Silver layer: joins, business logic, no final aggregation yet

{{
    config(
        materialized = 'incremental',
        unique_key = 'order_line_id',
        partition_by = {
            'field': 'order_date',
            'data_type': 'date',
            'granularity': 'day'
        },
        cluster_by = ['customer_id', 'product_id']
    )
}}

WITH orders AS (
    SELECT * FROM {{ ref('stg_erp__orders') }}          -- ref() creates lineage
),

order_items AS (
    SELECT * FROM {{ ref('stg_erp__order_items') }}
),

products AS (
    SELECT * FROM {{ ref('stg_pim__products') }}
),

enriched AS (
    SELECT
        oi.order_line_id,
        o.order_id,
        o.customer_id,
        o.order_date,
        oi.product_id,
        p.category,
        p.unit_cost,
        oi.quantity,
        oi.unit_price,
        oi.discount_pct,
        -- Business calculations
        oi.unit_price * oi.quantity                AS gross_revenue,
        oi.unit_price * oi.quantity * (1 - oi.discount_pct) AS net_revenue,
        p.unit_cost * oi.quantity                  AS cogs,
        (oi.unit_price * (1 - oi.discount_pct) - p.unit_cost) * oi.quantity
                                                   AS gross_profit
    FROM order_items oi
    JOIN orders   o ON oi.order_id   = o.order_id
    JOIN products p ON oi.product_id = p.product_id
)

SELECT * FROM enriched

-- INCREMENTAL FILTER: only process new/changed records
{% if is_incremental() %}
WHERE order_date > (SELECT MAX(order_date) FROM {{ this }})
{% endif %}
```

### dbt Model: Gold Layer (Final Output)
```sql
-- models/marts/finance/fct_sales.sql
-- Gold layer: final aggregated output for consumption

{{
    config(
        materialized = 'table',   -- materialize as a physical table for BI speed
        partition_by = {'field': 'order_date', 'data_type': 'date'},
        cluster_by = ['region', 'product_category']
    )
}}

WITH financials AS (
    SELECT * FROM {{ ref('int_order_financials') }}
),

customers AS (
    SELECT * FROM {{ ref('dim_customer') }}
),

final AS (
    SELECT
        f.order_date,
        f.order_id,
        f.order_line_id,
        c.customer_name,
        c.region,
        c.tier AS customer_tier,
        f.category AS product_category,
        f.quantity,
        f.gross_revenue,
        f.net_revenue,
        f.cogs,
        f.gross_profit,
        ROUND(f.gross_profit / NULLIF(f.net_revenue, 0) * 100, 2) AS gross_margin_pct
    FROM financials f
    LEFT JOIN customers c ON f.customer_id = c.customer_id
)

SELECT * FROM final
```

---

## 4. dbt Testing — Data Quality as Code

```yaml
# models/marts/finance/_models.yml
version: 2

models:
  - name: fct_sales
    description: "One row per order line item with financial metrics"
    tests:
      - dbt_utils.expression_is_true:
          expression: "gross_profit <= net_revenue"   # can't profit more than revenue
      - dbt_utils.expression_is_true:
          expression: "quantity > 0"
    columns:
      - name: order_line_id
        tests:
          - unique                   # built-in: no duplicates
          - not_null                 # built-in: no nulls
      - name: order_date
        tests:
          - not_null
          - dbt_utils.not_future_date  # no future-dated records
      - name: gross_margin_pct
        tests:
          - dbt_utils.accepted_range:
              min_value: -100         # can be negative (loss)
              max_value: 100          # can't be more than 100%
      - name: customer_tier
        tests:
          - accepted_values:          # built-in: only these values allowed
              values: ['Gold', 'Silver', 'Bronze', 'Unknown']
```

### Singular Tests (Custom SQL assertions)
```sql
-- tests/no_orphaned_order_items.sql
-- This test FAILS if it returns ANY rows (finds orphaned items)

SELECT oi.order_line_id
FROM {{ ref('fct_sales') }} oi
LEFT JOIN {{ ref('fct_orders') }} o ON oi.order_id = o.order_id
WHERE o.order_id IS NULL  -- order_line exists without a parent order = data bug
```

---

## 5. Incremental vs. Full Refresh — The Critical Decision

```
FULL REFRESH:
  dbt run --full-refresh --select my_model
  → Drops and recreates the entire table
  → Safe: always produces correct output
  → Expensive: processes ALL historical data every run
  → Use for: dimension tables, slowly-changing lookups, < 1M rows

INCREMENTAL:
  → Appends/merges only NEW or CHANGED data
  → Fast: processes only today's data (or since last run)
  → Risky: late-arriving data or source fixes may not backfill
  → Use for: fact tables, event logs, > 10M rows

INCREMENTAL STRATEGIES in dbt:
  - append      → only add new rows (no updates)
  - merge       → upsert based on unique_key (handles updates)
  - insert_overwrite → replace entire partitions (best for BigQuery)
  - delete+insert → delete matching rows then re-insert (slow but safe)

FDE RECOMMENDATION: use insert_overwrite in BigQuery with daily
partitions. Replace yesterday's partition on every run. This handles
late-arriving data naturally without complex merge logic.
```

---

## 6. The Data Pipeline Runbook Template

Every pipeline you build for a client must include a runbook. Template:

```markdown
# Pipeline: [Name] Runbook

## What it does
One-paragraph plain English description.

## Schedule
Cron: `0 6 * * *` (6am UTC daily)
Expected duration: ~15 minutes

## Dependencies
- Source: GCS bucket gs://[project]-raw/crm/customers/
- dbt models: stg_crm__customers → int_customers_enriched → dim_customer
- Tools: Cloud Composer (Airflow), dbt 1.7, BigQuery

## Health Checks
- Cloud Monitoring alert: fct_sales row count < 10,000 for any day
- dbt test: all tests must pass before Gold materialization
- SLA: Gold tables ready by 8am UTC

## Common Failures

### "Table not found: bronze_crm.raw_customers"
Cause: Fivetran sync didn't run last night.
Fix: Check Fivetran dashboard → manually trigger sync → rerun dbt.

### "Row count anomaly: 0 rows for yesterday"
Cause: Source system maintenance window.
Fix: Check source system status → if confirmed outage, backfill manually.

### "dbt test failure: not_null on order_id"
Cause: Source bug introduced NULLs in order_id field.
Fix: Check bronze layer for NULLs → alert source team → quarantine rows.

## Escalation
1st: Data Engineering on-call Slack #data-alerts
2nd: [Client contact name] + [Client email]
```
