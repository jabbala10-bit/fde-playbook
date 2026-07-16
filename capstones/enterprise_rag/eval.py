"""Index building, question answering, and golden-set evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

from .guardrails import enforce_citations, faithfulness_check
from .ingest import ingest_corpus
from .providers import EmbeddingProvider, GenerationProvider, make_providers
from .retrieve import retrieve
from .store import InMemoryVectorStore

DATA_DIR = Path(__file__).parent / "data"


def build_index(provider: str = "local") -> Tuple[InMemoryVectorStore, EmbeddingProvider, GenerationProvider]:
    documents = json.loads((DATA_DIR / "documents.json").read_text(encoding="utf-8"))
    chunks = ingest_corpus(documents)
    embedder, generator = make_providers(provider)
    store = InMemoryVectorStore()
    store.add(chunks, embedder.embed([c.text for c in chunks]))
    return store, embedder, generator


def answer_question(
    question: str,
    matter_id: str,
    store: InMemoryVectorStore,
    embedder: EmbeddingProvider,
    generator: GenerationProvider,
    k: int = 5,
) -> Dict[str, Any]:
    query_embedding = embedder.embed([question])[0]
    hits = retrieve(query_embedding, matter_id, store, k=k)
    sources = [chunk for _, chunk in hits]
    context = " ".join(c.text for c in sources)
    raw_answer = generator.generate(question, context)
    cited = enforce_citations(raw_answer, sources)
    faithfulness = faithfulness_check(raw_answer, sources)
    return {
        "answer": cited,
        "source_chunk_ids": [c.chunk_id for c in sources],
        "source_doc_ids": sorted({c.doc_id for c in sources}),
        "faithfulness": faithfulness,
    }


def run_eval(provider: str = "local") -> Dict[str, Any]:
    golden = json.loads((DATA_DIR / "golden_qa.json").read_text(encoding="utf-8"))
    store, embedder, generator = build_index(provider)

    hits, total, faithful = 0, 0, 0
    for item in golden:
        total += 1
        result = answer_question(
            item["question"], item["matter_id"], store, embedder, generator, k=item.get("k", 5)
        )
        if item["expected_doc_id"] in result["source_doc_ids"]:
            hits += 1
        if result["faithfulness"]["grounded"]:
            faithful += 1

    return {
        "provider": provider,
        "n": total,
        "retrieval_recall_at_k": round(hits / total, 2) if total else 0.0,
        "faithfulness_rate": round(faithful / total, 2) if total else 0.0,
    }
