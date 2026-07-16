# Relational Databases — Complete Reference (Beginner → Expert)

Consolidated reference: core concepts, every data type family, query writing
from trivial to advanced, indexing, query planning, performance tuning,
scalability, and operational strategy. Examples are ANSI SQL by default;
dialect-specific notes call out **PostgreSQL**, **MySQL**, and **SQL Server**
explicitly where behavior diverges.

---

## 1. Core Concepts

- **Relation** = table. **Tuple** = row. **Attribute** = column. A table is a
  set of rows (no inherent order, no duplicates in pure relational theory —
  SQL relaxes both).
- **Schema** = the structural definition (tables, columns, types, constraints)
  vs **instance** = the actual data at a point in time.
- **Key types**:
  - *Candidate key*: any minimal column set that uniquely identifies a row.
  - *Primary key (PK)*: the chosen candidate key; not null, unique, one per table.
  - *Natural key*: a PK derived from real-world data (e.g., email, SSN).
  - *Surrogate key*: a PK with no business meaning (auto-increment int, UUID) —
    preferred in practice because natural keys can change and business logic
    leaking into a PK causes painful migrations later.
  - *Foreign key (FK)*: a column referencing another table's PK — enforces
    referential integrity.
  - *Composite key*: PK made of multiple columns.
- **ACID**:
  - *Atomicity*: a transaction is all-or-nothing.
  - *Consistency*: a transaction moves the DB from one valid state to another
    (constraints, triggers, FKs all hold before and after).
  - *Isolation*: concurrent transactions don't see each other's uncommitted
    intermediate state (degree governed by isolation level, §11).
  - *Durability*: once committed, survives a crash (WAL/redo log fsynced).
- **CRUD** maps to SQL: Create → `INSERT`, Read → `SELECT`, Update → `UPDATE`,
  Delete → `DELETE`.
- **DDL vs DML vs DCL vs TCL**:
  - DDL: `CREATE`, `ALTER`, `DROP`, `TRUNCATE` — schema structure, usually
    auto-commits.
  - DML: `SELECT`, `INSERT`, `UPDATE`, `DELETE` — data manipulation.
  - DCL: `GRANT`, `REVOKE` — permissions.
  - TCL: `BEGIN`, `COMMIT`, `ROLLBACK`, `SAVEPOINT` — transaction control.

---

## 2. Data Types — the complete map

### 2.1 Exact numeric

| Type | Storage | Notes |
|---|---|---|
| `SMALLINT` | 2 bytes | -32,768 .. 32,767 |
| `INTEGER` / `INT` | 4 bytes | ±2.1B |
| `BIGINT` | 8 bytes | ±9.2 quintillion; default choice for surrogate PKs at scale |
| `DECIMAL(p,s)` / `NUMERIC(p,s)` | variable | exact precision — **always** use for money, never `FLOAT` |
| `SMALLSERIAL`/`SERIAL`/`BIGSERIAL` (Postgres) | 2/4/8 bytes | auto-increment sugar for `INT` + sequence; prefer `GENERATED ALWAYS AS IDENTITY` in modern Postgres |
| `TINYINT` (MySQL/SQL Server) | 1 byte | 0-255 unsigned or -128..127 signed depending on engine |
| `BIT` (SQL Server) | 1 bit (packed) | boolean-ish, 0/1/NULL |

### 2.2 Approximate numeric

| Type | Storage | Notes |
|---|---|---|
| `REAL` / `FLOAT4` | 4 bytes | ~6 decimal digits precision |
| `DOUBLE PRECISION` / `FLOAT8` | 8 bytes | ~15 decimal digits |
| `FLOAT(p)` | varies | precision-parametrized synonym in some engines |

**Rule**: never use float/double for currency or anything compared with `=` —
binary floating point cannot represent most decimal fractions exactly
(`0.1 + 0.2 != 0.3`). Use `DECIMAL`/`NUMERIC`.

### 2.3 Character / string

| Type | Notes |
|---|---|
| `CHAR(n)` | fixed-length, space-padded — rarely correct choice, wastes space on variable data |
| `VARCHAR(n)` | variable-length, bounded — the default for most text columns |
| `TEXT` | unbounded (Postgres, MySQL); SQL Server uses `VARCHAR(MAX)`/`NVARCHAR(MAX)` (legacy `TEXT` is deprecated) |
| `NCHAR`/`NVARCHAR` | Unicode-aware fixed/variable (SQL Server, needed for non-Latin scripts under legacy collations) |
| `CITEXT` (Postgres extension) | case-insensitive text — avoids `LOWER(col) = LOWER(?)` pattern that defeats plain indexes |

**Tip**: in Postgres, `VARCHAR(n)`, `VARCHAR` and `TEXT` have *identical*
storage/performance — the length constraint is enforced as a check, not
a storage optimization. Use `TEXT` + a `CHECK (length(col) <= n)` if you want
the constraint documented separately from storage.

### 2.4 Date / time

| Type | Notes |
|---|---|
| `DATE` | calendar date, no time |
| `TIME [(p)] [WITH TIME ZONE]` | time of day; `WITH TIME ZONE` is rarely what you want (it's just an offset, not a real zone) |
| `TIMESTAMP [(p)]` | date + time, no zone — "naive"; ambiguous across DST/zone boundaries |
| `TIMESTAMPTZ` / `TIMESTAMP WITH TIME ZONE` | stored internally as UTC, rendered in session zone — **default choice for event timestamps** |
| `INTERVAL` | a duration (Postgres has a rich native type; MySQL/SQL Server emulate with functions) |

**Tip**: store all timestamps as `TIMESTAMPTZ` (UTC) and convert to local
time only at the presentation layer. Mixing naive and zone-aware timestamps
is one of the most common correctness bugs in production schemas.

### 2.5 Boolean

`BOOLEAN` (Postgres native) vs `BIT`/`TINYINT(1)` (MySQL, SQL Server emulate
booleans — MySQL's `BOOLEAN` is literally a `TINYINT(1)` alias).

### 2.6 Binary

| Type | Notes |
|---|---|
| `BYTEA` (Postgres) / `VARBINARY` (MySQL, SQL Server) | raw binary blobs |
| `BLOB` (MySQL) | large binary object |
| **Rule of thumb** | store large files (images, PDFs) in object storage (S3) and keep only a reference/URL in the DB — blobs bloat backups, buffer cache, and replication |

### 2.7 Semi-structured / JSON

| Type | Notes |
|---|---|
| `JSON` | stores as text, validated, re-parses on every read |
| `JSONB` (Postgres) | binary, indexable (`GIN`), supports containment `@>`, path ops `#>` — prefer over `JSON` almost always |
| `JSON` (MySQL 5.7+) | binary-ish internally, has its own function set (`JSON_EXTRACT`, `->`, `->>`) |

```sql
-- Postgres JSONB example
SELECT data->>'email' AS email
FROM users
WHERE data @> '{"status": "active"}'::jsonb;

CREATE INDEX idx_users_data_gin ON users USING GIN (data);
```
**Rule of thumb**: JSON columns are an escape hatch for sparse/variable
attributes, not a replacement for schema design — if you're querying the same
JSON key in every WHERE clause, promote it to a real column.

### 2.8 Arrays (Postgres native; emulated elsewhere)

```sql
CREATE TABLE posts (id BIGINT PRIMARY KEY, tags TEXT[]);
INSERT INTO posts VALUES (1, ARRAY['flink','sql','tutorial']);
SELECT * FROM posts WHERE tags @> ARRAY['sql'];      -- contains
SELECT * FROM posts WHERE 'sql' = ANY(tags);          -- membership
CREATE INDEX idx_posts_tags ON posts USING GIN (tags);
```
MySQL/SQL Server have no native array type — model as a join table
(normalized) or a JSON array column.

### 2.9 Enumerated / domain types

```sql
-- Postgres native enum
CREATE TYPE order_status AS ENUM ('pending','paid','shipped','cancelled');
-- MySQL
status ENUM('pending','paid','shipped','cancelled')
-- Portable alternative (preferred for evolvability): a lookup table + FK,
-- since adding an ENUM value in Postgres requires ALTER TYPE and in some
-- versions can't run inside a transaction with other DDL.
```

### 2.10 UUID / identifiers

```sql
-- Postgres
id UUID PRIMARY KEY DEFAULT gen_random_uuid()   -- pgcrypto/pgcrypto or built-in in PG13+
-- MySQL 8.0+
id BINARY(16) PRIMARY KEY DEFAULT (UUID_TO_BIN(UUID()))
```
**Trade-off**: UUIDs are globally unique without coordination (good for
distributed writes/sharding, merging datasets) but random UUIDv4 fragments
B-tree indexes (random insert order → page splits, poor locality, worse
cache hit rate) versus a sequential `BIGINT`. Mitigation: UUIDv7 (time-
ordered UUIDs, increasingly supported natively) gets both global uniqueness
and insert locality.

### 2.11 Geometric / spatial

`POINT`, `POLYGON`, `GEOMETRY`, `GEOGRAPHY` (PostGIS on Postgres; SQL Server
has native `GEOMETRY`/`GEOGRAPHY`; MySQL has spatial extensions). Indexed via
R-tree-based `GiST`/`SPATIAL` indexes for range/containment queries.

### 2.12 Other notables

- `XML` — native type in SQL Server/Postgres; mostly legacy at this point.
- `MONEY` (Postgres/SQL Server) — generally avoid; locale-dependent formatting
  and rounding surprises make `NUMERIC(19,4)` the safer default.
- `INET`/`CIDR`/`MACADDR` (Postgres) — typed, indexable network address
  storage instead of storing IPs as text.
- `RANGE` types (Postgres: `INT4RANGE`, `TSRANGE`, `DATERANGE` …) — model
  intervals natively with overlap operators (`&&`) instead of pairs of
  columns + manual overlap logic.

---

## 3. DDL — defining structure

```sql
CREATE TABLE customers (
    customer_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    full_name     TEXT NOT NULL,
    signup_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    country_code  CHAR(2) NOT NULL,
    CONSTRAINT chk_country CHECK (country_code ~ '^[A-Z]{2}$')
);

CREATE TABLE orders (
    order_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id   BIGINT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    total_amount  NUMERIC(12,2) NOT NULL CHECK (total_amount >= 0),
    status        TEXT NOT NULL DEFAULT 'pending',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE orders ADD COLUMN shipped_at TIMESTAMPTZ;
ALTER TABLE orders ALTER COLUMN status SET DEFAULT 'pending';
ALTER TABLE orders DROP CONSTRAINT chk_country;  -- example only; wrong table, illustrative
CREATE INDEX idx_orders_customer_id ON orders (customer_id);
```

**FK `ON DELETE` / `ON UPDATE` actions**: `CASCADE` (propagate delete/update),
`RESTRICT`/`NO ACTION` (block if children exist), `SET NULL`, `SET DEFAULT`.
Default child-deletion behavior differs by intent — `CASCADE` is convenient
but dangerous on tables where accidental deletes must not silently fan out;
prefer `RESTRICT` + explicit application-level cascade for anything
high-stakes (financial, audit-adjacent data).

**`TRUNCATE` vs `DELETE`**: `TRUNCATE` deallocates pages instantly (no
per-row logging), resets identity sequences, but cannot be selectively
filtered and (in most engines) can't fire per-row triggers; `DELETE` is
transactional, filterable, slower at scale, fully logged/rollback-able.

---

## 4. Basic DML — SELECT, INSERT, UPDATE, DELETE

```sql
-- Basic SELECT
SELECT customer_id, full_name FROM customers WHERE country_code = 'US';

-- Filtering with multiple predicates, NULL handling
SELECT * FROM orders
WHERE status IN ('pending','paid')
  AND shipped_at IS NULL
  AND total_amount BETWEEN 10 AND 1000;

-- INSERT single / multi-row
INSERT INTO customers (email, full_name, country_code) VALUES
  ('a@x.com', 'Alice', 'US'),
  ('b@x.com', 'Bob',   'CA');

-- UPSERT (Postgres)
INSERT INTO customers (customer_id, email, full_name, country_code)
VALUES (1, 'a@x.com', 'Alice A.', 'US')
ON CONFLICT (customer_id)
DO UPDATE SET full_name = EXCLUDED.full_name;

-- UPSERT (MySQL)
INSERT INTO customers (customer_id, email, full_name, country_code)
VALUES (1, 'a@x.com', 'Alice A.', 'US')
ON DUPLICATE KEY UPDATE full_name = VALUES(full_name);

-- UPSERT (SQL Server) - MERGE
MERGE INTO customers AS tgt
USING (SELECT 1 AS customer_id, 'a@x.com' AS email) AS src
ON tgt.customer_id = src.customer_id
WHEN MATCHED THEN UPDATE SET email = src.email
WHEN NOT MATCHED THEN INSERT (customer_id, email) VALUES (src.customer_id, src.email);

-- UPDATE with join-derived value (Postgres)
UPDATE orders o
SET status = 'flagged'
FROM customers c
WHERE o.customer_id = c.customer_id AND c.country_code = 'RU';

-- DELETE with subquery
DELETE FROM orders WHERE customer_id IN (SELECT customer_id FROM customers WHERE email LIKE '%@spam.com');
```

**`NULL` semantics** (constantly misunderstood): `NULL = NULL` evaluates to
`NULL` (not `TRUE`) — always use `IS NULL`/`IS NOT NULL`. Any arithmetic or
comparison with `NULL` propagates `NULL`. `NULL` in `NOT IN (...)` is a classic
trap: if the subquery/list contains even one `NULL`, the entire `NOT IN`
returns no rows (because `x <> NULL` is `NULL`, not `TRUE`) — use `NOT EXISTS`
instead.

---

## 5. Aggregation, grouping, sorting

```sql
SELECT country_code, COUNT(*) AS n, AVG(total_amount) AS avg_amount
FROM orders o JOIN customers c USING (customer_id)
GROUP BY country_code
HAVING COUNT(*) > 100          -- filters groups, WHERE filters rows before grouping
ORDER BY avg_amount DESC
LIMIT 10 OFFSET 20;             -- pagination (see §13 for keyset alternative)
```

**Execution order** (not source-code order — the #1 conceptual gap for
beginners):
```
FROM/JOIN → WHERE → GROUP BY → HAVING → SELECT → DISTINCT → ORDER BY → LIMIT/OFFSET
```
This is why you can't reference a `SELECT`-aliased column in `WHERE` (alias
doesn't exist yet) but you can in `ORDER BY` (runs after `SELECT`).

`GROUPING SETS`, `ROLLUP`, `CUBE` — multi-level aggregation in one pass:
```sql
SELECT country_code, status, COUNT(*)
FROM orders o JOIN customers c USING (customer_id)
GROUP BY ROLLUP (country_code, status);
-- produces: (country,status) subtotals, (country) subtotals, and grand total
```

---

## 6. Joins — every flavor

```sql
-- INNER JOIN: only matching rows both sides
SELECT o.order_id, c.full_name
FROM orders o
INNER JOIN customers c ON o.customer_id = c.customer_id;

-- LEFT JOIN: all left rows, NULLs for unmatched right
SELECT c.full_name, o.order_id
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.customer_id;

-- RIGHT JOIN: symmetric opposite (rarely used — usually just flip to LEFT)
-- FULL OUTER JOIN: union of left and right unmatched + matched
SELECT c.customer_id, o.order_id
FROM customers c
FULL OUTER JOIN orders o ON o.customer_id = c.customer_id;

-- CROSS JOIN: cartesian product — every left row x every right row
SELECT s.size, col.color FROM sizes s CROSS JOIN colors col;

-- SELF JOIN: table joined to itself — classic for hierarchies/comparisons
SELECT e.name AS employee, m.name AS manager
FROM employees e
LEFT JOIN employees m ON e.manager_id = m.employee_id;

-- SEMI JOIN (via EXISTS): rows in A that have a match in B, A's columns only, no duplication even if B has multiple matches
SELECT c.* FROM customers c
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.customer_id);

-- ANTI JOIN (via NOT EXISTS): rows in A with NO match in B — the correct NULL-safe pattern
SELECT c.* FROM customers c
WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.customer_id);

-- NATURAL JOIN: auto-joins on same-named columns — avoid in production code,
-- implicit and breaks silently if a new same-named column is added later
```

**Join algorithm the planner picks** (you don't choose directly, but you
should recognize them in `EXPLAIN` output, §12):
| Algorithm | When |
|---|---|
| Nested loop | small outer input, or inner side has a good index on the join key |
| Hash join | no useful index, both sides largish, equality join — build hash table on smaller side, probe with larger |
| Merge join | both inputs already sorted (or cheap to sort) on the join key — streams both sides in order |

---

## 7. Subqueries & CTEs

```sql
-- Scalar subquery
SELECT full_name, (SELECT COUNT(*) FROM orders o WHERE o.customer_id = c.customer_id) AS order_count
FROM customers c;

-- Correlated subquery (re-evaluated per outer row — can be slow; often rewritable as a join)
SELECT * FROM customers c
WHERE total_spent > (SELECT AVG(total_amount) FROM orders o WHERE o.customer_id = c.customer_id);

-- CTE (readability, not a performance hint in most engines — Postgres 12+ inlines
-- non-recursive CTEs like a subquery unless you force materialization)
WITH big_spenders AS (
    SELECT customer_id, SUM(total_amount) AS spend
    FROM orders GROUP BY customer_id
    HAVING SUM(total_amount) > 1000
)
SELECT c.full_name, b.spend
FROM big_spenders b JOIN customers c USING (customer_id)
ORDER BY b.spend DESC;

-- Force materialization (Postgres) when you WANT the CTE computed once and reused,
-- e.g. it's referenced multiple times and is expensive
WITH expensive AS MATERIALIZED (
    SELECT customer_id, SUM(total_amount) AS spend FROM orders GROUP BY customer_id
)
SELECT * FROM expensive WHERE spend > 100
UNION ALL
SELECT * FROM expensive WHERE spend < -100;

-- Recursive CTE: hierarchy / graph traversal
WITH RECURSIVE org_chart AS (
    SELECT employee_id, manager_id, name, 1 AS depth
    FROM employees WHERE manager_id IS NULL         -- anchor: the root(s)
    UNION ALL
    SELECT e.employee_id, e.manager_id, e.name, oc.depth + 1
    FROM employees e
    JOIN org_chart oc ON e.manager_id = oc.employee_id  -- recursive step
)
SELECT * FROM org_chart ORDER BY depth, employee_id;
```

**`WHERE` vs `HAVING` vs subquery placement**: filter as early as possible —
pushing a predicate into a subquery/CTE's `WHERE` (row-level, pre-aggregation)
is almost always cheaper than filtering after a `GROUP BY` in `HAVING`.

---

## 8. Window functions

The single highest-leverage advanced SQL skill — replaces most self-joins
and correlated subqueries used for "compare this row to other rows" logic.

```sql
SELECT
    order_id, customer_id, total_amount,
    ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY created_at) AS rn,
    RANK()       OVER (PARTITION BY customer_id ORDER BY total_amount DESC) AS rnk,
    DENSE_RANK() OVER (PARTITION BY customer_id ORDER BY total_amount DESC) AS dense_rnk,
    LAG(total_amount)  OVER (PARTITION BY customer_id ORDER BY created_at) AS prev_amount,
    LEAD(total_amount) OVER (PARTITION BY customer_id ORDER BY created_at) AS next_amount,
    SUM(total_amount)  OVER (PARTITION BY customer_id ORDER BY created_at
                              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total,
    AVG(total_amount)  OVER (PARTITION BY customer_id ORDER BY created_at
                              ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS moving_avg_3,
    NTILE(4) OVER (ORDER BY total_amount) AS quartile
FROM orders;
```

**`ROW_NUMBER` vs `RANK` vs `DENSE_RANK`** on ties (e.g., two rows tied for
2nd place): `ROW_NUMBER` gives 1,2,3,4 arbitrarily breaking ties;
`RANK` gives 1,2,2,4 (gap after tie); `DENSE_RANK` gives 1,2,2,3 (no gap).

**Frame clause** (`ROWS`/`RANGE BETWEEN ... AND ...`) defaults to
`RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` when `ORDER BY` is
present — meaning aggregate window functions without an explicit frame are
already "running total" semantics, a very common gotcha when you actually
wanted the full-partition total (use `ROWS BETWEEN UNBOUNDED PRECEDING AND
UNBOUNDED FOLLOWING` or omit `ORDER BY` in the `OVER` clause for a full-
partition aggregate).

**Dedup-keep-latest pattern** (extremely common in interviews and real
pipelines):
```sql
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY email ORDER BY created_at DESC) AS rn
    FROM customers
) t WHERE rn = 1;
```

---

## 9. Set operations

```sql
SELECT email FROM customers_2024
UNION                      -- dedups
SELECT email FROM customers_2025;

SELECT email FROM customers_2024
UNION ALL                  -- keeps duplicates, cheaper (no dedup pass)
SELECT email FROM customers_2025;

SELECT email FROM customers_2024
INTERSECT
SELECT email FROM customers_2025;   -- present in both

SELECT email FROM customers_2024
EXCEPT                     -- (MINUS in Oracle)
SELECT email FROM customers_2025;   -- in first, not in second
```
Rule: all branches must have the same number of columns with compatible
types. Prefer `UNION ALL` over `UNION` whenever you know there are no
duplicates or don't care — the dedup sort/hash in plain `UNION` is not free.

---

## 10. Advanced query patterns

**Pivot (rows → columns)**:
```sql
SELECT customer_id,
       SUM(CASE WHEN status = 'paid' THEN total_amount ELSE 0 END) AS paid_total,
       SUM(CASE WHEN status = 'cancelled' THEN total_amount ELSE 0 END) AS cancelled_total
FROM orders GROUP BY customer_id;
-- Postgres crosstab() (tablefunc extension) or SQL Server PIVOT for native syntax
```

**Gaps and islands** (find contiguous runs, e.g. consecutive active days):
```sql
WITH numbered AS (
    SELECT user_id, activity_date,
           activity_date - (ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY activity_date))::int AS grp
    FROM daily_activity
)
SELECT user_id, MIN(activity_date) AS streak_start, MAX(activity_date) AS streak_end, COUNT(*) AS streak_len
FROM numbered GROUP BY user_id, grp
ORDER BY user_id, streak_start;
-- trick: subtracting a strictly-incrementing row number from a strictly-incrementing
-- date collapses consecutive dates to the same constant "grp"
```

**Top-N per group**:
```sql
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY total_amount DESC) AS rn
    FROM orders
) t WHERE rn <= 3;    -- top 3 orders per customer
```

**Percent of total / running share**:
```sql
SELECT customer_id, total_amount,
       total_amount / SUM(total_amount) OVER () AS pct_of_total,
       SUM(total_amount) OVER (ORDER BY total_amount DESC) / SUM(total_amount) OVER () AS cume_pct
FROM orders;
```

**Conditional aggregation / `FILTER`** (Postgres) vs `CASE WHEN`:
```sql
SELECT customer_id,
       COUNT(*) FILTER (WHERE status = 'paid') AS paid_count,   -- cleaner than SUM(CASE WHEN ... THEN 1 ELSE 0 END)
       COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_count
FROM orders GROUP BY customer_id;
```

**Finding duplicates**:
```sql
SELECT email, COUNT(*) FROM customers GROUP BY email HAVING COUNT(*) > 1;
```

**Delete duplicates keeping lowest id**:
```sql
DELETE FROM customers a USING customers b
WHERE a.email = b.email AND a.customer_id > b.customer_id;
```

---

## 11. Transactions & concurrency

```sql
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE account_id = 1;
UPDATE accounts SET balance = balance + 100 WHERE account_id = 2;
COMMIT; -- or ROLLBACK on error
```

**Isolation levels** (ANSI SQL, weakest → strongest; each stops one more
anomaly class):
| Level | Dirty read | Non-repeatable read | Phantom read |
|---|---|---|---|
| Read Uncommitted | possible | possible | possible |
| Read Committed | prevented | possible | possible |
| Repeatable Read | prevented | prevented | possible* |
| Serializable | prevented | prevented | prevented |

\* Postgres's `REPEATABLE READ` is actually snapshot isolation and also
prevents phantoms in practice, stricter than the ANSI minimum for that name —
know this distinction, it's a favorite trick question.

```sql
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
```

**MVCC (Multi-Version Concurrency Control)** — Postgres/MySQL InnoDB/Oracle
default to this: readers never block writers and writers never block readers,
because each transaction sees a consistent snapshot of rows as of its start
(or statement start), and old row versions are kept until no longer visible
to any active transaction (cleaned up by vacuum/purge). Contrast with
lock-based concurrency (SQL Server default `READ COMMITTED` without RCSI) —
readers can block on writer locks unless Read Committed Snapshot Isolation is
enabled.

**Locking**:
- *Row-level locks*: `SELECT ... FOR UPDATE` (exclusive, blocks other writers/
  lockers on those rows), `SELECT ... FOR SHARE` (shared, blocks writers only).
- *Optimistic locking*: version column checked on update instead of holding a
  lock — `UPDATE t SET ..., version = version + 1 WHERE id = ? AND version = ?`;
  zero rows affected means someone else won the race, application retries.
  Preferred at scale over long-held pessimistic locks.
- *Deadlocks*: two transactions each hold a lock the other needs — DB detects
  the cycle and kills one (victim) automatically. Prevention: always acquire
  locks/update rows in a **consistent order** across transactions.

```sql
-- classic queue-worker pattern: grab and lock the next job without blocking other workers
SELECT * FROM jobs WHERE status = 'pending'
ORDER BY created_at
FOR UPDATE SKIP LOCKED
LIMIT 1;
```
`SKIP LOCKED` is the standard building block for a SQL-based job queue —
each worker skips rows currently locked by another worker instead of
blocking on them.

---

## 12. Indexing

**B-tree** (default, virtually every engine): sorted structure, O(log n)
lookup, supports equality *and* range (`<`, `>`, `BETWEEN`), sort avoidance
for `ORDER BY`, prefix matching for `LIKE 'abc%'`.

```sql
CREATE INDEX idx_orders_customer_created ON orders (customer_id, created_at);
```

**Column order in a composite index matters** — an index on `(a, b)` can
serve queries filtering on `a` alone or `a AND b`, but *not* `b` alone
(can't binary-search a column that isn't the leading key). Put the
highest-selectivity / most commonly equality-filtered column first, unless a
specific query's `ORDER BY`/range pattern dictates otherwise.

**Other index types**:
| Type | Use case |
|---|---|
| Hash | equality-only, no range/sort support — rarely worth it over B-tree |
| `GIN` (Postgres) | full-text search, JSONB containment, array membership — "generalized inverted index" |
| `GiST` (Postgres) | geometric/range types, nearest-neighbor, exclusion constraints |
| `BRIN` (Postgres) | huge, naturally-ordered tables (e.g., append-only time-series by timestamp) — tiny index, coarse ranges, cheap to maintain |
| Full-text index (MySQL `FULLTEXT`, SQL Server) | native text search without an external engine |
| Spatial (`R-tree`) | geographic/geometric queries |

**Covering index / index-only scan**: if every column the query needs is in
the index itself (key columns + `INCLUDE`d columns), the engine never
touches the heap/table at all.
```sql
CREATE INDEX idx_orders_covering ON orders (customer_id) INCLUDE (total_amount, status);
-- SELECT total_amount, status FROM orders WHERE customer_id = ? can be answered from the index alone
```

**Partial index** (Postgres): index only the rows that matter, smaller and
faster to maintain.
```sql
CREATE INDEX idx_orders_pending ON orders (created_at) WHERE status = 'pending';
```

**Functional/expression index**: index the *result* of an expression so a
query filtering on that expression can use it.
```sql
CREATE INDEX idx_customers_lower_email ON customers (LOWER(email));
-- now: WHERE LOWER(email) = 'a@x.com' can use the index; WHERE email = 'a@x.com' cannot use THIS index
```

**Sargability** — "Search ARGument ABLE": a predicate that can use an index.
Wrapping the *indexed column* in a function or performing arithmetic on it
breaks sargability:
```sql
-- NOT sargable — function on the column forces a full scan unless a matching expression index exists
WHERE EXTRACT(YEAR FROM created_at) = 2025
-- sargable rewrite — range predicate on the raw column
WHERE created_at >= '2025-01-01' AND created_at < '2026-01-01'

-- NOT sargable
WHERE total_amount * 1.1 > 100
-- sargable
WHERE total_amount > 100 / 1.1
```

**Leading wildcard kills B-tree prefix matching**:
```sql
WHERE email LIKE '%gmail.com'   -- can't use a B-tree index (no known prefix)
WHERE email LIKE 'alice%'       -- can (prefix scan)
-- for arbitrary substring search at scale: trigram index (Postgres pg_trgm) or a dedicated search engine
CREATE INDEX idx_email_trgm ON customers USING GIN (email gin_trgm_ops);
```

**Index maintenance cost**: every index speeds reads but slows writes (each
`INSERT`/`UPDATE`/`DELETE` must maintain every index on the table) and costs
storage. Don't index columns that are never filtered/joined/sorted on; audit
unused indexes periodically (`pg_stat_user_indexes` in Postgres).

---

## 13. Query planning & execution

```sql
EXPLAIN SELECT * FROM orders WHERE customer_id = 42;          -- plan only, no execution
EXPLAIN ANALYZE SELECT * FROM orders WHERE customer_id = 42;  -- actually runs it, reports real timing/rows
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) SELECT ...;            -- + cache hit/miss info (Postgres)
```

**How to read a plan** — read it **inside-out / bottom-up**: the innermost
(deepest-indented) nodes execute first and feed outer nodes.

```
Nested Loop  (cost=0.85..16.92 rows=3 width=64) (actual time=0.02..0.05 rows=3 loops=1)
  ->  Index Scan using idx_orders_customer_id on orders  (cost=0.42..8.44 rows=3 width=40) (actual time=0.01..0.02 rows=3 loops=1)
        Index Cond: (customer_id = 42)
  ->  Index Scan using customers_pkey on customers  (cost=0.29..2.80 rows=1 width=24) (actual time=0.01..0.01 rows=1 loops=3)
        Index Cond: (customer_id = 42)
```

**Key things to look for**:
- **`Seq Scan` on a large table** where you expected an index scan — check
  the index exists, the predicate is sargable, and statistics are fresh
  (`ANALYZE`). Note: for a *small* table or a query returning a large
  fraction of rows, `Seq Scan` can legitimately be cheaper — the planner
  isn't always wrong.
- **Estimated rows vs actual rows** — a large mismatch means stale/skewed
  statistics, and the planner may have picked a bad join algorithm as a
  result. Fix: `ANALYZE table;` or increase `default_statistics_target` on
  problem columns.
- **`cost=startup..total`** — arbitrary planner cost units (not ms), used to
  compare candidate plans; `actual time=` is real elapsed milliseconds
  (only present with `ANALYZE`).
- **`loops=N`** in a nested-loop inner side — the inner node executed N
  times; multiply its per-loop actual time by N for real contribution.
- Look for **Sort** nodes with `Sort Method: external merge Disk` — spilled
  to disk because `work_mem` was too small for the sort/hash to fit in RAM.

**Cost-based optimizer**: the planner enumerates candidate join orders/
algorithms/access paths and picks the one with lowest estimated total cost,
derived from table/column statistics (row counts, distinct value counts,
histograms, correlation) it collects via `ANALYZE`. Stale statistics after a
bulk load or big data shift are one of the most common causes of a suddenly
bad plan.

**`ANALYZE` / `VACUUM ANALYZE`** (Postgres): `ANALYZE` refreshes planner
statistics; `VACUUM` reclaims space from dead row versions (MVCC leaves old
versions behind) and updates the visibility map. Autovacuum does this in the
background but can fall behind under heavy write load — a bloated table with
stale stats is a classic "why did this query suddenly get slow" root cause.

**Forcing a plan** — generally a last resort (fights the optimizer as data
changes); prefer fixing statistics/indexes. Postgres has no native query
hints by design; MySQL/SQL Server support explicit hints
(`USE INDEX`, `OPTION (FORCE ORDER)`, …) when you've proven the optimizer is
wrong and won't self-correct.

---

## 14. Performance tuning & query rewriting

**`SELECT *` avoidance**: pulls unnecessary columns (more I/O, defeats
covering indexes and index-only scans, breaks if schema changes) — always
enumerate needed columns in production code.

**`OFFSET` pagination doesn't scale** — `OFFSET 100000` still has to scan and
discard 100,000 rows.
```sql
-- slow at high offsets
SELECT * FROM orders ORDER BY order_id LIMIT 20 OFFSET 100000;

-- keyset/seek pagination — O(log n) via index regardless of page depth
SELECT * FROM orders WHERE order_id > 100000 ORDER BY order_id LIMIT 20;
```

**Batch writes** instead of row-by-row round trips:
```sql
INSERT INTO logs (msg) VALUES ('a'), ('b'), ('c');  -- one round trip, one WAL flush batch
-- vs 3 separate INSERT statements — 3x network + commit overhead
```

**Avoid N+1 query patterns** (ORM classic): fetching a parent list then
looping to fetch each child individually. Fix with a single join or a
`WHERE parent_id = ANY(?)` batched query.

**`EXISTS` vs `IN` vs `JOIN`** for existence checks: `EXISTS` typically wins
because it can short-circuit on the first match; `IN` with a large subquery
list can be materialized inefficiently by some planners (though modern
Postgres/MySQL optimizers often rewrite `IN` to a semi-join automatically —
verify with `EXPLAIN` rather than assuming).

**`COUNT(*)` vs `COUNT(col)`**: `COUNT(*)` counts rows (fast path in most
engines); `COUNT(col)` counts non-null values of that column (extra null
check per row). Use `COUNT(*)` unless you specifically need the null-
excluding semantics.

**Avoid implicit type coercion** — comparing a `TEXT` column to an integer
literal or a differently-typed column can silently disable index usage
(engine casts the indexed column instead of the literal). Keep join/filter
column types matched.

**Bulk load strategy**: drop/disable non-essential indexes before a huge
`COPY`/bulk `INSERT`, then rebuild indexes after — building an index once
over sorted bulk data is far cheaper than incrementally maintaining it row
by row during the load. Also consider deferring FK/constraint checks
(`SET CONSTRAINTS ... DEFERRED`) until the batch commits.

**Connection pooling**: opening a new physical DB connection is expensive
(auth handshake, backend process/thread spin-up — especially costly on
Postgres, which forks a process per connection). Always front the DB with a
pooler (PgBouncer, application-level pool) rather than opening a connection
per request.

**`work_mem` / sort & hash memory (Postgres)**: sorts, hash joins, and hash
aggregates use this per-operation memory budget before spilling to disk;
too low → disk spills show up as slow `Sort`/`Hash` nodes in `EXPLAIN`; too
high × many concurrent connections × multiple operators per query → OOM.
Tune per-session for known-heavy analytical queries rather than raising the
global default recklessly.

---

## 15. Normalization & denormalization

| Form | Rule |
|---|---|
| 1NF | atomic columns, no repeating groups |
| 2NF | 1NF + every non-key column depends on the *whole* PK (matters for composite keys) |
| 3NF | 2NF + no transitive dependency (non-key column depends only on the key, not on another non-key column) |
| BCNF | every determinant is a candidate key (stricter 3NF, handles some edge cases 3NF misses) |

**Why normalize**: eliminates update/insert/delete anomalies — a fact stored
once can't go inconsistent across rows.

**Why (and how) to denormalize deliberately**: read-heavy systems where join
cost dominates — duplicate a customer's name onto the `orders` row to avoid
a join on every read, accepting the cost of keeping it in sync (trigger,
application write-through, or accept eventual staleness). This is a
conscious trade-off, not a mistake, when read latency matters more than
write complexity/storage. Common vehicle: materialized views (§16) instead
of hand-maintained denormalized columns — get denormalized read speed
without hand-written sync logic.

---

## 16. Views, materialized views, stored procedures, triggers

```sql
-- View: stored query, always live, no storage of its own
CREATE VIEW active_customers AS
SELECT * FROM customers WHERE status = 'active';

-- Materialized view: stored result, must be explicitly refreshed — trades
-- staleness for read speed, ideal for expensive aggregations/dashboards
CREATE MATERIALIZED VIEW customer_ltv AS
SELECT customer_id, SUM(total_amount) AS ltv FROM orders GROUP BY customer_id;
REFRESH MATERIALIZED VIEW CONCURRENTLY customer_ltv;  -- CONCURRENTLY avoids locking readers out during refresh (needs a unique index)

-- Stored procedure / function (Postgres)
CREATE FUNCTION apply_discount(p_order_id BIGINT, p_pct NUMERIC)
RETURNS VOID AS $$
BEGIN
    UPDATE orders SET total_amount = total_amount * (1 - p_pct / 100)
    WHERE order_id = p_order_id;
END;
$$ LANGUAGE plpgsql;

-- Trigger: side effect on DML, e.g. maintaining an audit trail
CREATE FUNCTION audit_order_change() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO orders_audit (order_id, old_status, new_status, changed_at)
    VALUES (OLD.order_id, OLD.status, NEW.status, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_order_status_change
AFTER UPDATE OF status ON orders
FOR EACH ROW
WHEN (OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION audit_order_change();
```

**Trigger caution**: powerful but hides logic from anyone reading application
code — invisible side effects are a common source of "why did this row
change" incidents. Prefer explicit application-layer logic or a documented,
narrowly-scoped trigger (audit trails, `updated_at` maintenance) over
business logic embedded in triggers.

---

## 17. Partitioning

Splits one logical table into physical sub-tables sharing a partition key,
transparent to most queries.

```sql
-- Postgres declarative range partitioning (typical for time-series)
CREATE TABLE events (
    event_id BIGINT, occurred_at TIMESTAMPTZ NOT NULL, payload JSONB
) PARTITION BY RANGE (occurred_at);

CREATE TABLE events_2026_01 PARTITION OF events
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE events_2026_02 PARTITION OF events
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
```

**Partition types**: `RANGE` (dates, sequential IDs), `LIST` (discrete
categories — region, tenant), `HASH` (even distribution with no natural
range/list key).

**Why**: (1) **partition pruning** — a query filtered on the partition key
touches only relevant partitions, not the whole table; (2) fast bulk purge —
`DROP`/`DETACH` a whole old partition instead of a slow row-by-row `DELETE`;
(3) each partition's indexes are smaller, keeping hot indexes cache-resident;
(4) maintenance (vacuum, reindex) can run per-partition.

**Gotcha**: a query that doesn't filter on (or can't be proven to be
restricted by) the partition key scans every partition — partitioning is not
a free performance win, it targets a specific access pattern.

---

## 18. Scalability — replication, sharding, caching

**Vertical vs horizontal scaling**: vertical = bigger box (simple, hits a
ceiling, single point of failure); horizontal = more boxes (read replicas,
sharding) — more complex, effectively unbounded.

**Read replicas**: async (usually) streaming replication — writes go to the
primary, reads can be routed to replicas to scale read throughput. Trade-off:
**replication lag** — a replica read can return slightly stale data; "read
your own write" problems are the most common bug class this introduces (fix:
route read-after-write to the primary, or a session-consistency-aware router).

**Sharding** (horizontal partitioning across separate database instances,
not just tables): pick a shard key (often tenant ID or a hash of the PK),
route each query to the owning shard.
- *Pros*: near-linear write scalability, no single-box ceiling.
- *Cons*: cross-shard joins/transactions become application-level problems;
  resharding (adding shards) is a major migration; choose the shard key
  carefully upfront — the wrong key creates hot shards, same problem as a
  hot `keyBy` in a stream processor.

**Connection pooling & statement caching** — see §14; matters more, not
less, as instance count grows (each app instance opening its own pool
against every DB node multiplies connection count fast; use a shared
external pooler like PgBouncer in transaction-pooling mode for high
concurrency).

**Caching layers** (Redis/Memcached in front of the DB): cache-aside
(app checks cache, falls back to DB, writes back to cache), write-through,
or write-behind. Biggest risk: cache invalidation on writes — stale cache is
a correctness bug, not just a performance one; keep TTLs short for anything
where staleness matters, or invalidate explicitly on write.

**CQRS-ish read models**: for very read-heavy reporting workloads, a
separate read-optimized store (denormalized tables, a search index, an
OLAP warehouse fed by CDC) offloads reporting queries from the OLTP primary
entirely rather than trying to tune one schema for both access patterns.

**Change Data Capture (CDC)**: stream row-level changes (via logical
replication/WAL, e.g. Postgres logical decoding, Debezium) to downstream
systems (search index, cache invalidation, analytics warehouse, or a Flink
job — ties back to `Flink Streaming.md`) without dual-writing from the
application and risking write inconsistency between the DB and the
downstream system.

---

## 19. Fine-tuning checklist (operational)

- **Connection limits**: `max_connections` tuned to actual concurrency need,
  not maxed out blindly — each Postgres connection is a process with real
  memory overhead; use pooling instead of raising this indefinitely.
- **Shared buffers / buffer pool**: the DB's own page cache
  (`shared_buffers` in Postgres, `innodb_buffer_pool_size` in MySQL) sized to
  fit the hot working set in RAM — the single highest-leverage memory knob.
- **WAL / checkpoint tuning**: checkpoint frequency trades write-amplification
  (frequent checkpoints = more random I/O flushing dirty pages) against
  crash-recovery time (infrequent checkpoints = longer WAL replay on
  restart).
- **Autovacuum tuning (Postgres)**: on high-churn tables, default thresholds
  can fall behind — tune `autovacuum_vacuum_scale_factor` down (more
  frequent vacuum) per-table for hot tables rather than globally.
- **Statistics target**: raise `default_statistics_target` (or per-column)
  on columns with skewed/high-cardinality distributions the planner
  routinely misjudges.
- **Slow query log**: enable and review (`log_min_duration_statement` in
  Postgres, `slow_query_log` in MySQL) — the actual source of truth for
  "what's slow in production," not guesswork.
- **`pg_stat_statements`** (Postgres extension): aggregated per-query-shape
  timing/call-count stats — the standard first stop for "what's expensive."
- **Vertical read/write split at the app layer**: route analytical/reporting
  queries to a replica so they can't starve OLTP transactions of buffer
  cache/I/O on the primary.

---

## 20. Security

```sql
-- Principle of least privilege: role-scoped grants, not superuser app accounts
CREATE ROLE app_readonly LOGIN PASSWORD '...';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_readonly;

CREATE ROLE app_writer LOGIN PASSWORD '...';
GRANT SELECT, INSERT, UPDATE, DELETE ON orders, customers TO app_writer;

-- Row-level security (Postgres) — enforce tenant isolation in the DB itself,
-- not just in application query filters (defense in depth for multi-tenant systems)
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON orders
    USING (tenant_id = current_setting('app.current_tenant')::bigint);
```

**SQL injection**: always use parameterized queries/prepared statements —
*never* string-concatenate user input into SQL.
```sql
-- vulnerable (never do this)
"SELECT * FROM users WHERE email = '" + userInput + "'"
-- safe: parameterized
SELECT * FROM users WHERE email = $1;   -- driver binds the value, never interpolated as SQL text
```

**Least privilege for app accounts**: application connections should not be
superuser/owner roles — separate DDL-capable migration roles from runtime
DML-only roles.

---

## 21. Backup & recovery

- **Logical backup** (`pg_dump`/`mysqldump`): portable SQL/data dump,
  slower to restore at scale, easy to restore a single table/schema.
- **Physical backup** (base backup + WAL archiving in Postgres,
  `xtrabackup` in MySQL): file-level copy of the data directory, much faster
  restore for large databases, enables **point-in-time recovery (PITR)** by
  replaying WAL/binlog up to a specific timestamp — the standard way to
  recover from an accidental `DELETE`/`DROP` in production.
- **RPO/RTO**: Recovery Point Objective (how much data loss is acceptable —
  driven by backup/replication frequency) vs Recovery Time Objective (how
  long restore is allowed to take) — these two numbers should drive backup
  strategy choice, not the other way around.
- **Test restores regularly** — an untested backup is a hypothesis, not a
  guarantee.

---

## 22. Common anti-patterns

- **EAV (Entity-Attribute-Value) modeling** for core domain data — extreme
  flexibility, but destroys type safety, indexing, and query simplicity;
  usually a sign a `JSONB` column or proper schema evolution was needed
  instead.
- **Storing comma-separated values in a column** instead of a join table —
  breaks referential integrity, indexing, and any set-based query.
  ```sql
  -- anti-pattern
  tags VARCHAR(255) -- 'sql,flink,tutorial'
  -- fix: a tags join table, or a native array/JSONB column with proper indexing
  ```
- **No foreign keys "for performance"** — FKs are usually cheap (indexed
  lookups) relative to the data-integrity bugs they prevent; drop them only
  with a measured reason, not by default.
- **Using `AUTO_INCREMENT`/serial PK as the only uniqueness guarantee** on a
  business-unique column (e.g., email) — always add the `UNIQUE` constraint
  explicitly; an app-level check has a race condition, a DB constraint
  doesn't.
- **God tables** — one table with 80 nullable columns covering every variant
  of an entity; usually decomposable into a core table + type-specific
  extension tables (or JSONB for truly sparse/variable attributes).
- **Implicit cross join** from a missing `JOIN` condition (comma-join typo)
  — silently explodes row counts; always use explicit `JOIN ... ON`.
- **Over-indexing** — an index "just in case" on every column punishes every
  write for a read pattern that may never occur.

---

## 23. Interview Q&A — rapid fire

**Q: Why would `EXPLAIN` show a sequential scan even though there's an index
on the filtered column?**
A: The planner estimates the index scan would touch a large fraction of the
table (past the selectivity threshold where random I/O per row costs more
than one sequential sweep), stats are stale making that estimate wrong, the
predicate isn't sargable, or the column's data type doesn't match cleanly
(implicit cast).

**Q: What's the difference between a clustered and non-clustered index?**
A: Clustered index physically orders table rows by the index key (the table
*is* the index — one per table, e.g. SQL Server/MySQL InnoDB PK); a
non-clustered index is a separate structure with pointers back to the row
(heap location or clustering key). Postgres has no clustered index concept
by default — the heap is unordered and *all* indexes are non-clustered
(though `CLUSTER` can physically reorder a table once, non-maintained after).

**Q: Why is `NOT IN` dangerous with a subquery that can contain `NULL`?**
A: `NOT IN (SELECT ...)` translates to a chain of `<>` comparisons ANDed
together; if any value in the list is `NULL`, every comparison against it is
`NULL` (not `FALSE`), so `AND`-ing collapses the whole predicate to
`NULL`/never-true, silently returning zero rows. Always prefer
`NOT EXISTS` or explicitly filter `WHERE col IS NOT NULL` in the subquery.

**Q: How do you find and fix a slow query in production with no reproduction
environment?**
A: Pull the plan with `EXPLAIN ANALYZE` against production (or a same-scale
replica to avoid impacting live traffic), compare estimated vs actual rows
to catch stats/planner mismatches, check for missing/unused indexes, check
`pg_stat_statements`/slow query log for the query's historical
call-count/latency trend to see if it's a regression or always been slow at
this data volume.

**Q: How would you migrate a hot table's schema (add a `NOT NULL` column)
without locking writes for the duration?**
A: Add the column nullable (metadata-only change, near-instant in Postgres
11+), backfill in small batches to avoid long transactions/lock contention,
then add the `NOT NULL` constraint as `NOT VALID` + `VALIDATE CONSTRAINT`
(Postgres) so the constraint is enforced for new writes immediately but the
full-table validation scan doesn't hold a blocking lock the whole time.

**Q: When would you choose `NUMERIC` over `FLOAT`, and when is `FLOAT`
actually fine?**
A: `NUMERIC`/`DECIMAL` for anything compared with equality or requiring
exact decimal arithmetic — money, quantities, rates. `FLOAT`/`DOUBLE` is fine
for genuinely continuous scientific/measurement data (sensor readings,
coordinates) where small representation error is acceptable and the
performance/storage benefit matters.

**Q: What causes replication lag, and how do you monitor for it?**
A: Primary write throughput exceeding the replica's single-threaded (or
limited-parallelism) WAL/binlog replay rate, long-running queries on the
replica blocking replay (Postgres `hot_standby_feedback`/query conflicts),
or network latency between primary and replica. Monitor via
`pg_stat_replication` (`replay_lag`) or `SHOW REPLICA STATUS`
(`Seconds_Behind_Source`) in MySQL; alert on lag exceeding your RPO.

**Q: Composite index `(a, b)` — does it help `WHERE b = ?` alone?**
A: No — a B-tree composite index is only seekable via a prefix of its key
columns. It helps `WHERE a = ?`, `WHERE a = ? AND b = ?`, and `WHERE a = ?
ORDER BY b`, but a query filtering on `b` alone requires a full index scan
(better than nothing, but not a seek) or a separate index on `b`.

**Q: Explain the difference between `UNION` and `UNION ALL` performance.**
A: `UNION` must deduplicate the combined result (typically a sort or hash
pass over everything), `UNION ALL` just concatenates — always prefer
`UNION ALL` when you know duplicates can't occur or don't matter.
