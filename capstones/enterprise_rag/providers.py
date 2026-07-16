"""Pluggable embedding/generation providers.

Default mode ("local") is fully offline and dependency-free: a deterministic
hashed bag-of-words embedding and a mock generator that extracts supporting
sentences from retrieved context. Mode "live" swaps the generator for a real
Claude API call — it requires `pip install -e '.[live]'` and an
ANTHROPIC_API_KEY, and is never imported unless explicitly selected, so the
default install and test suite stay fully offline.
"""

from __future__ import annotations

import hashlib
import math
import os
from typing import List, Protocol, Sequence, Tuple


class EmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str]) -> List[List[float]]: ...


class GenerationProvider(Protocol):
    def generate(self, question: str, context: str) -> str: ...


class LocalHashEmbedding:
    """Deterministic, offline embedding via hashed word buckets (unit-normalized)."""

    def __init__(self, dims: int = 64):
        self.dims = dims

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> List[float]:
        vec = [0.0] * self.dims
        for word in text.lower().split():
            idx = int(hashlib.sha1(word.encode("utf-8")).hexdigest(), 16) % self.dims
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class MockLegalGenerator:
    """Deterministic offline stand-in for an LLM: stitches the most relevant
    supporting sentences from the retrieved context. Not a real generator —
    it exists so the retrieval -> guardrails -> citation pipeline is fully
    exercisable and testable without network access."""

    def generate(self, question: str, context: str) -> str:
        sentences = [s.strip() for s in context.split(".") if s.strip()]
        if not sentences:
            return "No supporting context found for this question."
        question_words = {w.strip("?.,").lower() for w in question.split()}
        scored: List[Tuple[int, str]] = []
        for sentence in sentences:
            sentence_words = {w.strip(".,").lower() for w in sentence.split()}
            scored.append((len(question_words & sentence_words), sentence))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        best = [s for _, s in scored[:2]]
        return ". ".join(best) + "."


class AnthropicGenerator:
    """Live generation via the Claude API. Requires the 'live' extra and
    ANTHROPIC_API_KEY. Only imported/instantiated when --provider live is
    explicitly selected — see make_providers()."""

    def __init__(self, model: str = "claude-sonnet-5"):
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError(
                "AnthropicGenerator requires the 'live' extra: pip install -e '.[live]'"
            ) from exc
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("Set ANTHROPIC_API_KEY to use --provider live.")
        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def generate(self, question: str, context: str) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Answer the question using only the provided context. "
                        "If the context does not support an answer, say so.\n\n"
                        f"Context:\n{context}\n\nQuestion: {question}"
                    ),
                }
            ],
        )
        return "".join(block.text for block in response.content if hasattr(block, "text"))


def make_providers(provider: str = "local") -> Tuple[EmbeddingProvider, GenerationProvider]:
    """Factory returning (embedding_provider, generation_provider) for the given mode.

    Embeddings stay local in both modes — see capstones/enterprise_rag/README.md
    "Go live" section for why, and what a real deployment would swap in instead.
    """
    if provider == "local":
        return LocalHashEmbedding(), MockLegalGenerator()
    if provider == "live":
        return LocalHashEmbedding(), AnthropicGenerator()
    raise ValueError(f"Unknown provider: {provider!r}")
