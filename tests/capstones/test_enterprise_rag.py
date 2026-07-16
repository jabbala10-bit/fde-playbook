"""Contract tests for Capstone 1 (Enterprise RAG). All local/offline — no
network calls, safe to run in CI."""

from __future__ import annotations

from capstones.enterprise_rag.eval import answer_question, build_index, run_eval
from capstones.enterprise_rag.guardrails import enforce_citations, faithfulness_check
from capstones.enterprise_rag.ingest import Chunk, chunk_text, ingest_corpus
from capstones.enterprise_rag.retrieve import retrieve


def test_chunk_text_rejects_overlap_ge_chunk_size():
    try:
        chunk_text("a b c d e", chunk_size=3, overlap=3)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError when overlap >= chunk_size")


def test_ingest_corpus_tags_matter_id():
    docs = [{"doc_id": "d1", "matter_id": "matter-101", "text": "word " * 30}]
    chunks = ingest_corpus(docs, chunk_size=10, overlap=2)
    assert chunks
    assert all(c.matter_id == "matter-101" for c in chunks)


def test_access_control_isolation():
    """The core requirement from notes/18: matter A can never retrieve matter B's chunks."""
    store, embedder, _ = build_index("local")
    query_embedding = embedder.embed(["breach incident forensic analysis"])[0]

    hits_202 = retrieve(query_embedding, "matter-202", store, k=10)
    hits_101 = retrieve(query_embedding, "matter-101", store, k=10)

    assert all(chunk.matter_id == "matter-202" for _, chunk in hits_202)
    assert all(chunk.matter_id == "matter-101" for _, chunk in hits_101)
    # cross-matter contamination check: no matter-202 doc_ids leak into matter-101 results
    matter_202_docs = {"beta-breach-notice", "beta-incident-timeline"}
    assert not ({c.doc_id for _, c in hits_101} & matter_202_docs)


def test_answer_question_includes_citations():
    store, embedder, generator = build_index("local")
    result = answer_question(
        "What is the transaction value in the Acme Robotics merger?",
        "matter-101",
        store,
        embedder,
        generator,
    )
    assert "Sources:" in result["answer"]
    assert result["source_doc_ids"]


def test_enforce_citations_no_sources_is_passthrough():
    assert enforce_citations("plain answer", []) == "plain answer"


def test_faithfulness_check_empty_answer():
    result = faithfulness_check("", [])
    assert result["grounded"] is False


def test_run_eval_smoke():
    report = run_eval("local")
    assert report["n"] == 9
    assert 0.0 <= report["retrieval_recall_at_k"] <= 1.0
    assert 0.0 <= report["faithfulness_rate"] <= 1.0
    # baseline (no-op rerank, mock generator) should still find the right doc most of the time
    assert report["retrieval_recall_at_k"] >= 0.6
