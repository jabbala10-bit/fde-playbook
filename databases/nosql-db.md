# Key-Value / NoSQL Databases — Complete Reference (Beginner → Expert)

Consolidated reference for key-value and adjacent NoSQL stores: core
concepts, data models, command/query patterns from trivial to advanced,
consistency theory, replication/partitioning, performance tuning, and
scalability strategy. Primary examples use **Redis** (richest data model,
most commonly interviewed) and **DynamoDB** (dominant managed KV/wide-column
hybrid); **Memcached**, **etcd**, and **Cassandra** called out where their
design diverges meaningfully. Companion to `relational_database.md`.

---

## 1. Core Concepts

- **Key-value store** = a dictionary/hashmap as a database: opaque key → an
  opaque or semi-structured value, accessed almost exclusively by key (no
  general-purpose join engine, no arbitrary predicate scan by default).
- **Why reach for KV over RDBMS**: sub-millisecond point lookups at massive
  scale, horizontal scalability with minimal coordination, flexible/sparse
  value schemas, and workloads that are naturally access-by-primary-key
  (sessions, caches, feature flags, leaderboards, counters, shopping carts).
- **What you give up**: multi-key ACID transactions (varies by engine),
  ad-hoc joins, secondary-attribute queries without extra indexing
  infrastructure, and often strong consistency by default.
- **NoSQL family map** (KV is one of four broad categories):
  | Category | Examples | Access pattern |
  |---|---|---|
  | Key-value | Redis, Memcached, DynamoDB (KV mode), etcd, RocksDB | get/put/delete by key |
  | Document | MongoDB, Couchbase, DynamoDB (document mode) | query by any field in a semi-structured doc |
  | Wide-column | Cassandra, HBase, Bigtable | rows keyed by partition+clustering key, sparse columns |
  | Graph | Neo4j, Neptune | nodes/edges, traversal queries |

  DynamoDB and Cassandra straddle KV and wide-column — covered here because
  their primary access pattern is still "look up by key(s)."

- **CAP theorem**: under a network partition, a distributed system must
  choose **Consistency** (every read sees the latest write) or
  **Availability** (every request gets a response) — you cannot have both.
  In practice this is a spectrum (PACELC extends it: even without a
  partition, you trade Latency vs Consistency). Most KV stores let you tune
  this per-operation rather than picking one mode globally.
- **Consistency models**, weakest → strongest:
  | Model | Guarantee |
  |---|---|
  | Eventual consistency | replicas converge *eventually*, no ordering guarantee on reads meanwhile |
  | Read-your-writes | a client always sees its own prior writes |
  | Session consistency | read-your-writes scoped to a session/connection |
  | Bounded staleness | replica lag capped by time or version count |
  | Strong consistency | every read reflects the most recent committed write |
- **BASE** (the NoSQL counterpoint to ACID): **B**asically **A**vailable,
  **S**oft state, **E**ventual consistency — the explicit trade-off many KV
  stores make to maximize availability/partition tolerance over strict
  consistency.

---

## 2. Data Models — what a "value" actually is

### 2.1 Redis — rich in-memory data structures

| Type | Shape | Typical use |
|---|---|---|
| String | bytes/text/int, up to 512MB | cache entry, counter, session blob, distributed lock token |
| Hash | field → value map within one key | object representation (user:123 → {name, email, age}) without full JSON serialize/deserialize |
| List | ordered, linked-list-backed | queue, recent-activity feed, `LPUSH`/`RPOP` job queue |
| Set | unordered unique members | tags, unique visitor tracking, set algebra (union/intersect/diff) |
| Sorted Set (ZSet) | unique members + float score, ordered by score | leaderboards, priority queues, time-windowed rankings |
| Hash + TTL fields (Redis 7.4+) | per-field expiry | fine-grained session/feature expiry without a full key TTL |
| Bitmap | string treated as a bit array | feature flags per user, daily-active-user tracking via `SETBIT`/`BITCOUNT` |
| HyperLogLog | probabilistic cardinality estimator | approximate unique counts (millions of items in ~12KB, ~0.81% error) |
| Geo | sorted set under the hood, geo-indexed | proximity search (`GEOSEARCH`) |
| Stream | append-only log with consumer groups | event sourcing, lightweight Kafka-alternative for smaller scale |

### 2.2 DynamoDB — item/attribute model

- **Item** = a row; **Attribute** = a column, but items in the same table
  can have wildly different attributes (schemaless beyond the key).
- **Primary key** is either:
  - *Simple*: a single **Partition Key (PK)** — pure KV lookup.
  - *Composite*: **Partition Key + Sort Key (SK)** — enables range queries
    and one-to-many modeling *within* a partition (e.g., `PK=USER#123`,
    `SK=ORDER#2026-01-01` lets you query "all orders for user 123" as a
    range scan on SK).
- **Attribute types**: `S` (string), `N` (number, arbitrary precision
  decimal string internally), `B` (binary), `BOOL`, `NULL`, `M` (map, nested
  document), `L` (list), `SS`/`NS`/`BS` (string/number/binary sets).
- **Secondary indexes**:
  - *LSI (Local Secondary Index)*: same PK, different SK, must be created at
    table-creation time, shares the base table's partition throughput.
  - *GSI (Global Secondary Index)*: independent PK/SK, its own throughput,
    can be added/removed anytime, **eventually consistent by default**
    (unlike the base table which supports strongly consistent reads).

### 2.3 Memcached

Pure string/blob values, no native data structures, no persistence, no
replication or clustering built in (client-side consistent hashing across a
pool of independent nodes) — deliberately the simplest possible cache, which
is exactly why it's still chosen when you want zero operational complexity
for a pure look-aside cache.

### 2.4 etcd

Key-value store specialized for **strongly consistent** small-value
metadata/config (Raft consensus underneath) — not for bulk data; used for
service discovery, distributed locks, leader election (backs Kubernetes'
entire cluster state).

### 2.5 Cassandra (wide-column, KV-adjacent)

`PRIMARY KEY (partition_key, clustering_columns...)` — partition key
determines which node(s) own the data (via consistent hashing), clustering
columns determine on-disk sort order *within* the partition. Conceptually
very close to DynamoDB's PK+SK model; predates it.

---

## 3. Basic operations

### Redis
```bash
SET user:123:name "Alice"
GET user:123:name
DEL user:123:name
EXISTS user:123:name
EXPIRE user:123:name 3600        # TTL in seconds
TTL user:123:name                # seconds remaining, -1 = no TTL, -2 = key doesn't exist
SET session:abc "token" EX 900 NX  # set with TTL, only if not exists — atomic "acquire" primitive
INCR page:views                  # atomic increment, creates key at 0 if missing
INCRBY inventory:sku42 -5
```

### DynamoDB (CLI / SDK-shaped)
```bash
aws dynamodb put-item --table-name Orders \
  --item '{"PK": {"S": "USER#123"}, "SK": {"S": "ORDER#2026-01-01"}, "total": {"N": "49.99"}}'

aws dynamodb get-item --table-name Orders \
  --key '{"PK": {"S": "USER#123"}, "SK": {"S": "ORDER#2026-01-01"}}'

aws dynamodb delete-item --table-name Orders \
  --key '{"PK": {"S": "USER#123"}, "SK": {"S": "ORDER#2026-01-01"}}'
```

---

## 4. Redis — data structure command deep dive

```bash
# Hash: partial-object updates without read-modify-write of a whole blob
HSET user:123 name "Alice" email "a@x.com" age 30
HGET user:123 email
HGETALL user:123
HINCRBY user:123 age 1
HDEL user:123 age

# List: queue / stack / capped recent-activity feed
LPUSH queue:jobs "job1"
RPUSH queue:jobs "job2"
LPOP queue:jobs                       # pop from head -> FIFO if paired with RPUSH
BRPOP queue:jobs 5                    # blocking pop, waits up to 5s — building block for a simple work queue
LTRIM feed:user:123 0 99              # cap a list at 100 most-recent entries, O(1)-ish amortized

# Set: tagging, unique tracking, set algebra
SADD post:42:tags "sql" "nosql" "tutorial"
SISMEMBER post:42:tags "sql"
SINTER post:42:tags post:43:tags      # shared tags between two posts
SCARD post:42:tags                    # cardinality

# Sorted Set: leaderboard
ZADD leaderboard 1500 "alice" 1800 "bob"
ZINCRBY leaderboard 50 "alice"
ZREVRANGE leaderboard 0 9 WITHSCORES  # top 10
ZRANK leaderboard "alice"             # 0-based rank ascending
ZRANGEBYSCORE leaderboard 1000 2000   # score-range query

# Transactions: MULTI/EXEC queues commands, executes atomically as a batch (no partial application)
MULTI
INCR counter
EXPIRE counter 60
EXEC

# Optimistic concurrency: WATCH aborts the transaction if a watched key changed since WATCH
WATCH account:1:balance
val = GET account:1:balance
MULTI
SET account:1:balance <val - 100>
EXEC   # returns nil if account:1:balance changed between WATCH and EXEC -> client must retry

# Lua scripting: server-side atomic multi-step logic — the general-purpose escape hatch
# beyond what MULTI/EXEC or single commands can express
EVAL "local v = redis.call('GET', KEYS[1]); if v == ARGV[1] then return redis.call('DEL', KEYS[1]) else return 0 end" 1 lock:resource token123

# Pub/Sub: fire-and-forget messaging, no persistence/replay (use Streams if you need durability)
SUBSCRIBE channel:orders
PUBLISH channel:orders "new order 42"

# Streams: durable, replayable, consumer-group semantics (Kafka-lite)
XADD orders:stream '*' order_id 42 status paid
XREADGROUP GROUP order-processors consumer-1 COUNT 10 STREAMS orders:stream '>'
XACK orders:stream order-processors <id>
```

**`KEYS *` vs `SCAN`**: `KEYS` is O(N) and **blocks the single-threaded
server** for the entire scan — never use in production. `SCAN` (and
`HSCAN`/`SSCAN`/`ZSCAN`) is cursor-based, O(1) per call, non-blocking,
production-safe.
```bash
SCAN 0 MATCH "user:*" COUNT 100
```

---

## 5. DynamoDB — access pattern & query design

**The core discipline**: unlike RDBMS (model the data, then write whatever
query you need), DynamoDB requires you to **design the table around your
known access patterns first** — there is no ad-hoc query engine. If a new
access pattern shows up later that the key/index design doesn't support,
you're adding a GSI or restructuring, not just writing new SQL.

```python
# Query: efficient, uses partition key (+ optional sort key condition) — the primary tool
response = table.query(
    KeyConditionExpression=Key('PK').eq('USER#123') & Key('SK').begins_with('ORDER#')
)

# Scan: reads the ENTIRE table then filters — expensive, avoid at scale except for
# small tables, exports, or one-off admin queries
response = table.scan(FilterExpression=Attr('status').eq('cancelled'))

# Conditional write: prevents lost updates without a separate lock (optimistic concurrency)
table.put_item(
    Item={'PK': 'USER#123', 'SK': 'PROFILE', 'version': 2, 'name': 'Alice'},
    ConditionExpression='version = :expected',
    ExpressionAttributeValues={':expected': 1}
)

# Atomic counter, no read-modify-write round trip
table.update_item(
    Key={'PK': 'USER#123', 'SK': 'PROFILE'},
    UpdateExpression='SET view_count = view_count + :inc',
    ExpressionAttributeValues={':inc': 1}
)

# Batch operations: up to 25 items (write) / 100 items (get) per call — reduces round trips
dynamodb.batch_write_item(RequestItems={'Orders': [...]})
```

**Single-table design**: the canonical DynamoDB pattern — store multiple
entity types (users, orders, order-items) in *one* physical table by
overloading PK/SK with generic names and prefixed values
(`PK=USER#123`/`SK=PROFILE`, `PK=USER#123`/`SK=ORDER#2026-01-01`), so
related entities that are queried together are colocated in the same
partition and fetched in a single `Query` call. This trades RDBMS-style
readability for the ability to serve every known access pattern with O(1)
partition lookups and zero joins — it is a direct consequence of DynamoDB
having no server-side join.

**GSI overloading**: reuse generic attribute names (`GSI1PK`, `GSI1SK`)
across different entity types so one GSI serves multiple access patterns —
the same trick as PK/SK overloading, applied to secondary indexes.

**Hot partition problem**: all read/write capacity for a partition key is
served by one physical partition — a single celebrity user, a popular
product, or a low-cardinality key (e.g., `status`) as the PK creates a hot
shard that throttles regardless of overall table throughput. Fix:
- Add a random or calculated **suffix** to spread writes:
  `PK = "PRODUCT#42#" + str(random.randint(0,9))`, then fan out reads across
  all 10 suffixes and merge — write-sharding pattern.
- Choose a naturally high-cardinality key, or a composite key that spreads
  load (e.g., `tenant_id#user_id` instead of just `tenant_id`).

**Capacity modes**: *Provisioned* (fixed RCU/WCU, cheaper at steady
predictable load, throttles above the limit) vs *On-Demand* (pay-per-request,
auto-scales instantly, better for spiky/unpredictable traffic, higher
per-request cost).

---

## 6. Consistency, replication & the Dynamo model

**Quorum reads/writes** (the model underlying Dynamo-family stores —
Cassandra, Riak, and DynamoDB's internals): with **N** replicas, a write
succeeds after **W** replicas ack, a read queries **R** replicas and
resolves conflicts. **W + R > N** guarantees strong (read-your-writes)
consistency because every read set and every write set must overlap by at
least one replica.

| Configuration | Property |
|---|---|
| W=N, R=1 | fast reads, slow/fragile writes (all replicas must be up) |
| W=1, R=N | fast writes, slow reads |
| W=majority, R=majority (e.g., N=3, W=2, R=2) | balanced, tolerates one node down, still strongly consistent |
| W=1, R=1 (W+R ≤ N) | eventual consistency only, fastest, weakest guarantee |

**Conflict resolution when replicas diverge**: **Last-Write-Wins (LWW)**
using timestamps (simple, can silently lose concurrent writes — clock skew
makes this worse); **vector clocks** (track causal history per replica,
detect true concurrent writes and surface them for app-level or
CRDT-based merge instead of silently dropping one); **CRDTs**
(Conflict-free Replicated Data Types — G-Counter, PN-Counter, OR-Set — data
structures with merge functions that are mathematically guaranteed to
converge regardless of order/duplication, used by Redis Enterprise's
"CRDB" active-active and Riak).

**Redis replication**: async by default (primary acks the write before
replicas confirm) — a crash right after ack can lose the last few writes not
yet shipped to a replica (`WAIT numreplicas timeout` forces waiting for
replica acks when you need stronger durability at write-latency cost).
**Redis Sentinel** handles primary failure detection + automatic failover
for a single primary/replica set. **Redis Cluster** shards data across
multiple primaries using 16,384 hash slots, each key mapped via
`CRC16(key) mod 16384` — supports horizontal write scaling, unlike a single
Sentinel-managed primary.

**Hash tags** (Redis Cluster): force related keys onto the same slot (thus
the same node) so multi-key operations work despite sharding:
```bash
SET "{user:123}:profile" "..."
SET "{user:123}:settings" "..."
# both hash on "user:123" (the {} portion only) -> same slot -> safe to MGET/transaction together
```

**Consistent hashing**: the general technique behind Redis Cluster slot
assignment, Cassandra/DynamoDB partitioning, and Memcached client-side
sharding — maps both nodes and keys onto a hash ring so adding/removing a
node only remaps `~1/N` of keys instead of rehashing everything (compare to
naive `hash(key) mod N`, where changing N reshuffles nearly all keys).

---

## 7. Persistence & durability

**Redis** (in-memory first, persistence is opt-in and tunable):
| Mechanism | Trade-off |
|---|---|
| RDB snapshot | periodic point-in-time binary dump — fast restart, compact, but loses writes since the last snapshot on crash |
| AOF (Append-Only File) | logs every write command — replayable, tunable fsync (`always`/`everysec`/`no`); `everysec` is the common durability/throughput balance |
| RDB + AOF together | fastest restart (load RDB) + minimal loss (replay AOF tail) — the production-recommended combination |
| No persistence | pure cache mode — acceptable when Redis is a look-aside cache backed by a durable source of truth |

**DynamoDB**: durable by default (replicated across 3 AZs synchronously
before a write is acknowledged) — no separate persistence decision to make;
**Point-in-Time Recovery (PITR)** enables restore to any second in the last
35 days, and on-demand backups for longer retention.

**Memcached**: no persistence at all, by design — a node restart or crash
loses everything in it; only appropriate when the DB/cache-miss path is
always correct and tolerable.

---

## 8. Performance patterns

**Caching strategies** (apply to any KV store fronting a system of record):
| Pattern | Mechanics | Risk |
|---|---|---|
| Cache-aside (lazy loading) | app checks cache, on miss reads DB and populates cache | thundering herd on a popular key's expiry |
| Read-through | cache library itself owns the DB fetch on miss | simpler app code, less control |
| Write-through | every write goes to cache and DB synchronously | write latency = slowest of the two |
| Write-behind (write-back) | write to cache immediately, async flush to DB | fastest writes, risk of data loss if cache node dies before flush |

**Thundering herd mitigation**: when a hot key expires, many concurrent
requests miss simultaneously and hammer the DB. Fixes: probabilistic early
expiration/refresh (jitter the TTL so not all requests expire at once),
a short-lived "recompute lock" (`SET key val NX EX 5` as a mutex so only one
request recomputes while others get a slightly stale value or wait), or
serve-stale-while-revalidate.

**Pipelining** (Redis): batch multiple commands into one round trip instead
of one request per command — the single biggest lever against network
round-trip latency dominating throughput for small values.
```bash
redis-cli --pipe < commands.txt
```

**Connection pooling**: same rationale as RDBMS (§14 of the relational doc)
— reuse connections, don't pay handshake cost per request; especially
important for Redis's single-threaded command loop where connection churn
adds up.

**Avoid large values / large collections in a single key**: a multi-MB
`String` or a `List`/`Set` with millions of members makes that one key's
operations slow (and, for Redis, blocks the single-threaded event loop
during the operation) — shard large collections across multiple keys
(e.g., bucket a huge sorted set by date range) instead.

**Batch/multi-get over N sequential gets**:
```bash
MGET user:1:name user:2:name user:3:name   # one round trip instead of three
```

**Key naming convention**: `entity:id:attribute` (colon-delimited) is the de
facto Redis convention — enables `SCAN MATCH "user:123:*"` patterns and
keeps keys self-describing; keep keys short (they're stored in full, not
just referenced, so verbose keys waste real memory at scale).

**TTL strategy**: set explicit expirations on anything cache-shaped so a
stale/orphaned key doesn't live forever and silently grow memory —
"every cache key should have a TTL unless you have a specific eviction
reason not to" is a reasonable default rule.

---

## 9. Eviction & memory management (Redis)

When `maxmemory` is reached, Redis evicts according to `maxmemory-policy`:
| Policy | Behavior |
|---|---|
| `noeviction` | reject writes with an error once full — correct for a primary datastore, wrong for a cache |
| `allkeys-lru` | evict least-recently-used across all keys — default sane choice for a pure cache |
| `allkeys-lfu` | evict least-*frequently*-used — better than LRU when access frequency, not recency, predicts future use |
| `volatile-lru`/`volatile-lfu`/`volatile-ttl` | only evict keys that have a TTL set, by LRU/LFU/soonest-to-expire — lets you mix permanent and cache-like keys in one instance safely |
| `volatile-random`/`allkeys-random` | random eviction — cheap, rarely the right default |

`allkeys-lru`/`lfu` use approximated (sampled) LRU/LFU, not exact, by
design — exact tracking would cost memory/CPU disproportionate to the
benefit at scale.

---

## 10. Advanced patterns

**Distributed lock (Redlock)**: acquire a lock across N independent Redis
masters, considered held only if a majority acknowledge within a timeout —
tolerates single-node failure without losing the lock guarantee (single-
instance `SET key token NX PX ttl` is simpler and fine for non-critical
locks, but a single point of failure).
```bash
SET lock:resource:42 <unique-token> NX PX 30000
# ... critical section ...
# release: only delete if the token still matches (never blind DEL — another
# holder may have acquired it after this client's lock expired)
EVAL "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) else return 0 end" 1 lock:resource:42 <unique-token>
```

**Rate limiting — sliding window via sorted set**:
```bash
ZADD rl:user:123 <now_ms> <now_ms>            # record this request, score = timestamp = member (unique enough for this use)
ZREMRANGEBYSCORE rl:user:123 0 <now_ms - window_ms>  # drop requests outside the window
ZCARD rl:user:123                              # count remaining -> compare to limit
EXPIRE rl:user:123 <window_seconds>
```
Simpler fixed-window alternative: `INCR` + `EXPIRE` on a window-bucketed key
(`rl:user:123:2026-07-12T10:15`) — cheaper, but allows burst at window
boundaries; the sorted-set version gives a true sliding window.

**Leaderboard with rank + surrounding context**:
```bash
ZADD leaderboard 2500 "alice"
ZREVRANK leaderboard "alice"                    # alice's rank
ZRANGE leaderboard <rank-2> <rank+2> WITHSCORES  # players immediately around her
```

**Session store**: `HSET session:<id> user_id 123 role admin` +
`EXPIRE session:<id> 1800`, refreshed on each request (`EXPIRE` reset) —
the textbook Redis use case, since sessions are pure KV, latency-sensitive,
and disposable.

**Idempotency key pattern** (dedup at-least-once-delivered requests/events):
```bash
SET idempotency:<request-id> "processed" NX EX 86400
# if SET returns nil (key existed), this request was already handled -> skip
```

**Job queue**: `LPUSH`/`BRPOP` for simple FIFO; for reliability (don't lose
a job if the worker crashes mid-processing), use
`BLMOVE src processing_queue` (Redis 6.2+) or `BRPOPLPUSH` (deprecated
alias) to atomically move the job into a "processing" list, and only remove
it from there after the worker confirms completion — otherwise a crashed
worker silently drops the job.

---

## 11. Fine-tuning & operational checklist

- **Right-size `maxmemory`** below the container/host limit, with headroom
  for fork-based RDB snapshotting (which briefly needs up to ~2x memory via
  copy-on-write pages during the fork).
- **Avoid `KEYS`, `FLUSHALL`, and unbounded `SMEMBERS`/`LRANGE 0 -1` on large
  collections in production paths** — all are O(N) blocking operations on a
  single-threaded server; use `SCAN` variants and bounded ranges instead.
- **Monitor `INFO` sections**: `used_memory`, `evicted_keys`
  (non-zero + growing = undersized cache or missing TTLs), `keyspace_hits`
  vs `keyspace_misses` (hit ratio — the core cache health metric),
  `connected_clients`, `blocked_clients`, `instantaneous_ops_per_sec`.
- **`SLOWLOG`**: Redis's built-in slow-command log — the first stop for "why
  did latency spike," analogous to a slow query log in an RDBMS.
- **Client-side caching (Redis 6+ tracking / RESP3)**: server notifies
  clients when a cached key changes, letting the client hold a local copy
  and skip the round trip entirely until invalidated — the next level past
  server-side caching for read-hot keys.
- **DynamoDB**: watch `ConsumedReadCapacityUnits`/`ConsumedWriteCapacityUnits`
  against provisioned limits, `ThrottledRequests`, and use **DAX**
  (DynamoDB Accelerator, a managed in-memory cache in front of the table)
  for microsecond read latency on hot items without managing Redis
  yourself.
- **Right-size item/value size**: DynamoDB charges in whole 1KB (write) /
  4KB (read) increments — a 4.1KB item costs as much read capacity as an
  8KB one; Redis values that are unnecessarily large (uncompressed JSON
  blobs) waste RAM, the most expensive resource in the system. Consider
  compression for large, infrequently-read values.
- **Scan cost awareness**: a DynamoDB `Scan` reads (and bills) every item in
  the table regardless of how few match the filter — filters apply *after*
  the read cost is incurred, not before.

---

## 12. Security

- **AUTH / ACLs (Redis 6+)**: per-user credentials with fine-grained command
  and key-pattern permissions (`ACL SETUSER app-readonly on >password
  ~cache:* +get +mget -@all`) — don't run Redis with no password and open
  network exposure; historically a common ransomware vector for
  misconfigured internet-facing instances.
- **TLS in transit**: enable for any traffic crossing an untrusted network
  (Redis supports TLS since 6.0; DynamoDB enforces HTTPS always).
- **IAM-scoped access (DynamoDB)**: fine-grained policies down to specific
  actions/items via `dynamodb:LeadingKeys` condition — lets you give a
  multi-tenant application credentials that can only touch that tenant's
  partition keys, enforced by AWS, not application code.
- **Encryption at rest**: DynamoDB always encrypts at rest by default;
  Redis relies on the underlying disk/volume encryption for RDB/AOF files
  since it has no native at-rest encryption for persisted files.
- **Never store secrets in plaintext values** even in a "just a cache" —
  breach blast radius includes the cache, not just the primary DB.

---

## 13. Common anti-patterns

- **Using Redis as a primary datastore with `noeviction` off and no
  persistence** — an eviction policy meant for a cache silently deletes
  "durable" data under memory pressure; mismatch between how the store is
  configured and how it's actually being used.
- **DynamoDB `Scan` in a hot request path** — should be reserved for
  offline/admin/export use; any user-facing query needs a `Query` against a
  key or GSI designed for that access pattern.
- **Unbounded Redis collections** (a `List`/`Set` that grows forever with no
  `LTRIM`/expiry) — turns an O(1)-ish structure into a slow, memory-hungry
  liability.
- **Treating eventual consistency as if it were strong** — reading
  immediately after writing from a different replica/region and assuming
  the new value is there; leads to intermittent, hard-to-reproduce bugs.
  Explicitly request strong consistency (`ConsistentRead=True` in
  DynamoDB) where correctness requires it, at a latency/availability cost.
- **Designing a DynamoDB schema RDBMS-style** (one item type per table,
  normalized, expecting to join at query time) — fights the engine; results
  in N sequential queries where a single-table design would do one.
- **Hot key from a low-cardinality partition key** (`status`, `country`, a
  single popular `tenant_id`) — throttles regardless of overall
  provisioned/cluster capacity; always sanity-check key cardinality and
  expected skew during design, not after a production incident.
- **Blind `DEL` on a distributed lock** without verifying token ownership —
  can delete a lock acquired by a different holder after the original
  lock expired, defeating the mutual exclusion guarantee entirely.

---

## 14. Interview Q&A — rapid fire

**Q: Why is Redis single-threaded for command execution, and how is it
still fast?**
A: All in-memory data access, no disk I/O in the hot path, and no lock
contention/context-switching overhead a multi-threaded design would need
for shared data structures — a single thread executing simple in-memory
operations at millions of ops/sec is faster in practice than a
lock-contended multi-threaded alternative for this workload shape.
(Redis 6+ added multi-threaded I/O for network read/write, but command
*execution* itself remains single-threaded.) The practical consequence: any
O(N) command (`KEYS`, unbounded `LRANGE`, huge `SORT`) blocks every other
client for its duration.

**Q: How would you model a one-to-many relationship (one user, many orders)
in DynamoDB?**
A: Composite primary key with `PK = USER#<id>`, `SK = ORDER#<timestamp>` for
the orders, and `SK = PROFILE` for the user's own item — a single `Query`
on `PK = USER#<id>` returns the user profile and all orders together
(optionally `begins_with(SK, 'ORDER#')` to fetch only orders), in one
partition, one round trip, no join.

**Q: What's the difference between LSI and GSI, and why does it matter
operationally?**
A: LSI shares the base table's partition (same PK, alternate SK) and its
throughput capacity, must be defined at table creation and can't be added
later; GSI is a fully separate index with its own PK/SK and provisioned
throughput, can be added or removed anytime, but is only *eventually*
consistent (base-table reads can be strongly consistent, GSI reads cannot).

**Q: Explain quorum consistency: with N=3, W=2, R=2, can you ever read stale
data?**
A: No — W+R=4 > N=3 guarantees every read quorum overlaps every write
quorum by at least one replica, so at least one replica in any read set has
seen the latest write. You *can* still read stale data if W+R ≤ N (e.g.,
W=1,R=1), which is a deliberate availability/latency trade some systems
allow per-request.

**Q: Cache is returning stale data intermittently after updates — what are
the likely causes and fixes?**
A: (1) Write-through/cache-aside code path failing to invalidate on update
(race between DB write and cache delete — prefer delete-then-write-DB, or
delete cache *after* DB commit, and consider a short TTL as a backstop);
(2) reading from a lagging replica while writing to primary; (3) a
thundering-herd recompute race where two requests repopulate the cache with
different values after a miss. Mitigation: version/timestamp-tag cached
values and reject writing back a version older than what's cached, plus a
sane TTL as a safety net regardless of invalidation logic correctness.

**Q: When would you choose Memcached over Redis for a pure cache?**
A: When you need dead-simple horizontal scaling with zero operational
overhead (multi-threaded by design, trivial client-side sharding, no
persistence/replication to configure) and don't need Redis's data
structures, pub/sub, scripting, or durability options — a genuinely
stateless, disposable cache layer where losing all contents on restart is
completely fine.

**Q: How do you avoid the thundering herd problem when a very hot cache key
expires?**
A: Jittered/probabilistic early refresh (recompute slightly before actual
expiry, probability increasing as expiry approaches, so recomputation
smears across time instead of spiking at the exact TTL boundary), or a
short mutex key (`NX` lock) so only one request recomputes while others
either wait briefly or serve the (soon-to-expire) stale value.

**Q: Why can `NOT IN`-style "does this exist anywhere" checks be expensive
in a KV store, and what's the idiomatic fix?**
A: There's no secondary index by default — checking existence across
values (not keys) requires a full scan unless you've explicitly built a
secondary structure (a Set of existing values, a GSI, a search index).
Idiomatic fix: maintain the inverse mapping explicitly at write time (e.g.,
a Redis `Set` of "emails in use" updated alongside the primary write, or a
DynamoDB GSI keyed on the attribute you need to look up by) — KV stores
require you to design your indexes into the write path, not add them
after the fact.
