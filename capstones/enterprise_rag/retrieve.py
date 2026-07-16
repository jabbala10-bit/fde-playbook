"""Retrieval with per-matter access control and a rerank exercise seam."""

from __future__ import annotations

from typing import List, Tuple

from .ingest import Chunk
from .store import InMemoryVectorStore


def retrieve(
    query_embedding: List[float], matter_id: str, store: InMemoryVectorStore, k: int = 8
) -> List[Tuple[float, Chunk]]:
    """Row-level-security retrieval: only ever returns chunks tagged with matter_id."""
    candidates = store.search(query_embedding, matter_id=matter_id, k=k)
    return rerank(candidates)


def rerank(candidates: List[Tuple[float, Chunk]]) -> List[Tuple[float, Chunk]]:
    """CAPSTONE EXERCISE — this is currently a no-op (identity) passthrough.

    notes/18's worked answer calls for a cross-encoder reranker between
    vector search and generation ("ms-marco or Cohere Rerank"). Implement
    one here — even a cheap lexical-overlap boost beats identity — then
    re-run `python -m capstones.enterprise_rag eval` and compare
    retrieval_recall_at_k / faithfulness_rate to the baseline in this
    package's README.

    Contract to preserve: same length list in and out, sorted descending by
    score, and it must never introduce a chunk from a different matter than
    what was passed in (access control is enforced upstream in
    InMemoryVectorStore.search — don't undo it here).
    """
    return candidates
