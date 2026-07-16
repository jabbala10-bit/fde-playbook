# Advanced Database Tips, Tricks, and Performance Playbook

Expert-level database work is not about memorizing isolated tricks. It is the
discipline of turning a vague complaint like "the database is slow" into a
measured diagnosis, a targeted fix, and a clear explanation of trade-offs.

This guide focuses on practical techniques for relational databases, NoSQL
stores, caches, query analysis, performance improvement, and senior-level
articulation.

---

## 1. Senior Mental Model

Every database performance problem is usually one of these:

1. **Too much data read**
   The query scans more rows/pages/documents than necessary.

2. **Too much data sorted, grouped, joined, or shuffled**
   The engine has the right data but must perform expensive memory/CPU work.

3. **Too much waiting**
   Lock waits, I/O waits, network waits, replication lag, queueing, or connection
   pool exhaustion dominate runtime.

4. **Wrong physical design**
   Indexes, partitions, shard keys, clustering keys, or data layout do not match
   the real access pattern.

5. **Wrong workload isolation**
   OLTP and analytical workloads are fighting for the same CPU, buffer cache,
   disk, locks, or replicas.

6. **Wrong consistency expectation**
   The system is designed for eventual consistency, but the application expects
   read-your-write or transactional behavior.

The expert move is to identify which bucket you are in before changing code.

---

## 2. The Performance Triage Loop

Use this loop before reaching for indexes blindly:

```text
1. Identify the symptom
   Slow query, timeout, CPU spike, lock wait, replica lag, cache miss storm,
   high p95 latency, high write latency, or degraded throughput.

2. Measure the real workload
   Frequency, average latency, p95/p99 latency, rows read, rows returned,
   calls per minute, total time contribution.

3. Inspect the execution path
   EXPLAIN / EXPLAIN ANALYZE, slow query logs, pg_stat_statements,
   Query Store, Performance Schema, profiler, tracing.

4. Find the bottleneck
   Scan, join, sort, aggregation, lock, I/O, network, memory spill, bad estimate,
   missing index, stale stats, hot partition, or application N+1 pattern.

5. Apply the smallest safe fix
   Rewrite predicate, add/adjust index, refresh stats, batch query, change access
   pattern, partition, cache, or move workload.

6. Verify
   Compare before/after plans and production-like latency. Watch write overhead,
   lock impact, storage growth, and regressions.
```

**Rule**: tune the highest total cost, not the single slowest query. A query
that takes 10 seconds once per day may matter less than a 200 ms query called
50,000 times per hour.

---

## 3. Query Analysis: How to Read a Plan

### 3.1 What to inspect first

When reading `EXPLAIN ANALYZE`, do not read top-to-bottom like prose. Scan for:

- **Actual time**: where time is spent.
- **Actual rows vs estimated rows**: where the optimizer guessed wrong.
- **Loops**: a cheap node repeated thousands of times may be the real cost.
- **Rows removed by filter**: often means a scan is doing too much work.
- **Sort/hash spill**: disk usage means memory was insufficient for the operation.
- **Join algorithm**: nested loop, hash join, merge join.
- **Index condition vs filter condition**: index condition narrows the search;
  filter condition is applied after rows are fetched.

PostgreSQL example:

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT c.customer_id, c.email, SUM(o.total_amount) AS spend
FROM customers c
JOIN orders o ON o.customer_id = c.customer_id
WHERE o.created_at >= now() - interval '30 days'
GROUP BY c.customer_id, c.email
ORDER BY spend DESC
LIMIT 20;
```

Look for:

- `Seq Scan` on a huge table when only a small time range is needed.
- `HashAggregate` or `Sort` spilling to disk.
- `Nested Loop` where the inner side runs hundreds of thousands of times.
- Estimate mismatch such as `rows=100` but `actual rows=5,000,000`.
- High shared/local/temp buffer reads.

### 3.2 Estimated rows vs actual rows

The optimizer chooses a plan based on estimates. If estimates are wrong, the
plan can be wrong even when indexes exist.

Common causes:

- Stale statistics.
- Skewed data distribution.
- Correlated columns the optimizer treats as independent.
- Predicates on expressions/functions.
- Parameters whose values vary wildly.
- Low statistics target or insufficient histogram detail.

Fixes:

```sql
-- PostgreSQL
ANALYZE orders;

-- Increase stats target for skewed columns
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 1000;
ANALYZE orders;

-- Extended statistics for correlated columns
CREATE STATISTICS stats_orders_tenant_status
ON tenant_id, status
FROM orders;
ANALYZE orders;
```

Articulation:

> The problem is not that the optimizer is bad. The optimizer made a rational
> choice from bad cardinality estimates. I would refresh or improve statistics
> before forcing a plan.

---

## 4. Sargability: Make Predicates Index-Friendly

A predicate is **sargable** when the engine can use an index to search directly
instead of computing a function for every row.

Bad:

```sql
WHERE LOWER(email) = 'alice@example.com'
WHERE DATE(created_at) = DATE '2026-07-16'
WHERE amount + tax > 100
WHERE CAST(customer_id AS TEXT) = '123'
WHERE email LIKE '%@example.com'
```

Better:

```sql
-- Use normalized or generated column, or expression index
WHERE email_normalized = 'alice@example.com'

-- Range predicate instead of function on column
WHERE created_at >= TIMESTAMPTZ '2026-07-16 00:00:00+00'
  AND created_at <  TIMESTAMPTZ '2026-07-17 00:00:00+00'

-- Move computation to constant side when possible
WHERE amount > 100 - tax

-- Match types
WHERE customer_id = 123

-- Use full-text, trigram, reverse index, or search engine for suffix search
```

Expression index option:

```sql
CREATE INDEX idx_users_lower_email ON users ((lower(email)));

SELECT *
FROM users
WHERE lower(email) = lower($1);
```

Expert nuance: expression indexes are useful, but they couple performance to
that exact expression. A normalized persisted column can be clearer when the
predicate is core business logic.

---

## 5. Indexing Strategy

### 5.1 Indexes are not free

Indexes speed reads but tax writes:

- Extra storage.
- More WAL/redo logging.
- Slower inserts, updates, deletes.
- More vacuum/maintenance.
- Potential planner confusion if many overlapping indexes exist.

Index only for real access patterns:

```text
high-frequency query + selective predicate + stable workload = good index candidate
rare query + low selectivity + high write table = suspicious index candidate
```

### 5.2 Composite index order

For a B-tree index:

```sql
CREATE INDEX idx_orders_tenant_status_created
ON orders (tenant_id, status, created_at DESC);
```

This helps:

```sql
WHERE tenant_id = ?

WHERE tenant_id = ?
  AND status = ?

WHERE tenant_id = ?
  AND status = ?
ORDER BY created_at DESC
LIMIT 50
```

It does not efficiently seek:

```sql
WHERE status = ?
```

because `status` is not the leftmost prefix.

General ordering rule:

```text
Equality columns first, then range columns, then ORDER BY columns.
```

Example:

```sql
WHERE tenant_id = ?
  AND status = ?
  AND created_at >= ?
ORDER BY created_at DESC
LIMIT 100
```

Good index:

```sql
CREATE INDEX idx_orders_tenant_status_created
ON orders (tenant_id, status, created_at DESC);
```

### 5.3 Covering indexes

A covering index contains all columns needed by a query, allowing an index-only
scan in engines that support it.

```sql
-- PostgreSQL
CREATE INDEX idx_orders_lookup
ON orders (tenant_id, status, created_at DESC)
INCLUDE (order_id, total_amount);
```

Query:

```sql
SELECT order_id, total_amount, created_at
FROM orders
WHERE tenant_id = 42
  AND status = 'paid'
ORDER BY created_at DESC
LIMIT 20;
```

Trade-off: covering indexes can be excellent for hot read paths, but they
increase index size and write cost.

### 5.4 Partial / filtered indexes

Use when a query repeatedly targets a small subset of a table.

```sql
CREATE INDEX idx_orders_open_by_tenant
ON orders (tenant_id, created_at DESC)
WHERE status IN ('pending', 'processing');
```

This is better than indexing every historical order if the application mostly
queries open orders.

### 5.5 Unique indexes as correctness tools

Do not rely on application checks for uniqueness:

```sql
CREATE UNIQUE INDEX uq_users_email_normalized
ON users (email_normalized);
```

Application-level check:

```text
SELECT no row exists -> INSERT
```

has a race condition under concurrency. A unique constraint does not.

### 5.6 Index anti-patterns

- Indexing every foreign key is usually good, but indexing every column is not.
- Multiple nearly identical composite indexes create write overhead.
- Low-cardinality indexes like `is_active` alone are often weak unless partial.
- Indexing columns that change constantly can punish writes.
- Indexes on huge text/blob fields are expensive; use specialized indexes.
- Adding an index without measuring the before/after plan is guessing.

---

## 6. Query Rewriting Patterns

### 6.1 Replace `OFFSET` with keyset pagination

Bad at deep pages:

```sql
SELECT *
FROM orders
ORDER BY created_at DESC
LIMIT 50 OFFSET 500000;
```

Better:

```sql
SELECT *
FROM orders
WHERE created_at < $last_seen_created_at
ORDER BY created_at DESC
LIMIT 50;
```

For stable ordering, include a tie-breaker:

```sql
SELECT *
FROM orders
WHERE (created_at, order_id) < ($last_seen_created_at, $last_seen_order_id)
ORDER BY created_at DESC, order_id DESC
LIMIT 50;
```

Index:

```sql
CREATE INDEX idx_orders_created_id_desc
ON orders (created_at DESC, order_id DESC);
```

### 6.2 Use `EXISTS` for existence checks

Often better:

```sql
SELECT c.*
FROM customers c
WHERE EXISTS (
    SELECT 1
    FROM orders o
    WHERE o.customer_id = c.customer_id
);
```

Instead of:

```sql
SELECT DISTINCT c.*
FROM customers c
JOIN orders o ON o.customer_id = c.customer_id;
```

Why: `EXISTS` can stop after the first match and avoids accidental
duplication.

### 6.3 Use `NOT EXISTS` instead of `NOT IN`

Safer with `NULL`:

```sql
SELECT c.*
FROM customers c
WHERE NOT EXISTS (
    SELECT 1
    FROM orders o
    WHERE o.customer_id = c.customer_id
);
```

`NOT IN` can return zero rows if the subquery contains `NULL`.

### 6.4 Pre-aggregate before joining

Bad when `orders` is huge and join multiplies rows:

```sql
SELECT c.customer_id, c.email, SUM(o.total_amount)
FROM customers c
JOIN orders o ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.email;
```

Better when only aggregate order data is needed:

```sql
WITH order_totals AS (
    SELECT customer_id, SUM(total_amount) AS total_spend
    FROM orders
    GROUP BY customer_id
)
SELECT c.customer_id, c.email, ot.total_spend
FROM customers c
JOIN order_totals ot ON ot.customer_id = c.customer_id;
```

This reduces the join input size.

### 6.5 Avoid `SELECT *`

`SELECT *` increases:

- Network transfer.
- Deserialization.
- Buffer/cache pressure.
- Risk of breaking consumers when schema changes.
- Chance that the optimizer cannot use a covering index.

Prefer explicit projection:

```sql
SELECT order_id, status, total_amount
FROM orders
WHERE customer_id = $1;
```

### 6.6 Prefer `UNION ALL` when deduplication is unnecessary

```sql
SELECT email FROM active_customers
UNION ALL
SELECT email FROM invited_customers;
```

`UNION` requires sorting or hashing to remove duplicates.

### 6.7 Be careful with CTEs

CTEs improve readability, but materialization behavior differs by engine and
version.

Use CTEs for:

- Clarity.
- Reusing a complex result.
- Recursive queries.
- Intentional materialization.

Avoid using them as a performance trick without checking the plan.

---

## 7. Joins: Expert Diagnostics

### 7.1 Nested loop

Good when:

- Outer input is small.
- Inner side has an efficient index lookup.

Bad when:

- Outer input is large.
- Inner lookup is repeated many times.

Symptom:

```text
Nested Loop
  -> Seq Scan large_table actual rows=900000
  -> Index Scan other_table loops=900000
```

Even a 0.1 ms inner lookup becomes expensive at 900,000 loops.

### 7.2 Hash join

Good when:

- Equality join.
- Inputs are large.
- No useful ordered index exists.

Bad when:

- Hash table spills to disk.
- Build side is much larger than estimated.

Fixes:

- Improve estimates.
- Add memory for the query/session.
- Reduce input rows earlier.
- Add a better index if nested loop would be cheaper.

### 7.3 Merge join

Good when:

- Inputs are already sorted by join key.
- Range or ordered processing matters.

Bad when:

- Sorting both sides is more expensive than hashing.

### 7.4 Join articulation

Say:

> I am checking whether the join algorithm matches the shape of the data. A
> nested loop is not inherently bad; it is bad when the outer input is large
> and the inner lookup repeats too many times. A hash join is not inherently
> good; it becomes bad when the hash spills or the build side is misestimated.

---

## 8. Locking, Isolation, and Concurrency

Many "slow database" incidents are not query-plan problems. They are waiting
problems.

### 8.1 Common lock symptoms

- Queries are fast alone but slow under load.
- CPU is low, but requests time out.
- Writes block reads or reads block writes depending on engine/isolation.
- Long-running transactions hold locks.
- Migrations block application traffic.

### 8.2 Long transaction rule

Keep transactions short:

```text
BEGIN
  read small amount
  write necessary rows
  commit
END
```

Avoid:

```text
BEGIN
  call external API
  wait for user input
  process huge batch
  update rows
COMMIT
```

Long transactions cause:

- Lock contention.
- MVCC bloat.
- Delayed vacuum.
- Replication lag.
- Deadlocks.

### 8.3 Lost update prevention

Optimistic concurrency:

```sql
UPDATE accounts
SET balance = balance - 100,
    version = version + 1
WHERE account_id = 1
  AND version = 7;
```

If zero rows are updated, someone else modified the row first.

Pessimistic locking:

```sql
SELECT *
FROM accounts
WHERE account_id = 1
FOR UPDATE;
```

Use pessimistic locking when conflicts are common and correctness is critical.
Use optimistic locking when conflicts are rare and throughput matters.

### 8.4 Deadlock prevention

- Update tables in a consistent order.
- Update rows in a consistent order.
- Keep transactions short.
- Use proper indexes so updates lock fewer rows.
- Retry deadlocked transactions safely.

Articulation:

> Deadlocks are not always bugs in the database. They are often a signal that
> two valid transactions acquire locks in inconsistent order. The fix is usually
> deterministic lock ordering plus retry logic.

---

## 9. Write Performance

### 9.1 Batch writes

Bad:

```text
insert one row
commit
insert one row
commit
...
```

Better:

```sql
INSERT INTO events (tenant_id, event_type, payload)
VALUES
    (1, 'click', '{}'),
    (1, 'view', '{}'),
    (1, 'purchase', '{}');
```

Or use bulk loaders:

- PostgreSQL: `COPY`
- MySQL: `LOAD DATA`
- SQL Server: bulk insert / bcp

### 9.2 Reduce index overhead on bulk loads

For massive one-time loads:

1. Load into staging table.
2. Validate.
3. Build indexes after load.
4. Swap/merge into target.

Building one index over bulk data is usually cheaper than maintaining many
indexes row-by-row during ingestion.

### 9.3 Avoid hot rows

Bad counter design:

```sql
UPDATE article_stats
SET views = views + 1
WHERE article_id = 42;
```

At huge scale, one row becomes a write bottleneck.

Better:

- Sharded counters.
- Append events and aggregate asynchronously.
- Use a cache counter with periodic flush.

Example:

```sql
UPDATE article_view_counter_shards
SET views = views + 1
WHERE article_id = 42
  AND shard_id = $chosen_shard_id;
```

Read:

```sql
SELECT SUM(views) AS total_views
FROM article_view_counter_shards
WHERE article_id = 42;
```

Conceptually: trade exact immediate reads for write scalability.

---

## 10. Partitioning and Sharding

### 10.1 Partitioning

Partitioning is table-level physical organization inside one database.

Good for:

- Time-series data.
- Large delete/purge by date.
- Partition pruning.
- Smaller per-partition indexes.
- Isolating hot recent data from cold historical data.

Bad when:

- Queries do not filter on partition key.
- Too many partitions increase planning overhead.
- Partition key does not match lifecycle or access pattern.

Example:

```sql
CREATE TABLE events (
    tenant_id BIGINT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL
) PARTITION BY RANGE (occurred_at);
```

Expert phrase:

> Partitioning is not a generic speed button. It is excellent when it lets the
> optimizer avoid touching irrelevant partitions or lets operations drop whole
> data ranges cheaply.

### 10.2 Sharding

Sharding splits data across database instances.

Use when:

- One primary cannot handle write volume.
- Data size exceeds a practical single-node ceiling.
- Tenants can be isolated naturally.

Hard parts:

- Cross-shard joins.
- Cross-shard transactions.
- Rebalancing.
- Hot shards.
- Global uniqueness.
- Operational complexity.

Shard-key checklist:

```text
High cardinality?
Even traffic distribution?
Most queries include this key?
Can tenants/users be moved later?
Does it avoid cross-shard transactions?
What happens to celebrity tenants/hot keys?
```

---

## 11. OLTP vs OLAP Separation

OLTP systems optimize for:

- Short transactions.
- Indexed point lookups.
- High concurrency.
- Low p95 latency.
- Data correctness.

OLAP systems optimize for:

- Large scans.
- Aggregations.
- Columnar compression.
- Batch/interactive analytics.
- Fewer but heavier queries.

Anti-pattern:

```text
Run huge reporting queries on the primary OLTP database during business hours.
```

Better:

- Read replica for reporting.
- Materialized views.
- CDC into warehouse/lakehouse.
- Search index for text-heavy access.
- Precomputed aggregates.
- Separate operational read models.

Articulation:

> I would not tune the primary forever to serve two conflicting workloads.
> At some point the right move is workload isolation: keep OLTP fast and push
> analytical reads to a replica, materialized view, or warehouse.

---

## 12. Caching and NoSQL Performance Patterns

### 12.1 Cache-aside

```text
read:
  value = cache.get(key)
  if miss:
      value = db.query(...)
      cache.set(key, value, ttl)
  return value

write:
  db.update(...)
  cache.delete(key)
```

Common risks:

- Stale data.
- Thundering herd.
- Cache penetration from nonexistent keys.
- Cache avalanche when many keys expire together.
- Hot keys.

### 12.2 Thundering herd fixes

- TTL jitter.
- Request coalescing.
- Short recompute lock.
- Serve stale while revalidating.
- Pre-warm hot keys.

Redis lock shape:

```bash
SET recompute:product:42 <token> NX EX 10
```

Only the lock holder recomputes. Others serve stale or wait briefly.

### 12.3 DynamoDB / wide-column access pattern discipline

Design from queries backward:

```text
Question: what exact query must be fast?
Need: get all orders for a user by date.
Key: PK = USER#<id>, SK = ORDER#<timestamp>
```

Avoid:

- Scans in hot paths.
- Low-cardinality partition keys.
- GSIs added without capacity/cost planning.
- Treating eventual GSI reads as strongly consistent.

### 12.4 Redis performance discipline

Avoid blocking commands on large keyspaces:

```bash
# bad in production
KEYS *
SMEMBERS huge:set
LRANGE huge:list 0 -1
```

Prefer:

```bash
SCAN 0 MATCH "user:*" COUNT 100
SSCAN huge:set 0 COUNT 100
LRANGE huge:list 0 99
```

---

## 13. Observability for Databases

Track these layers separately:

### Query workload

- Query fingerprint.
- Calls per minute.
- Mean, p95, p99 latency.
- Rows returned.
- Rows examined/read.
- Temporary disk usage.
- Plan changes.

### System resources

- CPU.
- Memory / buffer cache hit ratio.
- Disk IOPS and latency.
- Network throughput.
- Connection count.
- Queue depth.

### Concurrency

- Lock waits.
- Deadlocks.
- Long-running transactions.
- Blocked sessions.
- Transaction age.

### Replication

- Replica lag.
- WAL/binlog generation rate.
- Replay/apply lag.
- Replication slot growth.
- Replica conflicts.

### Maintenance

- Table/index bloat.
- Vacuum/autovacuum health.
- Statistics freshness.
- Checkpoint frequency.
- Backup success and restore tests.

### Cache / NoSQL

- Hit ratio.
- Evictions.
- Hot keys/partitions.
- Throttles.
- Consumed capacity.
- Slow commands.
- Memory fragmentation.

Senior principle:

> If a metric cannot lead to an action, it is dashboard decoration.

---

## 14. Common Production Incidents and How to Reason

### 14.1 Query suddenly slow

Likely causes:

- Plan changed.
- Stats stale.
- Data volume crossed threshold.
- Index no longer selective.
- Parameter value skew.
- Cache cold.
- Table/index bloat.
- Lock contention.

Response:

1. Compare old/new query plans if available.
2. Check actual vs estimated rows.
3. Check recent deployments/migrations.
4. Check stats freshness.
5. Check lock waits and I/O.
6. Test targeted fix.

### 14.2 CPU high

Likely causes:

- Expensive scans.
- Hash joins/aggregations.
- Sorts.
- Too many concurrent queries.
- Missing indexes.
- Bad application loop.
- Connection pool too large.

Fix direction:

- Reduce rows read.
- Add/adjust index.
- Limit concurrency.
- Precompute.
- Cache.
- Move analytics elsewhere.

### 14.3 I/O high

Likely causes:

- Working set larger than memory.
- Sequential scans.
- Index bloat.
- Poor locality.
- Checkpoint pressure.
- Vacuum falling behind.

Fix direction:

- Improve selectivity.
- Reduce result size.
- Partition hot/cold data.
- Increase memory or improve cache locality.
- Reindex/vacuum where appropriate.

### 14.4 Lock waits high

Likely causes:

- Long transactions.
- Missing indexes on update/delete predicates.
- Migration locks.
- Foreign key checks without supporting indexes.
- Hot rows.

Fix direction:

- Shorten transactions.
- Add supporting indexes.
- Batch updates.
- Use online migrations.
- Shard counters/hot rows.

---

## 15. Schema Design Best Practices

### 15.1 Design for invariants

Use the database to enforce facts that must never be false:

```sql
ALTER TABLE orders
ADD CONSTRAINT chk_total_amount_nonnegative
CHECK (total_amount >= 0);

ALTER TABLE users
ADD CONSTRAINT uq_users_email UNIQUE (email_normalized);
```

Application validation is for user experience. Database constraints are for
truth.

### 15.2 Normalize first, denormalize deliberately

Normalize to avoid anomalies. Denormalize only when:

- Read path is proven hot.
- Join cost is material.
- Staleness rules are clear.
- Sync mechanism is owned.
- Tests/monitoring catch divergence.

### 15.3 Model time explicitly

For temporal systems:

- `created_at`
- `updated_at`
- `deleted_at`
- `effective_from`
- `effective_to`
- `valid_at`
- `recorded_at`

Do not confuse:

- **Event time**: when business event happened.
- **Ingestion time**: when system received it.
- **Processing time**: when job processed it.

### 15.4 Soft delete carefully

Soft delete:

```sql
deleted_at TIMESTAMPTZ NULL
```

Needs:

- Partial indexes excluding deleted rows.
- Queries consistently filtering active rows.
- Retention/purge job.
- Unique constraints that handle deleted records intentionally.

Example:

```sql
CREATE UNIQUE INDEX uq_active_users_email
ON users (email_normalized)
WHERE deleted_at IS NULL;
```

---

## 16. Migration Best Practices

For hot production tables:

1. Add nullable column.
2. Deploy app that writes both old and new shape.
3. Backfill in small batches.
4. Validate counts/checksums.
5. Add constraint using online/non-blocking method if supported.
6. Switch reads to new shape.
7. Remove old column later.

Avoid:

```sql
ALTER TABLE huge_table ADD COLUMN new_col TEXT NOT NULL DEFAULT 'x';
```

unless you know the engine/version handles it as metadata-only.

Batch backfill pattern:

```sql
UPDATE users
SET email_normalized = lower(email)
WHERE email_normalized IS NULL
  AND user_id >= $start_id
  AND user_id <  $end_id;
```

Expert principle:

> Online migrations are product work, not just DDL. They require sequencing,
> observability, rollback, and application compatibility.

---

## 17. Security and Governance Tips

- Use parameterized queries only.
- Separate migration role from application runtime role.
- Apply least privilege.
- Use row-level security or tenant predicates for multi-tenant systems.
- Encrypt in transit.
- Encrypt backups.
- Audit privileged access.
- Avoid logging secrets or sensitive SQL parameters.
- Set retention for logs, traces, and query samples.
- Test restore procedures.

SQL injection framing:

> Escaping is a patch. Parameter binding is the design. The query text and the
> user value must travel separately to the database driver.

---

## 18. Articulation Techniques

### 18.1 The expert answer structure

When explaining a database problem, use:

```text
Observation -> Hypothesis -> Evidence -> Fix -> Trade-off -> Verification
```

Example:

> Observation: p95 latency increased from 80 ms to 2 seconds on the order
> lookup endpoint.
>
> Hypothesis: the query is scanning too many recent orders or the index no
> longer matches the predicate.
>
> Evidence: EXPLAIN ANALYZE shows a sequential scan on `orders`, 8 million rows
> removed by filter, and estimated rows are off by 100x.
>
> Fix: add a composite index on `(tenant_id, status, created_at DESC)` and
> refresh statistics.
>
> Trade-off: writes to `orders` become slightly more expensive and index storage
> increases, so I would verify write latency and disk growth.
>
> Verification: compare before/after p95, rows read, plan shape, and write
> overhead in staging or a production canary.

### 18.2 How to talk about indexes

Weak:

> Add an index to make it faster.

Strong:

> The query filters by tenant and status, then orders by creation time. I would
> use a composite B-tree index on `(tenant_id, status, created_at DESC)` because
> equality predicates come first and the range/order column comes last. I would
> verify the plan uses an index scan and that write overhead is acceptable.

### 18.3 How to talk about trade-offs

Use paired consequences:

- "This improves read latency but increases write amplification."
- "This reduces p95 latency but introduces cache staleness risk."
- "This avoids cross-shard joins but makes resharding a design concern."
- "This gives strong consistency but costs availability/latency under failure."
- "This makes analytics faster but introduces data freshness lag."

### 18.4 How to answer "Which database would you choose?"

Use access pattern first:

```text
1. What are the reads?
2. What are the writes?
3. What consistency is required?
4. What scale and latency are required?
5. What operational maturity exists?
6. What failure mode is acceptable?
```

Example:

> If the workload needs relational constraints, joins, and transactional updates,
> I would start with PostgreSQL. If it is high-scale key-based access with known
> access patterns and flexible schema, DynamoDB or Cassandra may fit better. If
> it is low-latency ephemeral lookup, Redis or Memcached may be the right layer,
> but not necessarily the system of record.

### 18.5 How to sound senior in performance reviews

Say:

- "Let's separate total database time from single-query latency."
- "What changed: data volume, plan, traffic, deployment, or configuration?"
- "Can we compare estimated rows to actual rows?"
- "Is the query CPU-bound, I/O-bound, lock-bound, or network-bound?"
- "Will this index pay for itself under write load?"
- "What is the consistency requirement for this read?"
- "Are we tuning one query or fixing the workload shape?"
- "What metric tells us the fix worked?"

Avoid:

- "Indexes always make queries faster."
- "NoSQL is faster than SQL."
- "Denormalization is bad."
- "Joins are slow."
- "Sequential scans are always bad."
- "Caching fixes database problems."

Expert nuance is the ability to say "it depends" and then immediately explain
what it depends on.

---

## 19. Expert Checklists

### Slow query checklist

- Is the query frequent enough to matter?
- Are predicates sargable?
- Are data types aligned?
- Is the right composite index available?
- Does the index match filter and sort order?
- Are estimates close to actual rows?
- Are statistics fresh?
- Is the query returning too many columns?
- Is sorting/grouping spilling to disk?
- Is a join multiplying rows accidentally?
- Is there an N+1 pattern in the application?
- Are locks or waits dominating runtime?

### Index review checklist

- Which query does this index support?
- Is the predicate selective?
- Does column order match equality/range/order usage?
- Can a partial index solve it more cheaply?
- Is this index redundant with another index?
- How much write overhead does it add?
- How large will it be?
- Can it be created online/concurrently?
- How will we verify it is used?

### Production readiness checklist

- Slow query logging enabled.
- Query fingerprint aggregation available.
- Backup and restore tested.
- Connection pool sized correctly.
- Read/write timeouts configured.
- Long transaction monitoring in place.
- Lock wait monitoring in place.
- Replica lag alerting in place.
- Migration playbook exists.
- Rollback plan exists.
- Cache invalidation strategy documented.
- Dashboard maps metrics to actions.

---

## 20. Rapid-Fire Expert Q&A

**Q: Why might a sequential scan be faster than an index scan?**

A: If the query returns a large fraction of the table, sequential I/O can be
cheaper than many random index lookups plus heap fetches. Index scans are best
when predicates are selective.

**Q: Why did adding an index not help?**

A: The predicate may be non-sargable, the index column order may not match the
query, the predicate may not be selective, the query may be bottlenecked on
sort/join/lock/network instead of filtering, or the optimizer may estimate that
the index is more expensive.

**Q: Why can a query be fast in staging but slow in production?**

A: Different data volume, distribution, cache warmth, statistics, parameter
values, concurrency, locks, hardware, or configuration. Plans are data-shaped.

**Q: What is the difference between latency and throughput tuning?**

A: Latency tuning reduces time per request. Throughput tuning increases total
work per second. Sometimes they conflict: batching improves throughput but can
increase individual request latency.

**Q: When is denormalization correct?**

A: When a measured read path is hot, staleness is acceptable or controlled, sync
logic is owned, and the read improvement is worth write/storage complexity.

**Q: How do you debug database p95 latency?**

A: Group by query fingerprint, identify top contributors, inspect plans for the
p95 path, check waits/locks/I/O, compare estimates to actual rows, and correlate
with deployments, data growth, and traffic changes.

**Q: What is the safest first response to a production slow query?**

A: Observe before changing. Capture the query fingerprint, plan, timings, rows,
waits, and recent changes. Then apply a targeted fix such as stats refresh,
index creation, query rewrite, or workload isolation.

---

## 21. One-Page Expert Summary

Database expertise is the ability to connect four layers:

```text
Logical request
  -> query shape
  -> physical access path
  -> operational behavior under load
```

The best engineers do not say "add an index" as a reflex. They ask:

- What access pattern must be fast?
- How many rows are read vs returned?
- Is the plan estimate accurate?
- Is time spent on CPU, I/O, locks, network, or queueing?
- Does the physical design match the workload?
- What trade-off does the fix introduce?
- How will we prove the fix worked?

That is the difference between writing SQL and engineering database systems.
