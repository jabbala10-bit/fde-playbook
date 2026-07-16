"""Output guardrails: citation enforcement + a heuristic faithfulness check.

Operationalizes reference-architecture.md's OUTPUT GUARDRAILS stage
("validation, policy check, confidence threshold") and notes/18's
requirement that "every claim must have [source: doc, clause]."
"""

from __future__ import annotations

from typing import Dict, List

from .ingest import Chunk


def enforce_citations(answer: str, sources: List[Chunk]) -> str:
    """Appends a citation block naming every source chunk's document.

    A production system would push this further — forcing the generator to
    emit inline [source: doc, clause] tags per claim rather than one block
    at the end — but even this coarse version makes "which documents backed
    this answer" auditable, which is the actual requirement.
    """
    if not sources:
        return answer
    seen = []
    for chunk in sources:
        if chunk.doc_id not in seen:
            seen.append(chunk.doc_id)
    citations = ", ".join(f"[{doc_id}]" for doc_id in seen)
    return f"{answer}\n\nSources: {citations}"


def faithfulness_check(answer: str, sources: List[Chunk]) -> Dict[str, object]:
    """Heuristic groundedness check (local mode): what fraction of the
    answer's significant words (len > 3) appear somewhere in the retrieved
    context? Live mode would replace this with an LLM-as-judge faithfulness
    prompt — see eval-driven-development.md's LLM-as-judge section."""
    context_words = set()
    for chunk in sources:
        context_words |= {w.strip(".,") for w in chunk.text.lower().split()}
    answer_words = {w.strip(".,") for w in answer.lower().split() if len(w) > 3}
    if not answer_words:
        return {"score": 0.0, "grounded": False}
    supported = answer_words & context_words
    score = len(supported) / len(answer_words)
    return {"score": round(score, 2), "grounded": score >= 0.5}
