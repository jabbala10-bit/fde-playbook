"""Vector store backends.

InMemoryVectorStore is the default (local mode) and enforces per-matter
access control (row-level security) directly in `search` — the same
requirement notes/18's worked answer calls out for the legal-firm scenario:
"Lawyer on Case XYZ can only retrieve chunks from Case XYZ docs."
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

from .ingest import Chunk


@dataclass
class VectorRecord:
    chunk: Chunk
    embedding: List[float]


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._records: List[VectorRecord] = []

    def __len__(self) -> int:
        return len(self._records)

    def add(self, chunks: List[Chunk], embeddings: List[List[float]]) -> None:
        for chunk, emb in zip(chunks, embeddings):
            self._records.append(VectorRecord(chunk, emb))

    def search(self, query_embedding: List[float], matter_id: str, k: int = 5) -> List[Tuple[float, Chunk]]:
        """Metadata-filtered similarity search. `matter_id` is a hard filter,
        not a ranking signal — a record for a different matter is never
        eligible to be returned, regardless of similarity score."""
        scored = [
            (_cosine(query_embedding, record.embedding), record.chunk)
            for record in self._records
            if record.chunk.matter_id == matter_id
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return scored[:k]


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


class BigQueryVectorStore:
    """Optional live backend for the "go live" stretch goal. Requires
    `pip install -e '.[live]'` and GCP credentials. The query methods are
    intentionally left as an exercise — wire them to a
    VECTOR_SEARCH-backed table per notes/09_bigquery_data_architecture.md."""

    def __init__(self, dataset: str, table: str = "rag_chunks"):
        try:
            from google.cloud import bigquery
        except ImportError as exc:
            raise RuntimeError(
                "BigQueryVectorStore requires the 'live' extra: pip install -e '.[live]'"
            ) from exc
        self.dataset = dataset
        self.table = table
        self._client = bigquery.Client()

    def add(self, chunks: List[Chunk], embeddings: List[List[float]]) -> None:
        raise NotImplementedError(
            "Stretch goal: INSERT chunks+embeddings into a BigQuery table with a "
            "VECTOR column, per notes/09_bigquery_data_architecture.md."
        )

    def search(self, query_embedding: List[float], matter_id: str, k: int = 5) -> List[Tuple[float, Chunk]]:
        raise NotImplementedError(
            "Stretch goal: run VECTOR_SEARCH filtered by matter_id, per "
            "notes/09_bigquery_data_architecture.md."
        )
