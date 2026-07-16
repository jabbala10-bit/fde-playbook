# Database Setup and Configuration Playbook for AI/ML Systems

Forward Deployed Engineer perspective: the database is not just storage. It is
the operational contract between the product, the model, the customer workflow,
security, compliance, and cost. A good setup lets the team answer:

- What data is authoritative?
- What access pattern must be fast?
- What consistency is required?
- What failure mode is acceptable?
- What must be observable during a customer escalation?
- What can be changed safely without downtime?

This guide covers setup steps, best practices, cloud database choices,
AI/ML-oriented configurations, strategies, and trade-offs.

Verified against current official cloud/product docs on 2026-07-16. See the
sources section at the end.

---

## 1. FDE Mental Model

For AI/ML systems, split database design by responsibility:

| Layer | Purpose | Common choices |
|---|---|---|
| System of record | Correct operational state, transactions, auditability | PostgreSQL, Aurora, Cloud SQL, AlloyDB, Azure PostgreSQL, SQL Server |
| Low-latency key-value | Sessions, feature flags, rate limits, idempotency, counters | Redis/Valkey, ElastiCache, Memorystore, Azure Cache for Redis, DynamoDB |
| Document store | Flexible JSON/product/user/customer objects | MongoDB Atlas, Cosmos DB, DocumentDB, Firestore |
| Vector/search layer | RAG retrieval, semantic search, agent memory, recommendations | pgvector, OpenSearch, Azure AI Search, Pinecone, Weaviate, Milvus/Zilliz, Databricks AI Search |
| Analytical store | Training data, feature analysis, evaluations, BI, batch scoring | BigQuery, Snowflake, Databricks Lakehouse, Redshift, Synapse/Fabric |
| Feature/online serving | ML features for real-time inference | Feast + Redis/Postgres/Bigtable/DynamoDB, Databricks Feature Store, Vertex AI Feature Store |
| Graph/relationship store | Knowledge graphs, entity resolution, lineage, fraud rings | Neo4j Aura, Amazon Neptune, Cosmos DB Gremlin, Spanner Graph/BigQuery Graph |
| Observability/audit store | Traces, prompts, evals, feedback, model events | OpenSearch, ClickHouse, BigQuery, Snowflake, Postgres partitions |

FDE rule:

> Choose the database by access pattern first, then by cloud convenience,
> then by organizational familiarity.

---

## 2. First 30 Questions Before Setup

Ask these before provisioning anything:

1. What is the source of truth?
2. What are the top 5 reads by user workflow?
3. What are the top 5 writes by workflow?
4. Is the workload OLTP, OLAP, search, vector retrieval, streaming, or mixed?
5. What p95/p99 latency is required?
6. What throughput is required now and in 12 months?
7. What consistency is required: strong, read-your-writes, session, eventual?
8. Is cross-region active-active required or only disaster recovery?
9. What is the RPO and RTO?
10. What data is PII, PHI, PCI, export-controlled, or customer-confidential?
11. Does data need tenant isolation?
12. Does the customer require private networking?
13. Does the customer require customer-managed keys?
14. What logs/traces can legally store prompts and responses?
15. How will secrets rotate?
16. What data must be deleted or retained?
17. What is the expected data growth curve?
18. What is the query fan-out?
19. Is there a hot tenant, hot user, hot document, or hot key risk?
20. What is the migration path from prototype to production?
21. How will schema and index changes be deployed?
22. How are backups tested?
23. How are restores tested?
24. What metrics trigger rollback?
25. Who owns database incidents?
26. How are model and embedding versions tracked?
27. How are vector indexes rebuilt safely?
28. How is retrieval quality evaluated?
29. What cost guardrails exist?
30. What must be explainable to the customer during a review?

---

## 3. Cloud Database Selection Matrix

### 3.1 If you need transactional correctness

Use managed PostgreSQL or a relational database.

| Cloud | Strong default options | AI/ML note |
|---|---|---|
| AWS | Aurora PostgreSQL, RDS PostgreSQL, RDS MySQL, Aurora MySQL | Aurora PostgreSQL supports `pgvector` and can be used with Amazon Bedrock Knowledge Bases |
| Google Cloud | AlloyDB for PostgreSQL, Cloud SQL, Spanner | AlloyDB AI includes vector search, model calls, and AI functions |
| Azure | Azure Database for PostgreSQL Flexible Server, Azure SQL | PostgreSQL Flexible Server supports `pgvector`; Azure SQL is strong for enterprise app integration |

Choose this when:

- You need transactions.
- You need constraints and relational joins.
- You need an operational source of truth.
- You need tenant-aware metadata filters with vectors.
- You want one store for app data plus moderate RAG.

Trade-off:

- Great correctness and operational simplicity.
- Vector search can become limiting for very high-scale recall/latency needs.

### 3.2 If you need hybrid keyword + vector search

Use a search engine or managed search service.

| Cloud/provider | Good fit |
|---|---|
| AWS OpenSearch Serverless vector search | RAG, semantic search, product/document search, hybrid retrieval |
| Azure AI Search | Enterprise RAG, hybrid search, Azure OpenAI integration, permission-aware knowledge |
| Elastic Cloud | Search-heavy systems, observability/search convergence, hybrid retrieval |
| Databricks AI Search | Lakehouse-native retrieval, Delta table sync, hybrid search, reranking |

Choose this when:

- Exact terms, SKUs, case IDs, law citations, or product codes matter.
- You need filters, facets, aggregations, text analyzers, and vector search.
- You need search relevance tuning.

Trade-off:

- Better retrieval UX than pure vector search.
- More moving pieces if your source of truth is elsewhere.

### 3.3 If you need a dedicated vector database

Use Pinecone, Weaviate Cloud, Milvus/Zilliz, Qdrant Cloud, or similar.

Choose this when:

- Vectors are the main product path.
- You need high recall/low latency at large scale.
- You need namespaces, metadata filters, hybrid search, or agent memory.
- Your team wants a purpose-built retrieval service.

Trade-off:

- Strong retrieval ergonomics.
- Another data store to sync, secure, monitor, and govern.

### 3.4 If you need high-scale key-value or document access

| Pattern | Good options |
|---|---|
| Massive key-value scale | DynamoDB, Cosmos DB, Bigtable |
| Flexible document model | MongoDB Atlas, Cosmos DB for NoSQL, Firestore, DocumentDB |
| Low-latency cache/state | Redis/Valkey, ElastiCache, Memorystore, Azure Cache for Redis |

Choose this when:

- Access pattern is known and key-driven.
- Schema changes often.
- You need extremely high throughput.
- You do not need arbitrary joins.

Trade-off:

- High scale and flexible writes.
- You design indexes/access paths upfront.

### 3.5 If you need analytics, training data, or offline features

| Cloud/provider | Good fit |
|---|---|
| BigQuery | Serverless analytics, BigQuery ML/AI, vector search in SQL, large-scale evaluation |
| Snowflake | Enterprise data sharing, Cortex AI, vector type/functions, governance |
| Databricks | Lakehouse, Delta, ML pipelines, feature engineering, AI Search |
| Redshift | AWS data warehouse, BI, large SQL analytics |
| Synapse/Fabric | Microsoft analytics ecosystem |

Choose this when:

- Query scans are large.
- Workload is analytical, not transactional.
- You need training datasets, eval datasets, batch inference, or dashboards.

Trade-off:

- Excellent for analytics and ML pipelines.
- Not the default place for user-facing transactional reads.

---

## 4. Reference Architecture Patterns

### 4.1 Production RAG on managed PostgreSQL

Good for: customer support copilots, internal policy assistants, small to medium
knowledge bases, strong metadata filters.

```text
Object store/doc source
  -> ingestion job
  -> parse/chunk
  -> embedding model
  -> PostgreSQL table with text, metadata, embedding
  -> pgvector HNSW/IVFFLAT index
  -> app retrieves top_k with tenant/security filters
  -> reranker or LLM response
```

Recommended setup:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE rag_chunks (
    chunk_id        UUID PRIMARY KEY,
    tenant_id       BIGINT NOT NULL,
    source_id       TEXT NOT NULL,
    document_id     TEXT NOT NULL,
    chunk_ordinal   INTEGER NOT NULL,
    content         TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}',
    embedding_model TEXT NOT NULL,
    embedding_dim   INTEGER NOT NULL,
    embedding       vector(1536) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ NULL
);

CREATE INDEX idx_rag_chunks_tenant_doc
ON rag_chunks (tenant_id, document_id);

CREATE INDEX idx_rag_chunks_metadata
ON rag_chunks USING GIN (metadata);

CREATE INDEX idx_rag_chunks_embedding_hnsw
ON rag_chunks USING hnsw (embedding vector_cosine_ops);
```

FDE notes:

- Always include `tenant_id`.
- Always include source provenance.
- Store embedding model and dimension.
- Store content hash for idempotent re-indexing.
- Keep metadata filterable.
- Do not store only vectors. Store enough text/provenance to explain the answer.

Trade-off:

- Unified data layer, simpler consistency.
- Scaling ceiling arrives earlier than specialized vector services.

### 4.2 Production RAG with search engine

Good for: enterprise search, SKUs, contracts, legal docs, support tickets,
hybrid keyword/vector workloads.

```text
Source systems
  -> ingestion/indexing pipeline
  -> search index with text fields, keyword fields, metadata, vectors
  -> hybrid retrieval: lexical + vector + filters
  -> reranking
  -> LLM response with citations
```

Configuration priorities:

- Analyzer/tokenizer choice.
- Exact-match keyword fields for IDs.
- Vector field dimension and similarity metric.
- Metadata filters for tenant, ACL, language, date, source type.
- Refresh interval and indexing latency.
- Index lifecycle management.
- Relevance evaluation set.

Trade-off:

- Best practical retrieval quality for many enterprise RAG systems.
- Sync and source-of-truth consistency must be engineered.

### 4.3 Agent memory store

Good for: AI agents that need user preferences, task history, tool outcomes,
and long-term memory.

Recommended split:

| Memory type | Store |
|---|---|
| Session state | Redis/Valkey |
| Durable task state | PostgreSQL/DynamoDB/Cosmos DB |
| Semantic memory | Vector DB/search |
| Audit log | PostgreSQL partitions, OpenSearch, BigQuery/Snowflake |
| Tool idempotency keys | Redis/DynamoDB/PostgreSQL unique table |

Minimum schema:

```sql
CREATE TABLE agent_events (
    event_id      UUID PRIMARY KEY,
    tenant_id     BIGINT NOT NULL,
    session_id    TEXT NOT NULL,
    actor_id      TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    tool_name     TEXT,
    input_hash    TEXT,
    output_hash   TEXT,
    policy_result TEXT NOT NULL,
    payload       JSONB NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_agent_events_session_time
ON agent_events (tenant_id, session_id, created_at DESC);
```

FDE notes:

- Separate memory from audit. Memory can be summarized/forgotten. Audit often
  has retention and legal requirements.
- Use idempotency keys for side-effecting tools.
- Store policy decisions before side effects.

### 4.4 Feature store architecture

Good for: fraud, recommendations, personalization, risk scoring.

```text
Raw events
  -> streaming/batch pipelines
  -> offline feature store in warehouse/lakehouse
  -> online feature store in Redis/DynamoDB/Bigtable/Cosmos DB
  -> model serving
  -> predictions and labels back to warehouse
```

Setup decisions:

- Feature freshness SLA.
- Point-in-time correctness.
- Online/offline feature parity.
- Backfill strategy.
- Feature ownership.
- Model version and feature schema version.

Trade-off:

- Feature stores reduce training-serving skew.
- They introduce another governance and freshness surface.

---

## 5. Universal Database Setup Steps

### Step 1: Classify the workload

```text
OLTP       = many small transactional reads/writes
OLAP       = large scans, aggregates, BI, training data
Search     = keyword, filters, relevance, ranking
Vector     = embedding similarity and RAG
Cache      = low-latency ephemeral lookup
Graph      = relationship traversal
Streaming  = time-ordered events and state
```

### Step 2: Define SLOs

For every primary workflow:

```text
p50 latency:
p95 latency:
p99 latency:
availability:
RPO:
RTO:
max replica lag:
max index freshness lag:
max retrieval latency:
max cost per 1k requests:
```

### Step 3: Design network and access

Best practice:

- Use private networking for production.
- Disable public access unless explicitly required.
- Use security groups/firewalls to restrict source services.
- Use IAM/service principals/managed identities where possible.
- Store secrets in a managed secret store.
- Rotate credentials.
- Use TLS in transit.
- Use customer-managed keys if required by the customer.

### Step 4: Design identity and roles

Separate roles:

```text
migration_admin  -> DDL changes
app_writer       -> normal app reads/writes
app_readonly     -> read-only paths
etl_writer       -> ingestion jobs
analyst_readonly -> BI/ad hoc analysis
breakglass_admin -> emergency only, audited
```

Do not let the application run as database owner or superuser.

### Step 5: Design backup and restore

Minimum:

- Automated backups.
- Point-in-time recovery where available.
- Cross-region copy for critical systems.
- Restore drill before production launch.
- Documented RPO/RTO.
- Backup encryption.
- Access controls on backups.

FDE phrase:

> A backup that has never been restored is only an assumption.

### Step 6: Design observability

Minimum production telemetry:

- Query latency by fingerprint.
- Top queries by total time.
- Connection count and pool saturation.
- CPU, memory, disk, IOPS.
- Lock waits and deadlocks.
- Replication lag.
- Backup success/failure.
- Index build and index freshness.
- Cache hit ratio and evictions.
- Vector recall, retrieval latency, and source freshness.
- Cost by tenant/workload where possible.

### Step 7: Define migration process

Use an expand/contract workflow:

```text
1. Add backward-compatible schema.
2. Deploy app writing old and new shape.
3. Backfill safely in batches.
4. Validate.
5. Switch reads.
6. Remove old shape later.
```

Avoid large blocking migrations during customer usage windows.

---

## 6. Environment Strategy

| Environment | Purpose | Configuration |
|---|---|---|
| Local | Developer iteration | Docker, sample data, no real secrets |
| Dev | Integration | Small managed instance, representative schemas |
| Staging | Release validation | Production-like parameters, masked data where allowed |
| Performance | Load testing | Production-scale data shape, isolated from staging |
| Production | Customer workload | HA, backup, monitoring, alerting, change control |
| DR | Recovery path | Cross-region backup/replica, tested failover |

Best practices:

- Keep schemas consistent across environments.
- Keep production data out of local/dev unless masked and approved.
- Keep database parameter drift visible.
- Use infrastructure as code.
- Use separate cloud accounts/projects/subscriptions for prod when possible.

---

## 7. Configuration Baselines by Database Type

### 7.1 Managed PostgreSQL / Aurora / AlloyDB / Azure PostgreSQL

Use for:

- Transactional AI app backend.
- RAG metadata plus pgvector.
- Customer workflow state.
- Model/eval metadata.
- Audit-friendly relational data.

Baseline setup:

```sql
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS vector;
```

Configuration checklist:

- Enable automated backups and PITR.
- Use private endpoint/VPC/VNet.
- Enforce TLS.
- Configure parameter group/database flags intentionally.
- Enable slow query logging.
- Enable query statistics extension if supported.
- Use connection pooling.
- Create read replicas only when read scale or isolation requires them.
- Use partitioning for time-series traces/events.
- Use `jsonb` carefully for sparse metadata, not core relational facts.
- Use `pgvector` for moderate-scale vector search and strong metadata filters.

Important settings/concepts:

| Area | What to check |
|---|---|
| Connections | Pool size, max connections, connection storm protection |
| Memory | Sort/hash memory, buffer cache, instance sizing |
| WAL/redo | Write volume, checkpoint pressure, replication slots |
| Autovacuum | Hot tables, dead tuples, bloat |
| Statistics | `ANALYZE`, skewed columns, extended stats |
| Indexes | Composite indexes, partial indexes, vector indexes |
| Replication | Lag, read-after-write routing |

Trade-offs:

- Strong consistency and SQL power.
- Vertical scaling and index maintenance need attention.
- High-dimensional vector search can become memory/index heavy.

### 7.2 DynamoDB / Cosmos DB / Bigtable / Firestore

Use for:

- Massive key-value access.
- Event/session state.
- User profiles.
- High-scale sparse records.
- Online features.

Configuration checklist:

- Model access patterns before table design.
- Choose partition key for high cardinality and even distribution.
- Avoid hot partitions.
- Use sort keys for time/entity ranges.
- Use GSIs/indexes only for real access patterns.
- Define TTL for ephemeral records.
- Use conditional writes for optimistic concurrency.
- Enable point-in-time recovery where available.
- Configure autoscaling/on-demand capacity intentionally.
- Monitor throttles, consumed capacity, hot keys, and latency.

Dynamo-style design example:

```text
PK = TENANT#42#USER#123
SK = SESSION#2026-07-16T10:01:22Z

PK = TENANT#42#DOC#abc
SK = CHUNK#000001
```

Trade-offs:

- Very high scale and operational simplicity.
- Query flexibility is limited to designed keys/indexes.
- Secondary indexes can be eventually consistent depending on platform.

### 7.3 Redis / Valkey / ElastiCache / Memorystore / Azure Cache

Use for:

- Cache-aside.
- Sessions.
- Rate limits.
- Agent short-term memory.
- Idempotency locks.
- Work queues when requirements are simple.

Configuration checklist:

- Decide cache vs primary-store behavior.
- If cache, use eviction policy such as allkeys-lru/lfu.
- If durable-ish, enable persistence/replication where supported.
- Set TTLs on cache keys.
- Add TTL jitter to prevent mass expiration.
- Use private networking.
- Enable auth/TLS.
- Avoid unbounded collections.
- Avoid blocking commands in production paths.
- Monitor hit ratio, evictions, memory, slow commands, blocked clients.

Trade-offs:

- Extremely low latency.
- Memory is expensive.
- Stale data and invalidation are correctness risks.

### 7.4 Search engines and vector search services

Use for:

- RAG.
- Document/product/support search.
- Hybrid keyword + vector search.
- Facets, filters, relevance tuning.

Configuration checklist:

- Design index mappings/schema.
- Keep exact-match fields as keyword/filterable fields.
- Store vector fields with correct dimension and metric.
- Store source ID, tenant ID, ACL fields, document version, chunk ordinal.
- Configure refresh/indexing latency expectations.
- Use aliases or versioned indexes for safe rebuilds.
- Build relevance test sets.
- Track recall@k, precision@k, MRR, citation precision.
- Monitor indexing failures and source freshness lag.

Trade-offs:

- Search quality and hybrid retrieval are strong.
- Sync pipeline and index consistency become production concerns.

### 7.5 Dedicated vector databases

Use for:

- Large-scale semantic search.
- Agent memory.
- RAG over many tenants.
- Recommendation retrieval.

Configuration checklist:

- Pick distance metric: cosine, dot product, or Euclidean.
- Match metric to embedding model guidance.
- Fix embedding dimension per index.
- Decide namespace/collection strategy.
- Store metadata filters for tenant, ACL, language, source, version, time.
- Decide index type and recall/latency target.
- Batch upserts.
- Version embeddings and indexes.
- Plan re-embedding and index rebuilds.
- Monitor recall, latency, QPS, index freshness, and cost.

Trade-offs:

- Purpose-built retrieval.
- Additional data replication and governance surface.

### 7.6 Data warehouse / lakehouse

Use for:

- Training datasets.
- Offline feature engineering.
- Evaluation sets.
- Batch scoring.
- BI and analytics.
- Prompt/response analytics when retention allows.

Configuration checklist:

- Partition by time or high-value pruning column.
- Cluster/sort by tenant, entity, or common filters.
- Separate raw, curated, feature, and serving datasets.
- Use table lifecycle policies.
- Track data lineage.
- Track model/eval version metadata.
- Control cost with warehouses, slots, reservations, or workload groups.
- Use materialized views for repeated aggregates.
- Use row/column-level security for sensitive data.

Trade-offs:

- Excellent for analytics and ML development.
- Not a low-latency transactional backend.

### 7.7 Graph databases

Use for:

- Entity resolution.
- Knowledge graphs.
- Fraud rings.
- Permission inheritance.
- Supply-chain or relationship-heavy reasoning.

Configuration checklist:

- Model nodes and edges around traversal questions.
- Index node IDs and high-cardinality lookup fields.
- Avoid unbounded traversals.
- Define max traversal depth.
- Store provenance on edges.
- Track graph refresh frequency.
- Consider hybrid graph + vector retrieval for GraphRAG.

Trade-offs:

- Strong relationship reasoning.
- Requires graph-literate modeling and query discipline.

---

## 8. Vector Database Configuration Deep Dive

### 8.1 Embedding model choices

Record these with every vector:

```text
embedding_model
embedding_dimension
distance_metric
embedding_created_at
source_document_version
chunking_strategy
normalization_strategy
```

Do not mix incompatible embedding models in the same index unless the platform
and ranking strategy explicitly support it.

### 8.2 Distance metric

| Metric | Use when |
|---|---|
| Cosine | Text embeddings where direction matters more than magnitude |
| Dot product | Model trained/normalized for inner product search |
| Euclidean/L2 | Spatial or embeddings designed for L2 distance |

If vectors are normalized, cosine and dot-product rankings can be closely
related. Still, use the metric recommended for the embedding model.

### 8.3 Index types and trade-offs

| Index type | Fit | Trade-off |
|---|---|---|
| Flat/brute force | Small filtered sets, exact recall | Slow at large scale |
| HNSW | Low-latency ANN, dynamic updates | Memory-heavy, tuning required |
| IVF/IVFFLAT | Large datasets, batch-oriented indexes | Recall depends on lists/probes |
| ScaNN | Google ecosystem/vector search optimization | Platform-specific tuning |
| DiskANN | Large vector sets, disk-backed efficiency | Platform-specific operational model |
| Quantized index | Lower memory/cost | Some accuracy loss |

### 8.4 HNSW knobs

Common knobs:

- `m`: graph connectivity. Higher can improve recall but increases memory/build cost.
- `ef_construction`: build-time candidate list. Higher improves index quality but slows build.
- `ef_search`: query-time candidate list. Higher improves recall but increases latency.

FDE tuning loop:

```text
1. Build a labeled retrieval eval set.
2. Measure recall@k, MRR, latency, and cost.
3. Increase recall knobs until latency/cost breaks SLO.
4. Keep separate settings for interactive vs batch workflows.
```

### 8.5 Metadata filtering

Every production RAG/vector index should support filters such as:

```text
tenant_id
acl_group
source_system
document_type
language
created_at/effective_at
document_version
jurisdiction/region
classification
```

Never rely on the LLM to ignore unauthorized retrieved content. Authorization
must happen before generation.

### 8.6 Multi-tenancy

Options:

| Strategy | Pros | Cons |
|---|---|---|
| Tenant filter in shared index | Simple, cost efficient | Isolation depends on correct filters |
| Namespace/collection per tenant | Better isolation, simpler deletion | More operational overhead |
| Dedicated instance per tenant | Strong isolation | Highest cost and management burden |

FDE default:

- Small/medium tenants: shared index with mandatory tenant filter and tests.
- Regulated/high-value tenants: namespace or dedicated collection.
- Strict enterprise isolation: dedicated project/account/instance if required.

### 8.7 Index freshness

Track:

```text
source_updated_at
ingested_at
embedded_at
indexed_at
searchable_at
```

Alert on freshness lag when the knowledge base powers customer decisions.

---

## 9. Cloud Provider Reference

### 9.1 AWS

Common AI/ML database choices:

| Service | Use |
|---|---|
| Aurora PostgreSQL / RDS PostgreSQL | Transactional app DB, pgvector, Bedrock Knowledge Bases |
| DynamoDB | High-scale key-value/document access, online features, session/state |
| OpenSearch Service / Serverless vector search | Hybrid search, vector search, logs/search, RAG |
| ElastiCache for Redis/Valkey | Cache, session, rate limit, short-term agent state |
| Redshift | Analytics, BI, feature analysis |
| Neptune | Graph and knowledge graph use cases |
| Timestream | Time-series telemetry |
| S3 + Athena/Glue | Data lake, ingestion, archival analytics |

AWS setup strategy:

- Use VPC-private databases.
- Use Secrets Manager for credentials.
- Use IAM auth where suitable.
- Use KMS encryption.
- Use CloudWatch alarms for CPU, connections, IOPS, latency, throttles.
- For Aurora pgvector with Bedrock, enable `pgvector`, create vector table,
  HNSW index, text index, metadata index, and least-privilege role.
- For DynamoDB, design partition/sort keys from access patterns and monitor
  throttles/hot partitions.
- For OpenSearch vector collections, design index mappings and evaluate
  compression/recall/latency trade-offs.

### 9.2 Google Cloud

Common AI/ML database choices:

| Service | Use |
|---|---|
| AlloyDB for PostgreSQL | High-performance Postgres, AlloyDB AI, vector search |
| Cloud SQL | Managed relational DB for standard app workloads |
| Spanner | Globally distributed relational workloads |
| BigQuery | Analytics, ML, vector search over large tables, eval datasets |
| Firestore | Serverless document/mobile/web apps |
| Bigtable | High-throughput wide-column/time-series/feature access |
| Memorystore | Redis/Valkey cache |
| Vertex AI Feature Store | Feature serving and ML platform integration |

GCP setup strategy:

- Prefer private IP/Private Service Connect for production.
- Use Secret Manager.
- Use IAM and service accounts carefully.
- Use Cloud Monitoring dashboards and alerting.
- Use BigQuery partitioning/clustering for analytics cost control.
- Use AlloyDB AI/vector search when Postgres compatibility plus AI functions
  matter.
- Use BigQuery vector search when embeddings already live in analytical tables
  and batch/analytical retrieval is acceptable.

### 9.3 Azure

Common AI/ML database choices:

| Service | Use |
|---|---|
| Azure Database for PostgreSQL Flexible Server | Postgres app DB, pgvector, AI extension integrations |
| Azure SQL Database / SQL Managed Instance | Enterprise relational workloads |
| Cosmos DB for NoSQL | Global document/KV workloads and integrated vector search |
| Azure AI Search | Enterprise hybrid/vector search and RAG knowledge layer |
| Azure Cache for Redis | Cache/session/rate limit |
| Synapse / Microsoft Fabric / OneLake | Analytics, lakehouse, BI, ML data |
| Azure Data Explorer | Telemetry/time-series/log analytics |

Azure setup strategy:

- Use private endpoints.
- Use managed identities where possible.
- Use Key Vault for secrets.
- Use Defender/monitoring policies if required by enterprise governance.
- Use Azure AI Search for hybrid RAG and permission-aware enterprise search.
- Use PostgreSQL `pgvector` when transactional metadata and vector search should
  live together.
- Use Cosmos DB vector search when vectors naturally belong inside JSON
  documents and partition-key access is strong.

### 9.4 Cross-cloud and independent providers

| Provider | Use |
|---|---|
| MongoDB Atlas | Managed document DB, Atlas Vector Search, flexible app data |
| Pinecone | Purpose-built vector database for semantic search and agent memory |
| Weaviate Cloud | Vector-first database, hybrid search, multi-modal/vector workloads |
| Zilliz/Milvus | Open-source vector database ecosystem, large-scale vector search |
| Qdrant Cloud | Vector search with payload filters and Rust-based engine |
| Snowflake | Governed data cloud, Cortex AI, vector functions, analytics |
| Databricks | Lakehouse, ML pipelines, Delta, AI Search, feature engineering |
| Neo4j Aura | Graph and knowledge graph workloads |

FDE note:

> Independent providers can be the fastest path to capability, but enterprise
> customers will ask about network boundaries, data residency, IAM integration,
> encryption, audit logs, procurement, and exit strategy.

---

## 10. Configuration Strategies by Use Case

### 10.1 Customer support RAG

Recommended:

- PostgreSQL/Aurora/AlloyDB/Azure PostgreSQL for tickets, users, metadata.
- Azure AI Search/OpenSearch/Databricks AI Search/Pinecone/Weaviate for retrieval.
- BigQuery/Snowflake/Databricks for feedback/eval analytics.
- Redis for sessions and rate limits.

Key configuration:

- Tenant and ACL filters mandatory.
- Hybrid search for product names, order IDs, error codes.
- Source citations required.
- Freshness lag monitored.
- Prompt/response retention policy defined.

### 10.2 Real-time recommendation system

Recommended:

- DynamoDB/Cosmos DB/Bigtable for user/item online features.
- Redis for hot candidate cache.
- Vector DB/search for candidate generation.
- Warehouse/lakehouse for training and evaluation.

Key configuration:

- Feature freshness SLA.
- Sharded hot keys.
- Batch and streaming updates.
- A/B experiment dimensions.
- Cost per recommendation monitored.

### 10.3 Fraud/anomaly detection

Recommended:

- PostgreSQL/Spanner/Aurora for transactional state.
- Graph DB for relationship/ring analysis.
- Streaming store/events in Kafka/Pub/Sub/Kinesis plus warehouse.
- Redis/DynamoDB/Bigtable for online features.

Key configuration:

- Strong audit trail.
- Low-latency feature lookup.
- Explainability fields stored with decisions.
- Immutable event history.
- Backtesting dataset retained.

### 10.4 Agentic workflow platform

Recommended:

- PostgreSQL for durable task state and audit metadata.
- Redis for session state and locks.
- Vector DB/search for memory/retrieval.
- Object storage for artifacts.
- Warehouse/lakehouse for evals and telemetry.

Key configuration:

- Tool action idempotency.
- Human approval state.
- Policy decision logging.
- Rollback/compensation records.
- Trace ID on every database write.

### 10.5 LLM evaluation and observability

Recommended:

- Warehouse/lakehouse for aggregated eval results.
- PostgreSQL for eval suite definitions and release gates.
- Object storage for sampled artifacts.
- OpenSearch/ClickHouse for trace exploration if high volume.

Key configuration:

- Model version, prompt version, retrieval index version.
- Dataset version.
- Human label schema.
- Retention policy.
- PII redaction before logging where required.

---

## 11. Trade-Off Reference

| Decision | Benefit | Cost/risk |
|---|---|---|
| Managed DB over self-hosted | Less operations burden | Less low-level control |
| PostgreSQL + pgvector | Unified transactional and vector data | Scaling vector workloads can be harder |
| Dedicated vector DB | High-scale retrieval | Data sync and extra vendor surface |
| Search engine for RAG | Hybrid relevance, filters, facets | Index management and eventual consistency |
| NoSQL/KV | High throughput and flexible records | Access patterns must be designed upfront |
| Cache-aside | Lower latency and DB load | Stale data and invalidation complexity |
| Read replicas | Read scale and workload isolation | Replica lag and read-your-write issues |
| Multi-region active-active | Resilience and locality | Conflict resolution and cost |
| Strong consistency | Easier correctness | Higher latency or lower availability under failure |
| Eventual consistency | Scale and availability | More app logic and user-visible anomalies |
| Tenant shared index | Lower cost | Filter correctness is critical |
| Tenant dedicated index | Better isolation | Higher operational overhead |
| Quantized vectors | Lower memory/cost | Possible recall loss |
| Higher vector recall | Better answer quality | Higher latency/cost |

---

## 12. Production Readiness Checklist

### Access and security

- Private endpoint or private networking configured.
- TLS required.
- Encryption at rest enabled.
- Customer-managed keys configured if required.
- Secrets stored in managed secret service.
- Credentials rotated.
- Least-privilege roles created.
- Break-glass access audited.
- Tenant isolation tested.

### Reliability

- Automated backups enabled.
- PITR enabled where possible.
- Restore drill completed.
- Multi-AZ/zone HA enabled for production.
- DR plan documented.
- RPO/RTO documented.
- Failover tested.

### Performance

- Query/index plan reviewed.
- Connection pooling configured.
- Slow query logging enabled.
- Hot partition/key analysis done.
- Cache strategy documented.
- Vector recall/latency evaluated.
- Load test run with production-like data shape.

### AI/ML specific

- Embedding model/version stored.
- Vector dimension fixed and validated.
- Metadata filters enforced.
- Index freshness monitored.
- Retrieval eval set exists.
- Prompt/model/retrieval versions linked in traces.
- PII/prompt retention policy implemented.
- Human feedback loop captured.

### Operations

- Dashboards created.
- Alerts mapped to runbooks.
- Cost budgets and alerts configured.
- Migration process documented.
- Rollback process tested.
- Ownership defined.

---

## 13. FDE Articulation Patterns

### Database choice

Weak:

> I chose DynamoDB because it scales.

Strong:

> The access pattern is key-based, high-throughput, and does not need joins.
> DynamoDB fits because we can model the primary reads with partition and sort
> keys. The trade-off is that new ad hoc access patterns require GSIs or a
> separate analytical/search path.

### Vector database choice

Weak:

> We need a vector DB for RAG.

Strong:

> We need filtered, tenant-safe semantic retrieval with citation quality. If
> the corpus is moderate and metadata consistency matters most, PostgreSQL with
> pgvector is simpler. If recall/latency at large scale is the bottleneck, a
> dedicated vector DB or search service is more appropriate.

### Cache choice

Weak:

> Add Redis to make it faster.

Strong:

> Redis reduces p95 latency for repeated reads, but introduces cache staleness
> and invalidation risk. I would only cache values with a clear TTL, versioning
> or invalidation path, and metrics for hit ratio and stale reads.

### Cloud provider alignment

Weak:

> Use whatever the cloud has.

Strong:

> I would prefer the customer's native cloud database when it meets the access
> pattern and governance requirements, because private networking, IAM, audit,
> procurement, and operational support are easier. I would go outside the cloud
> only when the product capability gap justifies the integration cost.

---

## 14. Common Anti-Patterns

- Running production app traffic on a database with public access enabled.
- Using one superuser credential for app, migrations, and analysts.
- No restore test before launch.
- Treating a vector index as the system of record.
- Storing vectors without source provenance.
- RAG without ACL filters.
- RAG without freshness monitoring.
- Putting analytical dashboards on the OLTP primary.
- Using DynamoDB/Cosmos DB scans in hot request paths.
- Treating Redis as durable without persistence/eviction strategy.
- Adding a read replica and forgetting read-after-write consistency.
- Mixing embedding models in one index without version separation.
- Rebuilding indexes in place without alias/version swap.
- No cost alerts for warehouses, vector search, or embedding generation.

---

## 15. One-Page Setup Flow

```text
1. Workload
   OLTP, OLAP, vector, search, cache, graph, document, feature serving.

2. Access pattern
   Top reads/writes, latency, consistency, tenant/security filters.

3. Cloud fit
   Prefer native managed service if it meets capability and governance needs.

4. Data model
   Schema, keys, indexes, partitions, vector dimensions, metadata, provenance.

5. Security
   Private networking, IAM, secrets, TLS, encryption, tenant isolation.

6. Reliability
   HA, backups, PITR, DR, restore tests, failover plan.

7. Performance
   Pooling, index strategy, cache strategy, capacity, load test.

8. AI/ML controls
   Embedding/model versions, retrieval evals, freshness, prompt retention.

9. Observability
   Query latency, errors, locks, lag, cost, retrieval quality, index health.

10. Operations
   Migration plan, rollback, runbooks, owners, alerts, cost budgets.
```

---

## 16. Sources Checked

- AWS Aurora PostgreSQL as a Bedrock Knowledge Base and pgvector setup:
  https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html
- AWS OpenSearch Serverless vector search collections:
  https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-vector-search.html
- AWS DynamoDB developer guide:
  https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Introduction.html
- AWS ElastiCache overview:
  https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/WhatIs.html
- Google Cloud AlloyDB AI embeddings/vector search docs:
  https://cloud.google.com/alloydb/docs/ai/work-with-embeddings
- Google BigQuery vector search:
  https://cloud.google.com/bigquery/docs/vector-search
- Microsoft Azure Database for PostgreSQL pgvector:
  https://learn.microsoft.com/en-us/azure/postgresql/extensions/how-to-use-pgvector
- Microsoft Azure AI Search vector search:
  https://learn.microsoft.com/en-us/azure/search/vector-search-overview
- Microsoft Azure Cosmos DB vector search:
  https://learn.microsoft.com/en-us/azure/cosmos-db/vector-search
- Snowflake Cortex vector embeddings and vector functions:
  https://docs.snowflake.com/en/user-guide/snowflake-cortex/vector-embeddings
- Databricks AI Search:
  https://docs.databricks.com/aws/en/ai-search/ai-search
- Pinecone documentation:
  https://docs.pinecone.io/guides/get-started/overview
- Weaviate vector indexing:
  https://docs.weaviate.io/weaviate/concepts/vector-index
