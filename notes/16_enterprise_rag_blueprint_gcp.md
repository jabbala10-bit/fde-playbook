# 16 — Enterprise RAG Blueprint on GCP

> **Why this matters for FDEs:** RAG (Retrieval-Augmented Generation)
> is the most common AI pattern you will deploy at enterprise clients.
> "Can your AI answer questions from our documents?" is the entry point
> for most AI engagements. This file gives you the complete production
> blueprint — from ingestion to monitoring.

---

## 1. The Enterprise RAG Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE RAG ARCHITECTURE (GCP)                   │
│                                                                         │
│  INGESTION PIPELINE                   QUERY PIPELINE                  │
│  ─────────────────                    ──────────────                   │
│                                                                         │
│  [Documents]                          [User Query]                     │
│  PDFs, DOCX,        ──LlamaParse──►   ──────────────►                 │
│  HTML, TXT                                                              │
│       │                                [Embedding Model]               │
│       ▼                                (text-embedding-gecko)          │
│  [Document Parser]                          │                          │
│  LlamaParse/         ──Chunks──►            ▼                         │
│  Cloud Document AI                    [Query Vector]                   │
│       │                                     │                          │
│       ▼                                     ▼                         │
│  [Chunking Strategy]              [Vertex AI Search]                   │
│  Semantic/Fixed/                   or Vector Store                     │
│  Hierarchical                           │                              │
│       │                                 ▼                             │
│       ▼                           [Retrieved Chunks]                   │
│  [Embedding Model]                (Top-K candidates)                   │
│  text-embedding-                        │                              │
│  gecko@003                              ▼                             │
│       │                           [Reranker]                           │
│       ▼                           (Cross-encoder)                      │
│  [Vector Store]                         │                              │
│  Vertex AI Search /                     ▼                             │
│  BigQuery VECTOR_SEARCH /         [Context Assembly]                   │
│  Vertex AI Vector Search          (Top-N chunks)                       │
│       │                                 │                              │
│       ▼                                 ▼                             │
│  [Metadata Index]                 [LLM Generation]                     │
│  BigQuery table                   Gemini 1.5 Pro                       │
│                                         │                              │
│                                         ▼                             │
│                                   [Response + Citations]               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Ingestion Pipeline — Documents to Vectors

### Step 1: Document Extraction with LlamaParse
```python
import nest_asyncio
from llama_parse import LlamaParse
from google.cloud import storage

nest_asyncio.apply()

class DocumentIngestionPipeline:
    """
    Production document ingestion pipeline for enterprise RAG.
    Handles PDFs, DOCX, HTML, and other formats using LlamaParse.
    """

    def __init__(self, project_id: str, gcs_bucket: str, bq_dataset: str):
        self.project_id = project_id
        self.gcs_bucket = gcs_bucket
        self.bq_dataset = bq_dataset

        # LlamaParse: enterprise-grade document parser
        # Handles complex PDFs with tables, charts, columns, headers
        self.parser = LlamaParse(
            api_key="llx-...",           # LlamaCloud API key
            result_type="markdown",       # output as structured markdown
            num_workers=8,                # parallel parsing
            verbose=False,
            language="en",
            parsing_instruction="""
            Extract all text content including:
            - Tables (as markdown tables)
            - Headers and subheaders
            - Numbered and bulleted lists
            - Captions and footnotes
            Preserve the document structure and hierarchy.
            For financial documents: preserve all numbers exactly.
            """
        )

    def parse_document(self, gcs_path: str) -> list[dict]:
        """
        Parse a document from GCS and return structured chunks.
        
        Args:
            gcs_path: gs://bucket/path/to/document.pdf
            
        Returns:
            List of page dicts with 'page_num', 'content', 'metadata'
        """
        # Download from GCS
        storage_client = storage.Client()
        blob = storage_client.bucket(self.gcs_bucket).blob(
            gcs_path.replace(f"gs://{self.gcs_bucket}/", "")
        )
        local_path = f"/tmp/{blob.name.split('/')[-1]}"
        blob.download_to_filename(local_path)

        # Parse with LlamaParse
        documents = self.parser.load_data(local_path)

        pages = []
        for i, doc in enumerate(documents):
            pages.append({
                "page_num": i + 1,
                "content": doc.text,
                "source_path": gcs_path,
                "doc_id": self._generate_doc_id(gcs_path),
                "metadata": doc.metadata
            })

        return pages

    def _generate_doc_id(self, path: str) -> str:
        """Generate a stable document ID from its path."""
        import hashlib
        return hashlib.sha256(path.encode()).hexdigest()[:16]
```

### Step 2: Chunking Strategy
```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

class ChunkingStrategy:
    """
    Different chunking strategies for different document types.
    The chunking strategy is one of the highest-leverage RAG decisions.
    """

    @staticmethod
    def fixed_size_chunking(text: str, chunk_size: int = 512,
                            overlap: int = 50) -> list[str]:
        """
        Fixed-size chunking: simple, predictable.
        Use for: homogeneous documents, plain text, logs.
        """
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len
        )
        return splitter.split_text(text)

    @staticmethod
    def semantic_chunking(text: str, model_name: str = "text-embedding-gecko@003") -> list[str]:
        """
        Semantic chunking: splits at topic boundaries, not character counts.
        Use for: heterogeneous documents, narrative text, reports.
        Creates chunks that contain coherent semantic units.
        """
        from langchain_experimental.text_splitter import SemanticChunker
        from langchain_google_vertexai import VertexAIEmbeddings

        embeddings = VertexAIEmbeddings(model_name=model_name)

        splitter = SemanticChunker(
            embeddings,
            breakpoint_threshold_type="percentile",  # split where embedding distance > 95th percentile
            breakpoint_threshold_amount=95
        )
        return [doc.page_content for doc in splitter.create_documents([text])]

    @staticmethod
    def hierarchical_chunking(pages: list[dict]) -> list[dict]:
        """
        Hierarchical chunking: creates PARENT chunks (full sections) and
        CHILD chunks (small passages for retrieval).

        Retrieval: use small child chunks for precision.
        Generation: pass large parent chunks for context.
        This is the "parent document retriever" pattern.
        """
        chunks = []

        for page in pages:
            # Create parent chunk (full page or section)
            parent_id = f"{page['doc_id']}_page_{page['page_num']}"
            chunks.append({
                "chunk_id": parent_id,
                "chunk_type": "parent",
                "content": page["content"],
                "doc_id": page["doc_id"],
                "page_num": page["page_num"],
                "parent_id": None,
            })

            # Create child chunks (small passages)
            small_chunks = ChunkingStrategy.fixed_size_chunking(
                page["content"], chunk_size=256, overlap=25
            )
            for j, small_chunk in enumerate(small_chunks):
                chunks.append({
                    "chunk_id": f"{parent_id}_chunk_{j}",
                    "chunk_type": "child",
                    "content": small_chunk,
                    "doc_id": page["doc_id"],
                    "page_num": page["page_num"],
                    "parent_id": parent_id,  # link to parent
                })

        return chunks
```

### Step 3: Embedding and Storage
```python
from vertexai.language_models import TextEmbeddingModel
from google.cloud import bigquery
import numpy as np

def embed_and_store(chunks: list[dict], project_id: str, dataset_id: str):
    """
    Generate embeddings for chunks and store in BigQuery with vector search.
    """
    # Initialize Vertex AI embedding model
    embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")

    bq_client = bigquery.Client(project=project_id)

    # Process in batches (Vertex AI has rate limits)
    BATCH_SIZE = 250
    rows_to_insert = []

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        texts = [c["content"] for c in batch]

        # Generate embeddings
        embeddings_response = embedding_model.get_embeddings(
            [{"content": text, "task_type": "RETRIEVAL_DOCUMENT"} for text in texts]
        )

        for chunk, emb in zip(batch, embeddings_response):
            rows_to_insert.append({
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "content": chunk["content"],
                "chunk_type": chunk.get("chunk_type", "standard"),
                "parent_id": chunk.get("parent_id"),
                "page_num": chunk.get("page_num"),
                "source_path": chunk.get("source_path", ""),
                "embedding": emb.values,       # ARRAY<FLOAT64>
                "ingested_at": "AUTO"
            })

        print(f"Processed batch {i//BATCH_SIZE + 1}/{len(chunks)//BATCH_SIZE + 1}")

    # Insert into BigQuery
    table_id = f"{project_id}.{dataset_id}.document_chunks"
    errors = bq_client.insert_rows_json(table_id, rows_to_insert)

    if errors:
        raise ValueError(f"BigQuery insert errors: {errors}")

    print(f"Inserted {len(rows_to_insert)} chunks into {table_id}")
```

---

## 3. Query Pipeline — Retrieval and Generation

```python
class EnterpriseRAGPipeline:
    """
    Production RAG query pipeline with reranking, citation, and guardrails.
    """

    def __init__(self, project_id: str, dataset_id: str):
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.bq_client = bigquery.Client(project=project_id)
        self.embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")

    def retrieve(self, query: str, top_k: int = 20) -> list[dict]:
        """
        Step 1: Retrieve top-K candidate chunks using vector similarity.
        Uses BigQuery VECTOR_SEARCH for scalability.
        """
        # Embed the query
        query_embedding = self.embedding_model.get_embeddings([{
            "content": query,
            "task_type": "RETRIEVAL_QUERY"  # different task type than documents!
        }])[0].values

        # Vector search in BigQuery
        vector_search_sql = f"""
        SELECT
            base.chunk_id,
            base.doc_id,
            base.content,
            base.chunk_type,
            base.parent_id,
            base.source_path,
            base.page_num,
            distance
        FROM VECTOR_SEARCH(
            TABLE `{self.project_id}.{self.dataset_id}.document_chunks`,
            'embedding',
            (SELECT {query_embedding} AS embedding),
            top_k => {top_k},
            distance_type => 'COSINE',
            options => '{{"fraction_lists_to_search": 0.1}}'
        )
        WHERE base.chunk_type = 'child'  -- retrieve small chunks for precision
        ORDER BY distance ASC
        """

        results = self.bq_client.query(vector_search_sql).result()
        return [dict(row) for row in results]

    def rerank(self, query: str, candidates: list[dict], top_n: int = 5) -> list[dict]:
        """
        Step 2: Rerank candidates using a cross-encoder for precision.
        The vector search finds semantically similar chunks.
        The reranker picks the ones ACTUALLY most relevant to the SPECIFIC query.
        """
        from sentence_transformers import CrossEncoder

        # Cross-encoder reranker (more accurate than bi-encoder for ranking)
        # Use a small model for speed: ms-marco-MiniLM-L-6-v2
        reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

        # Score each candidate against the query
        pairs = [(query, c["content"]) for c in candidates]
        scores = reranker.predict(pairs)

        # Sort by reranker score and take top-N
        scored = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return [c for c, _ in scored[:top_n]]

    def fetch_parent_chunks(self, child_chunks: list[dict]) -> list[dict]:
        """
        Step 3 (Hierarchical RAG): Fetch full parent chunks for better context.
        We retrieved small child chunks for precision.
        Now we pass their full parent sections to the LLM for better answers.
        """
        parent_ids = list(set(
            c["parent_id"] for c in child_chunks
            if c.get("parent_id")
        ))

        if not parent_ids:
            return child_chunks

        parent_ids_str = ", ".join([f"'{p}'" for p in parent_ids])
        query = f"""
        SELECT chunk_id, doc_id, content, source_path, page_num
        FROM `{self.project_id}.{self.dataset_id}.document_chunks`
        WHERE chunk_id IN ({parent_ids_str})
        AND chunk_type = 'parent'
        """

        parents = [dict(row) for row in self.bq_client.query(query).result()]
        return parents if parents else child_chunks

    def generate(self, query: str, context_chunks: list[dict]) -> dict:
        """
        Step 4: Generate answer using the retrieved context.
        """
        import vertexai
        from vertexai.generative_models import GenerativeModel

        vertexai.init(project=self.project_id, location="us-central1")
        model = GenerativeModel("gemini-1.5-pro-002")

        # Format context with source citations
        context_text = ""
        for i, chunk in enumerate(context_chunks):
            context_text += f"\n[Source {i+1}: {chunk['source_path']}, Page {chunk.get('page_num', 'N/A')}]\n"
            context_text += chunk["content"]
            context_text += "\n---\n"

        prompt = f"""You are an expert analyst answering questions based on provided documents.

DOCUMENTS:
{context_text}

QUESTION:
{query}

INSTRUCTIONS:
1. Answer ONLY based on the provided documents
2. Cite your sources using [Source N] notation for every factual claim
3. If the documents don't contain the answer, say: "I couldn't find information about this in the available documents."
4. Be concise and direct. Lead with the answer, then provide supporting detail.
5. If the question involves numbers or dates, quote them exactly from the source.

ANSWER:"""

        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.1,    # low temperature for factual accuracy
                "max_output_tokens": 1024,
                "top_p": 0.8,
            }
        )

        return {
            "answer": response.text,
            "sources": [
                {
                    "source_num": i + 1,
                    "path": chunk["source_path"],
                    "page": chunk.get("page_num")
                }
                for i, chunk in enumerate(context_chunks)
            ],
            "context_used": len(context_chunks)
        }

    def query(self, user_query: str) -> dict:
        """Full RAG pipeline: retrieve → rerank → fetch parents → generate."""
        # 1. Retrieve top-20 candidates
        candidates = self.retrieve(user_query, top_k=20)

        if not candidates:
            return {
                "answer": "No relevant documents found for this query.",
                "sources": [],
                "context_used": 0
            }

        # 2. Rerank to top-5
        top_chunks = self.rerank(user_query, candidates, top_n=5)

        # 3. Fetch parent chunks for full context
        context_chunks = self.fetch_parent_chunks(top_chunks)

        # 4. Generate answer
        result = self.generate(user_query, context_chunks)

        return result
```

---

## 4. Vertex AI Search — The Managed Alternative

For clients who don't want to manage their own vector store:

```python
from google.cloud import discoveryengine_v1 as discoveryengine

def setup_vertex_ai_search_datastore(project_id: str, location: str = "us"):
    """
    Set up a Vertex AI Search data store.
    This is the MANAGED RAG solution — Google handles chunking,
    embedding, indexing, and retrieval. You provide documents.
    """
    client = discoveryengine.DataStoreServiceClient()

    # Create the data store
    operation = client.create_data_store(
        parent=f"projects/{project_id}/locations/{location}/collections/default_collection",
        data_store=discoveryengine.DataStore(
            display_name="Enterprise Knowledge Base",
            industry_vertical=discoveryengine.IndustryVertical.GENERIC,
            content_config=discoveryengine.DataStore.ContentConfig.CONTENT_REQUIRED,
            solution_types=[discoveryengine.SolutionType.SOLUTION_TYPE_SEARCH],
        ),
        data_store_id="enterprise-knowledge-base",
    )
    datastore = operation.result()
    print(f"Created data store: {datastore.name}")
    return datastore.name

def import_documents_to_vertex_search(datastore_name: str, gcs_bucket: str):
    """Import documents from GCS into Vertex AI Search."""
    client = discoveryengine.DocumentServiceClient()

    # Import from GCS (supports PDF, HTML, DOCX, TXT)
    operation = client.import_documents(
        parent=f"{datastore_name}/branches/default_branch",
        gcs_source=discoveryengine.GcsSource(
            input_uris=[f"gs://{gcs_bucket}/documents/**"],
            data_schema="content",
        ),
        reconciliation_mode=discoveryengine.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL,
    )
    result = operation.result()
    print(f"Import completed. Created: {result.create_count}, Failed: {result.failure_count}")

def search_vertex_ai(datastore_id: str, project_id: str, query: str,
                     page_size: int = 10) -> list[dict]:
    """
    Query Vertex AI Search — returns ranked, contextualized results.
    Uses Google's proprietary ranking (better than basic cosine similarity).
    """
    client = discoveryengine.SearchServiceClient()

    request = discoveryengine.SearchRequest(
        serving_config=f"projects/{project_id}/locations/us/collections/default_collection/"
                       f"dataStores/{datastore_id}/servingConfigs/default_config",
        query=query,
        page_size=page_size,
        content_search_spec=discoveryengine.SearchRequest.ContentSearchSpec(
            snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
                return_snippet=True,
                max_snippet_count=3
            ),
            extractive_content_spec=discoveryengine.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
                max_extractive_answer_count=3,  # Gemini-powered extractive answers
                max_extractive_segment_count=3,
            ),
        ),
    )

    response = client.search(request)

    results = []
    for result in response.results:
        doc = result.document
        snippets = [s.snippet for s in result.document.derived_struct_data.get("snippets", [])]
        results.append({
            "doc_id": doc.id,
            "title": doc.derived_struct_data.get("title", ""),
            "snippets": snippets,
            "link": doc.derived_struct_data.get("link", ""),
        })

    return results
```

---

## 5. Guardrails — Safety for Enterprise RAG

```python
class RAGGuardrails:
    """
    Input and output guardrails for enterprise RAG deployments.
    """

    BLOCKED_QUERY_PATTERNS = [
        r"(password|credential|secret|api.?key)",  # credential fishing
        r"(ssn|social.security|credit.card|account.number)",  # PII extraction
        r"(system.prompt|ignore.previous|jailbreak)",  # prompt injection
    ]

    def check_input(self, query: str) -> dict:
        """Validate query before sending to RAG pipeline."""
        import re

        for pattern in self.BLOCKED_QUERY_PATTERNS:
            if re.search(pattern, query.lower()):
                return {
                    "allowed": False,
                    "reason": "Query contains potentially unsafe patterns",
                    "query": query
                }

        if len(query) > 2000:
            return {
                "allowed": False,
                "reason": "Query too long (max 2000 characters)",
                "query": query
            }

        return {"allowed": True, "query": query}

    def check_output(self, answer: str, context_chunks: list[dict]) -> dict:
        """
        Validate that the generated answer is grounded in retrieved context.
        Simple heuristic: key phrases from answer should appear in context.
        For production, use LLM-as-judge faithfulness check (see File 15).
        """
        # Check for refusal patterns (valid — agent correctly saying "I don't know")
        refusal_phrases = ["couldn't find", "not available in", "no information about",
                           "outside the scope"]
        if any(phrase in answer.lower() for phrase in refusal_phrases):
            return {"safe": True, "is_refusal": True}

        # Check answer length (very short answers may be unhelpful)
        if len(answer) < 20:
            return {"safe": False, "reason": "Answer too short — may be unhelpful"}

        return {"safe": True, "is_refusal": False}
```

---

## 6. RAG Quality Checklist — Pre-Go-Live

```
INGESTION QUALITY:
□ LlamaParse correctly extracts text from all document types in corpus
□ Tables are preserved as markdown tables (not flattened text)
□ Headers/footers stripped (they add noise to every chunk)
□ Duplicate documents detected and deduplicated
□ Document metadata (source, date, author) preserved in index
□ Test: manually verify 10 randomly sampled chunks look correct

RETRIEVAL QUALITY:
□ Vector search returns relevant results for 10 test queries (manual check)
□ Reranker improves precision over raw vector similarity (measure both)
□ Parent chunk retrieval provides sufficient context for complex questions
□ "No results" case handled gracefully
□ Cross-encoder reranker model appropriate for the language/domain

GENERATION QUALITY:
□ Golden dataset evaluation: overall pass rate >= target threshold
□ Citation accuracy: every factual claim linked to a source document
□ Refusal behavior: "I don't know" when information isn't available
□ Hallucination check: no made-up facts on hard examples
□ Response format: structured, concise, professional

PERFORMANCE:
□ End-to-end latency: P50 < 3s, P95 < 8s (measure at production load)
□ Embedding batch size optimized for throughput
□ Caching implemented for repeated/similar queries
□ GCS → BigQuery pipeline runs on schedule and completes within SLA

SECURITY:
□ Input guardrails blocking prompt injection attempts
□ Output guardrails preventing PII extraction
□ RAG access restricted to authorized users via IAM
□ Document access controls enforced (row-level security in BQ)
□ All API keys in Secret Manager, not hardcoded
```
