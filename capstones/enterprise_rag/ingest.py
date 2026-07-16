"""Ingestion: chunk legal documents and tag each chunk with matter metadata.

Implements the "hierarchical chunking, per-matter metadata" step from
notes/18's worked "Enterprise RAG for a Legal Firm" answer, minus the
real PDF parsing (LlamaParse etc.) — the chunking/tagging mechanics are the
same regardless of what produced the source text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Chunk:
    chunk_id: str
    matter_id: str
    doc_id: str
    text: str
    metadata: Dict[str, str] = field(default_factory=dict)


def chunk_text(text: str, chunk_size: int = 120, overlap: int = 20) -> List[str]:
    if overlap >= chunk_size:
        raise ValueError(f"overlap ({overlap}) must be smaller than chunk_size ({chunk_size})")
    words = text.split()
    chunks: List[str] = []
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i : i + chunk_size]))
        i += chunk_size - overlap
    return chunks


def ingest_document(
    doc_id: str, matter_id: str, text: str, chunk_size: int = 60, overlap: int = 10
) -> List[Chunk]:
    return [
        Chunk(chunk_id=f"{doc_id}::{i}", matter_id=matter_id, doc_id=doc_id, text=piece)
        for i, piece in enumerate(chunk_text(text, chunk_size, overlap))
    ]


def ingest_corpus(documents: List[dict], chunk_size: int = 60, overlap: int = 10) -> List[Chunk]:
    """documents: list of {"doc_id", "matter_id", "text"} — see data/documents.json."""
    chunks: List[Chunk] = []
    for doc in documents:
        chunks.extend(ingest_document(doc["doc_id"], doc["matter_id"], doc["text"], chunk_size, overlap))
    return chunks
