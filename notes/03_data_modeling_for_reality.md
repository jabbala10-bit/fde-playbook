# 03 — Data Modeling for Reality

> **Why this matters for FDEs:** You will never work with a perfectly
> designed schema. You will work with 20-year-old OLTP databases with no
> documentation, Excel sheets promoted to "data warehouses", and five
> different source systems that all call the same concept by different
> names. This file teaches you how to model data correctly AND how to
> rescue broken data models in the field.

---

## 1. Normalization — Know the Rules Before You Break Them

### 1NF — First Normal Form: Eliminate Repeating Groups
```
VIOLATION:
┌────────────┬────────────────────────────────────────┐
│ order_id   │ products                               │
├────────────┼────────────────────────────────────────┤
│ 1001       │ "Widget A, Widget B, Gadget C"         │
│ 1002       │ "Widget A"                             │
└────────────┴────────────────────────────────────────┘
← Multi-valued in a single cell. Cannot join. Cannot filter by product.

FIXED (1NF):
┌────────────┬───────────────┐
│ order_id   │ product_name  │
├────────────┼───────────────┤
│ 1001       │ Widget A      │
│ 1001       │ Widget B      │
│ 1001       │ Gadget C      │
│ 1002       │ Widget A      │
└────────────┴───────────────┘
← One value per cell. Each row is uniquely identifiable.

FDE FIELD PATTERN: Client has "tags" or "categories" stored as
comma-separated strings. Use UNNEST/SPLIT to normalize at query time.
See SQL file (02) for the pattern. If this is a persistent problem,
create a normalized bridge table in the Silver layer.
```

### 2NF — Second Normal Form: No Partial Dependencies
```
VIOLATION (composite PK: order_id + product_id):
┌──────────────────────────────────────────────────────────────┐
│ order_id │ product_id │ qty │ unit_price │ customer_name     │
├──────────────────────────────────────────────────────────────┤
│ 1001     │ P001       │ 3   │ 29.99      │ Acme Corp         │
│ 1001     │ P002       │ 1   │ 49.99      │ Acme Corp         │← REPEATED
└──────────────────────────────────────────────────────────────┘
← customer_name depends ONLY on order_id, not on product_id.
  This is a partial dependency violation.

FIXED (2NF): Separate into orders + order_items tables.
```

### 3NF — Third Normal Form: No Transitive Dependencies
```
VIOLATION:
┌──────────────────────────────────────────────────────────┐
│ order_id │ customer_id │ customer_name │ customer_city   │
├──────────────────────────────────────────────────────────┤
│ 1001     │ C100        │ Acme Corp     │ New York        │
│ 1002     │ C100        │ Acme Corp     │ New York        │← REPEATED
└──────────────────────────────────────────────────────────┘
← customer_name and customer_city depend on customer_id, not order_id.
  Update Acme's city → must update every row. = Update anomaly.

FIXED (3NF): Extract to a customers dimension table.
```

### Denormalization — When to Break the Rules
```
Normalized databases minimize redundancy. But at ANALYTICAL QUERY SCALE,
joining 12 tables every time kills performance. The rule:

OLTP (transactional, write-heavy) → Normalize to 3NF minimum
OLAP (analytical, read-heavy)     → Denormalize into dimensional models

FDE rule of thumb: the Silver layer is normalized (source of truth),
the Gold layer is denormalized (optimized for consumption).
```

---

## 2. Dimensional Modeling — The Star Schema

The **Star Schema** is the universal pattern for analytical data warehouses.
Every FDE must be able to build one from scratch and explain it clearly.

### Core Concepts
```
FACT TABLE:
  - Contains MEASUREMENTS / EVENTS (what happened)
  - Each row = one business event (sale, click, visit, transaction)
  - Contains FOREIGN KEYS to dimension tables
  - Contains MEASURES (numeric values to aggregate: amount, qty, duration)
  - Should be as NARROW and TALL as possible (many rows, few wide columns)

DIMENSION TABLE:
  - Contains CONTEXT about the event (who, what, where, when, how)
  - Relatively SMALL and WIDE (few rows, many descriptive columns)
  - Changes SLOWLY (see SCD section below)
  - Examples: customer, product, date, geography, salesperson
```

### The Sales Star Schema — Built Out
```sql
-- DATE DIMENSION (always start here — every fact table needs a date key)
CREATE TABLE dim_date (
    date_key        INT PRIMARY KEY,   -- format: YYYYMMDD e.g. 20260615
    full_date       DATE,
    day_of_week     INT,               -- 1=Monday, 7=Sunday
    day_name        STRING,            -- 'Monday'
    week_of_year    INT,
    month_number    INT,
    month_name      STRING,
    quarter         INT,
    year            INT,
    is_weekday      BOOL,
    is_holiday      BOOL,
    fiscal_year     INT,               -- add client-specific fiscal calendar
    fiscal_quarter  INT
);
-- FDE TIP: generate this table for 10 years at project start.
-- NEVER join on DATE() casts — always use a pre-built date dimension.

-- CUSTOMER DIMENSION
CREATE TABLE dim_customer (
    customer_key    INT PRIMARY KEY,   -- surrogate key (auto-increment)
    customer_id     STRING,            -- natural/business key from source
    customer_name   STRING,
    email           STRING,
    tier            STRING,            -- Gold/Silver/Bronze
    region          STRING,
    country         STRING,
    acquisition_channel STRING,
    first_order_date DATE,
    -- SCD Type 2 fields (see section 3)
    valid_from      DATE,
    valid_to        DATE,
    is_current      BOOL
);

-- PRODUCT DIMENSION
CREATE TABLE dim_product (
    product_key     INT PRIMARY KEY,
    product_id      STRING,
    product_name    STRING,
    category        STRING,
    subcategory     STRING,
    brand           STRING,
    unit_cost       NUMERIC,
    list_price      NUMERIC,
    is_active       BOOL
);

-- SALES FACT TABLE (one row per order line item)
CREATE TABLE fact_sales (
    sale_key        INT PRIMARY KEY,   -- surrogate key
    date_key        INT REFERENCES dim_date,
    customer_key    INT REFERENCES dim_customer,
    product_key     INT REFERENCES dim_product,
    -- Foreign keys to other dims as needed
    -- MEASURES (the numeric values analysts aggregate)
    quantity        INT,
    unit_price      NUMERIC,
    discount_amount NUMERIC,
    net_amount      NUMERIC,           -- unit_price * quantity - discount
    cost_amount     NUMERIC,           -- from product dim at time of sale
    gross_margin    NUMERIC            -- net_amount - cost_amount
);
```

### Star Schema Query Pattern
```sql
-- Total sales by product category and customer tier, last 3 months
SELECT
    p.category,
    c.tier,
    SUM(f.net_amount)   AS total_sales,
    SUM(f.gross_margin) AS total_margin,
    COUNT(DISTINCT f.customer_key) AS unique_customers
FROM fact_sales f
JOIN dim_date d     ON f.date_key     = d.date_key
JOIN dim_customer c ON f.customer_key = c.customer_key AND c.is_current = TRUE
JOIN dim_product p  ON f.product_key  = p.product_key
WHERE d.full_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 MONTH)
GROUP BY p.category, c.tier
ORDER BY total_sales DESC;
```

---

## 3. Slowly Changing Dimensions (SCDs)

One of the most important data modeling concepts. Client data changes
over time — customer moved cities, product changed price, employee changed
department. How do you handle this in a data warehouse?

### SCD Type 1 — Overwrite (no history)
```sql
-- Just UPDATE the record. Old value is gone forever.
-- Use when: history doesn't matter (e.g., correcting a typo)
UPDATE dim_customer
SET email = 'new@email.com'
WHERE customer_id = 'C100';

-- PROBLEM: Now you can't tell what the email was last month.
-- Use only for corrections, not for real business changes.
```

### SCD Type 2 — New Row (full history)
```sql
-- Most powerful and most common. When an attribute changes,
-- CLOSE the old record and INSERT a new row.

-- Customer C100 moves from 'New York' to 'Austin' on 2026-06-01:

-- Step 1: Close the old record
UPDATE dim_customer
SET valid_to = '2026-05-31', is_current = FALSE
WHERE customer_id = 'C100' AND is_current = TRUE;

-- Step 2: Insert a new row with the new city
INSERT INTO dim_customer
VALUES (
    NEXTVAL('customer_key_seq'),  -- new surrogate key
    'C100',                        -- same natural key
    'Acme Corp',
    'New York',
    -- ... other fields ...
    '2026-06-01',   -- valid_from
    '9999-12-31',   -- valid_to (open-ended = still current)
    TRUE            -- is_current
);

-- Now you can answer time-based questions:
-- "What city was customer C100 in on 2026-03-15?" → New York
-- "What city is customer C100 now?" → Austin (WHERE is_current = TRUE)
```

### SCD Type 3 — Previous Value Column
```sql
-- Store only ONE prior value. Simple but loses deeper history.
-- Add columns: previous_city, city_change_date
ALTER TABLE dim_customer
ADD COLUMN previous_city STRING,
ADD COLUMN city_change_date DATE;

-- When city changes:
UPDATE dim_customer
SET previous_city = city, city_change_date = CURRENT_DATE, city = 'Austin'
WHERE customer_id = 'C100';

-- Good for: "What was their LAST value?" — e.g., previous job title
-- Bad for: "What was their value 2 years ago?" — only 1 level of history
```

---

## 4. Schema Design for GCP / BigQuery Reality

### Nested and Repeated Fields (BigQuery Superpower)
```sql
-- BigQuery natively supports STRUCT (nested) and ARRAY (repeated) types
-- This avoids expensive JOINs on frequently-read nested data

CREATE TABLE orders (
    order_id    STRING,
    customer    STRUCT<             -- NESTED: one object
                    id      STRING,
                    name    STRING,
                    email   STRING,
                    tier    STRING
                >,
    line_items  ARRAY<STRUCT<       -- REPEATED: array of objects
                    product_id  STRING,
                    product_name STRING,
                    quantity    INT64,
                    unit_price  FLOAT64
                >>,
    created_at  TIMESTAMP
);

-- Query nested fields: use dot notation
SELECT
    order_id,
    customer.name,
    customer.tier,
    ARRAY_LENGTH(line_items) AS item_count
FROM orders;

-- Unnest repeated fields: use CROSS JOIN UNNEST
SELECT
    o.order_id,
    o.customer.name,
    li.product_name,
    li.quantity * li.unit_price AS line_total
FROM orders o
CROSS JOIN UNNEST(o.line_items) AS li;
```

### When to Use Nested vs. Flat

```
USE NESTED/REPEATED when:
  ✓ The child rows ALWAYS belong to one parent (order items → order)
  ✓ You always query parent and child together (never child alone)
  ✓ You want to avoid JOIN cost on very large tables
  ✓ The child has a natural upper bound (< 1000 items per parent)

USE SEPARATE TABLES (normalized) when:
  ✓ You need to query child data independently
  ✓ Child data is reused across multiple parent entities
  ✓ Child data is updated independently of the parent
  ✓ Array would be unbounded (could have millions of items)
```

---

## 5. Data Vault — The Modern Scalable Alternative

For large enterprises with many source systems that change over time,
**Data Vault 2.0** scales better than dimensional modeling.

### Core Components
```
HUB: Unique business keys from each source system
     (hub_customer: customer_id from CRM, ERP, eCommerce)

LINK: Relationships between hubs
     (link_customer_order: connects hub_customer + hub_order)

SATELLITE: Descriptive attributes that change over time
     (sat_customer_details: name, email, address with load_date)
```

### When to Use Data Vault vs. Star Schema

```
┌────────────────────────┬────────────────────────┬────────────────────────┐
│ Factor                 │ Star Schema             │ Data Vault 2.0         │
├────────────────────────┼────────────────────────┼────────────────────────┤
│ Source systems         │ 1-3 sources            │ 5+ sources             │
│ Schema changes         │ Infrequent             │ Frequent               │
│ History requirement    │ Basic                  │ Full audit trail       │
│ Team SQL expertise     │ Standard               │ High                   │
│ Query complexity       │ Simple (few joins)     │ Higher (always joins)  │
│ Loading pattern        │ Full refresh OK        │ Append-only incremental│
│ Auditability           │ Medium                 │ Very high              │
└────────────────────────┴────────────────────────┴────────────────────────┘

FDE DEFAULT: Use Star Schema for most engagements unless the client
explicitly requires Data Vault (usually financial services or healthcare
with strict audit requirements). Data Vault adds complexity the client's
team may not be able to maintain after you leave.
```

---

## 6. The Entity-Relationship Diagram (ERD) as Communication Tool

FDEs use ERDs to communicate data models to non-technical stakeholders.
Draw one on a whiteboard in the first week. It establishes authority.

```
[Customer]          [Order]              [Order_Item]        [Product]
──────────          ─────────            ────────────        ─────────
customer_id (PK) ←→ order_id (PK)    ←→ order_id (FK)  ←→ product_id (PK)
name                customer_id (FK)     product_id (FK)    name
email               order_date           quantity           category
tier                status               unit_price         unit_cost
region              total_amount         discount           is_active

  One Customer     One Order            Many Order_Items    One Product
  can have many    has many             each have one       can be in
  Orders (1:N)     Order_Items (1:N)    Product (N:1)       many Orders (N:M)
```

**ERD Interview Tips:**
- Always identify the "grain" of fact tables (what does one row represent?)
- Draw cardinality explicitly (1:1, 1:N, M:N)
- M:N relationships always need a bridge/junction table
- Ask about temporal aspects: "Does this data change? Do we need history?"

---

## 7. Field Scenario: "Our Data is a Mess"

When a client says "our data is a mess", it means one of these five things:

| Problem | Symptom | Your Response |
|---|---|---|
| No unified identifiers | Same customer has 3 different IDs in 3 systems | Entity resolution: build a golden record using probabilistic matching |
| Inconsistent categorical values | "NY", "New York", "new york", "NY State" all in same column | Reference data / lookup table normalization in Silver layer |
| Missing required fields | 60% of rows have NULL in a critical field | Imputation strategy (median/mode) OR default value + quality flag |
| Duplicate records | Same order exists twice with slightly different timestamps | Deduplication using ROW_NUMBER() on natural key + window function |
| Schema drift | CSV files change column order/names between exports | Schema validation gate at ingestion; alert + quarantine on mismatch |
