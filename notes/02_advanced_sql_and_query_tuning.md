# 02 — Advanced SQL & Query Tuning

> **Why this matters for FDEs:** Your first week at any client site
> involves a data audit. If you can't read an EXPLAIN plan, write a
> Window Function, or untangle a 20-year-old schema, you cannot build
> anything on top of it. SQL is the universal language of every
> enterprise data system you will ever touch.

---

## 1. Window Functions — Beyond GROUP BY

Window functions compute a value across a "window" of rows RELATED to
the current row, WITHOUT collapsing the rows like GROUP BY does.

### Syntax
```sql
function_name(expression) OVER (
    [PARTITION BY col1, col2]   -- defines the "window group"
    [ORDER BY col3]             -- defines the order within the window
    [ROWS/RANGE BETWEEN ...]    -- defines the frame (optional)
)
```

### The Essential Window Functions

#### ROW_NUMBER — unique sequential rank per partition
```sql
-- Use case: de-duplicate records, keep the latest per patient
SELECT *
FROM (
    SELECT
        patient_id,
        visit_date,
        diagnosis,
        ROW_NUMBER() OVER (
            PARTITION BY patient_id
            ORDER BY visit_date DESC
        ) AS rn
    FROM patient_visits
) ranked
WHERE rn = 1;
-- FDE REALITY: this exact pattern removes duplicates from client
-- legacy systems that have no primary key enforcement
```

#### RANK / DENSE_RANK — handle ties differently
```sql
-- RANK: 1,1,3,4 (skips after tie)
-- DENSE_RANK: 1,1,2,3 (no skipping)
SELECT
    product_id,
    revenue,
    RANK()       OVER (ORDER BY revenue DESC) AS rank_with_gaps,
    DENSE_RANK() OVER (ORDER BY revenue DESC) AS rank_no_gaps
FROM sales;
```

#### LAG / LEAD — access previous/next row values
```sql
-- Use case: calculate period-over-period change
SELECT
    month,
    revenue,
    LAG(revenue, 1)  OVER (ORDER BY month) AS prev_month_revenue,
    LEAD(revenue, 1) OVER (ORDER BY month) AS next_month_revenue,
    revenue - LAG(revenue, 1) OVER (ORDER BY month) AS mom_change
FROM monthly_revenue;
```

#### SUM/AVG with ROWS BETWEEN — rolling calculations
```sql
-- 7-day rolling average — vital for smoothing noisy sensor/transaction data
SELECT
    date,
    daily_transactions,
    AVG(daily_transactions) OVER (
        ORDER BY date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW  -- 7 rows including current
    ) AS rolling_7day_avg
FROM daily_stats;

-- Running total
SELECT
    date,
    amount,
    SUM(amount) OVER (
        PARTITION BY account_id
        ORDER BY date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_balance
FROM transactions;
```

#### NTILE — bucket rows into percentiles
```sql
-- Segment customers into quartiles by spend
SELECT
    customer_id,
    total_spend,
    NTILE(4) OVER (ORDER BY total_spend) AS spend_quartile
FROM customer_spend;
```

---

## 2. Recursive CTEs — Hierarchical Data Problems

CTEs (Common Table Expressions) become RECURSIVE when they reference
themselves. Essential for org charts, category trees, bill-of-materials,
and any parent-child hierarchical relationship.

```sql
-- Standard BigQuery syntax (also works in PostgreSQL, SQL Server)
-- Problem: find all subordinates of a given manager in an org chart

WITH RECURSIVE org_hierarchy AS (
    -- Base case: start with the root manager
    SELECT
        employee_id,
        name,
        manager_id,
        0 AS level,
        CAST(name AS STRING) AS path
    FROM employees
    WHERE employee_id = 1001  -- start at the CEO

    UNION ALL

    -- Recursive step: find all direct reports of the current level
    SELECT
        e.employee_id,
        e.name,
        e.manager_id,
        h.level + 1,
        h.path || ' → ' || e.name
    FROM employees e
    INNER JOIN org_hierarchy h ON e.manager_id = h.employee_id
    WHERE h.level < 10  -- CRITICAL: always add a depth limit to prevent
                         -- infinite loops on circular reference bugs
)
SELECT * FROM org_hierarchy ORDER BY level, name;
```

### BigQuery-specific: PATH-BASED hierarchy flattening
```sql
-- In BigQuery, use ARRAY_AGG for flattening trees efficiently
-- More efficient for large hierarchies than recursive CTEs
WITH RECURSIVE cat_tree AS (
    SELECT category_id, parent_id, name, [name] AS full_path
    FROM categories WHERE parent_id IS NULL  -- root nodes
    UNION ALL
    SELECT c.category_id, c.parent_id, c.name,
           ARRAY_CONCAT(t.full_path, [c.name])
    FROM categories c JOIN cat_tree t ON c.parent_id = t.category_id
)
SELECT *, ARRAY_TO_STRING(full_path, ' > ') AS breadcrumb
FROM cat_tree;
```

---

## 3. Reading EXPLAIN Plans — Your Most Critical Field Skill

### BigQuery EXPLAIN (use INFORMATION_SCHEMA)
```sql
-- BigQuery uses job information, not EXPLAIN directly
-- Run the query, then inspect via:
SELECT
    stage_id,
    name,
    status,
    input_stages,
    steps,
    records_read,
    records_written,
    shuffle_output_bytes,
    wait_ratio_max,
    read_ratio_max,
    compute_ratio_max,
    write_ratio_max
FROM
    INFORMATION_SCHEMA.JOBS_BY_PROJECT,
    UNNEST(query_plan) AS stage
WHERE job_id = '[your-job-id]'
ORDER BY stage_id;
```

### PostgreSQL EXPLAIN ANALYZE
```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT *
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.status = 'pending';

/* Reading the output — what to look for:
   
   Seq Scan on orders (cost=0.00..450000.00 rows=10000000 ...)
   ← BAD: full table scan on a large table. Missing index.
   
   Index Scan using idx_orders_status on orders
   ← GOOD: using an index for the WHERE clause
   
   Hash Join (cost=100..5000 rows=5000 ...)
     Hash Cond: (o.customer_id = c.id)
     Buffers: shared hit=50 read=10000
   ← "read=10000" means 10K disk pages read → consider increasing
     shared_buffers or adding a covering index
   
   actual time=0.050..23000.000 rows=1000000 (loops=1)
   ← actual 23 seconds vs estimate, high row count = data skew or
     bad statistics. Run ANALYZE on the table.
*/
```

### The 5 Things to Find Immediately in Any Slow Query Plan

```
1. SEQUENTIAL SCAN on a large table with a WHERE clause
   → Missing index. Add one on the filter column.

2. NESTED LOOP with a large outer table
   → For large tables, a Hash Join or Merge Join is usually faster.
   → Check if inner table has an index on the join column.

3. actual rows >> estimated rows (big difference)
   → Statistics are stale. Run ANALYZE (PostgreSQL) or wait for
     auto-statistics update (BigQuery). Otherwise the planner will
     keep making wrong choices.

4. Sort operation on a non-indexed column with LIMIT
   → Add an index to avoid a full sort before limiting.

5. High read_bytes but low output in BigQuery
   → Table is not partitioned/clustered on the filter column.
   → 1TB scan for 1KB result = 1000x cost waste. Partition the table.
```

---

## 4. BigQuery-Specific Performance Patterns

### Partitioning — filter by date/int to PRUNE whole partitions
```sql
-- CREATE a partitioned table (do this at table creation time)
CREATE TABLE my_dataset.events
PARTITION BY DATE(event_timestamp)
CLUSTER BY event_type, user_id
OPTIONS (
    partition_expiration_days = 365,  -- auto-delete old partitions = cost control
    require_partition_filter = TRUE   -- FORCE all queries to use a partition filter
                                       -- prevents accidental full scans
)
AS
SELECT * FROM raw_events;

-- Now queries MUST include a date filter — they read only matching partitions
SELECT COUNT(*)
FROM my_dataset.events
WHERE DATE(event_timestamp) BETWEEN '2026-01-01' AND '2026-06-30'  -- reads 6 months
AND event_type = 'purchase';
-- Without partitioning: scans ALL data. With partitioning: scans 6 months only.
-- Cost difference at 10TB total: 10TB vs ~5TB = ~$25 vs $12.50 per query
```

### Clustering — physical sort order for filter pruning
```sql
-- Clustering organizes data within each partition by the specified columns.
-- Queries filtering on cluster columns skip entire blocks.
-- Best for high-cardinality columns frequently used in WHERE/GROUP BY.

-- Rule: partition = date (low cardinality); cluster = IDs/categories (high card.)
CREATE TABLE sales
PARTITION BY DATE(sale_date)
CLUSTER BY region, product_category, salesperson_id;
-- A query WHERE region = 'APAC' AND product_category = 'Electronics'
-- reads only the relevant blocks, not the whole partition.
```

### Avoid SELECT * at scale
```sql
-- BAD: scans all columns, even those not needed (BigQuery is columnar)
SELECT * FROM orders WHERE status = 'pending';

-- GOOD: scan only required columns — in BigQuery, each column costs separately
SELECT order_id, customer_id, total, created_at
FROM orders WHERE status = 'pending';
-- At petabyte scale, this can be 10-50x cheaper per query.
```

### Approximate functions for massive aggregations
```sql
-- Counting distinct users at scale — EXACT COUNT DISTINCT is expensive
-- APPROX_COUNT_DISTINCT uses HyperLogLog, error < 1%, 100x faster/cheaper

SELECT
    date,
    APPROX_COUNT_DISTINCT(user_id) AS approx_dau,  -- for dashboards: fine
    COUNT(DISTINCT user_id) AS exact_dau            -- for billing/contracts: required
FROM events
GROUP BY date;
```

---

## 5. Common Client Data Disasters — And How to Fix Them

### Problem: No Primary Keys (Client Legacy DB)
```sql
-- Identify duplicate records without a PK
SELECT
    natural_key_col1,
    natural_key_col2,
    COUNT(*) AS occurrences
FROM legacy_table
GROUP BY 1, 2
HAVING COUNT(*) > 1
ORDER BY occurrences DESC
LIMIT 100;  -- find the worst offenders first

-- Fix: de-duplicate using ROW_NUMBER (see Window Functions section)
```

### Problem: Dates stored as strings or integers
```sql
-- Client stores dates as 'YYYYMMDD' integers (common in mainframe exports)
SELECT
    PARSE_DATE('%Y%m%d', CAST(date_int AS STRING)) AS proper_date,
    -- BigQuery version:
    DATE(CAST(SUBSTR(CAST(date_int AS STRING), 1, 4) AS INT64),
         CAST(SUBSTR(CAST(date_int AS STRING), 5, 2) AS INT64),
         CAST(SUBSTR(CAST(date_int AS STRING), 7, 2) AS INT64))
    AS bq_date
FROM legacy_transactions;
```

### Problem: NULL meaning different things in different columns
```sql
-- Always profile NULLs BEFORE building on top of client data
SELECT
    column_name,
    COUNT(*) AS total_rows,
    COUNTIF(column_value IS NULL) AS null_count,
    ROUND(COUNTIF(column_value IS NULL) * 100.0 / COUNT(*), 2) AS null_pct,
    COUNT(DISTINCT column_value) AS distinct_values
FROM (
    SELECT column_name, column_value
    FROM your_table
    UNPIVOT (column_value FOR column_name IN (col1, col2, col3, col4))
)
GROUP BY column_name
ORDER BY null_pct DESC;
```

### Problem: Multi-valued columns (comma-separated in one field)
```sql
-- "tags" column contains "fraud,high_risk,manual_review"
-- Explode into rows for proper analysis

-- BigQuery:
SELECT
    transaction_id,
    tag
FROM transactions,
UNNEST(SPLIT(tags, ',')) AS tag  -- UNNEST explodes the array
WHERE TRIM(tag) != '';

-- Then re-aggregate cleanly
SELECT tag, COUNT(*) AS transaction_count
FROM (SELECT id, TRIM(t) AS tag FROM tbl, UNNEST(SPLIT(tags,',')) t)
GROUP BY tag ORDER BY transaction_count DESC;
```

---

## 6. Query Optimization Checklist — Field Reference

Before delivering any query to a client in production, run through this:

```
□ Is there a WHERE clause that could use an index/partition filter?
□ Is SELECT * being used on a wide table? → Specify only needed columns
□ Are there multiple JOINs? → Check JOIN order (smallest result set first)
□ Is there a large GROUP BY? → Can it be replaced with approx functions?
□ Are statistics up to date? (ANALYZE in PostgreSQL, auto in BigQuery)
□ Is the result being LIMIT'd without an ORDER BY index?
□ Are subqueries being used where a JOIN or CTE would be faster?
□ Is there string manipulation in a WHERE clause? (kills index usage)
□ Are there implicit type casts in JOIN conditions? (kills index usage)
□ Has the query been tested at full production data volume, not just a sample?
```

---

## 7. Interview-Ready SQL Scenarios

### Scenario: "Find customers who purchased in Jan but not in Feb"
```sql
-- Set difference using EXCEPT (clean)
SELECT customer_id FROM orders WHERE order_month = '2026-01'
EXCEPT
SELECT customer_id FROM orders WHERE order_month = '2026-02';

-- Or using LEFT JOIN (more flexible — lets you see both months)
SELECT jan.customer_id
FROM (SELECT DISTINCT customer_id FROM orders WHERE order_month = '2026-01') jan
LEFT JOIN (SELECT DISTINCT customer_id FROM orders WHERE order_month = '2026-02') feb
    ON jan.customer_id = feb.customer_id
WHERE feb.customer_id IS NULL;
```

### Scenario: "Calculate 30-day retention rate"
```sql
WITH first_purchases AS (
    SELECT customer_id, MIN(DATE(order_date)) AS first_purchase_date
    FROM orders GROUP BY customer_id
),
repeat_purchases AS (
    SELECT DISTINCT o.customer_id
    FROM orders o
    JOIN first_purchases fp ON o.customer_id = fp.customer_id
    WHERE DATE(o.order_date) > fp.first_purchase_date
    AND DATE(o.order_date) <= DATE_ADD(fp.first_purchase_date, INTERVAL 30 DAY)
)
SELECT
    COUNT(DISTINCT r.customer_id) AS retained,
    COUNT(DISTINCT f.customer_id) AS total_new,
    ROUND(COUNT(DISTINCT r.customer_id) * 100.0 / COUNT(DISTINCT f.customer_id), 2)
        AS retention_rate_pct
FROM first_purchases f
LEFT JOIN repeat_purchases r ON f.customer_id = r.customer_id;
```

### Scenario: "Detect session gaps in clickstream data"
```sql
-- Define a new session as: gap of > 30 minutes between events
WITH session_flags AS (
    SELECT
        user_id,
        event_time,
        LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time) AS prev_event,
        CASE
            WHEN TIMESTAMP_DIFF(event_time,
                LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time),
                MINUTE) > 30
            OR LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time) IS NULL
            THEN 1 ELSE 0
        END AS new_session_flag
    FROM clickstream
),
sessions AS (
    SELECT *,
        SUM(new_session_flag) OVER (PARTITION BY user_id ORDER BY event_time) AS session_id
    FROM session_flags
)
SELECT user_id, session_id, MIN(event_time) AS session_start,
       MAX(event_time) AS session_end,
       COUNT(*) AS events_in_session
FROM sessions
GROUP BY user_id, session_id;
```
