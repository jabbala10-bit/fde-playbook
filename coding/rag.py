"""
Comprehensive RAG (Retrieval-Augmented Generation) examples ranging from simple
proof-of-concept to production-grade patterns for principal-level AI engineers
and architects. Covers: ingestion, chunking, vector stores (FAISS-like),
semantic search, hybrid retrieval, re-ranking, streaming, caching, async
batching, provenance, evaluation hooks, error handling and deployment tips.

This file is self-contained and uses lightweight dependencies where possible.
Replace placeholders (API keys, model calls) with real integrations.

Author: Generated
"""

import os
import math
import time
import json
import hashlib
import asyncio
from typing import List, Tuple, Dict, Any, Iterable

######################################################################
# Utilities
######################################################################

def sha1(text: str) -> str:
	return hashlib.sha1(text.encode('utf-8')).hexdigest()

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
	words = text.split()
	chunks = []
	i = 0
	while i < len(words):
		chunk = words[i:i+chunk_size]
		chunks.append(' '.join(chunk))
		i += chunk_size - overlap
	return chunks

######################################################################
# Mock Embedding and Model Interfaces (replace with real SDK calls)
######################################################################

def embed_texts(texts: List[str]) -> List[List[float]]:
	# Lightweight deterministic embedding placeholder (not semantic)
	# Replace with OpenAI/Anthropic/Vertex embeddings in prod.
	embeddings = []
	for t in texts:
		h = sha1(t)
		vec = [((ord(c) % 97)+1)/100.0 for c in h[:64]]
		embeddings.append(vec)
	return embeddings

def dummy_generate(prompt: str) -> str:
	# Replace with LLM generation call (e.g. OpenAI chat/completions)
	return f"[GENERATED ANSWER for prompt len={len(prompt)}]"

######################################################################
# Simple In-Memory Vector Store (FAISS-like minimal)
######################################################################

class InMemoryVectorStore:
	def __init__(self, dim: int = 64):
		self.dim = dim
		self.vectors: List[List[float]] = []
		self.metadatas: List[Dict[str,Any]] = []

	def add(self, ids: List[str], embeddings: List[List[float]], metadatas: List[Dict[str,Any]]):
		for e, m in zip(embeddings, metadatas):
			self.vectors.append(e)
			self.metadatas.append(m)

	def similarity_search(self, query_vec: List[float], k: int = 5) -> List[Tuple[float, Dict[str,Any]]]:
		scores = []
		for v, m in zip(self.vectors, self.metadatas):
			# cosine similarity approximation
			dot = sum(a*b for a,b in zip(v, query_vec))
			norm_v = math.sqrt(sum(a*a for a in v)) or 1.0
			norm_q = math.sqrt(sum(a*a for a in query_vec)) or 1.0
			sim = dot / (norm_v * norm_q)
			scores.append((sim, m))
		scores.sort(key=lambda x: x[0], reverse=True)
		return scores[:k]

######################################################################
# RAG Patterns
######################################################################

def ingest_documents(docs: Iterable[Tuple[str, str]], store: InMemoryVectorStore, chunk_size=200, overlap=40):
	# docs: iterable of (doc_id, text)
	metadatas = []
	texts = []
	ids = []
	for doc_id, text in docs:
		chunks = chunk_text(text, chunk_size, overlap)
		for i, c in enumerate(chunks):
			texts.append(c)
			ids.append(f"{doc_id}::chunk::{i}")
			metadatas.append({"doc_id": doc_id, "chunk_index": i, "text": c})
	embeddings = embed_texts(texts)
	store.add(ids, embeddings, metadatas)


def rag_qa_simple(question: str, store: InMemoryVectorStore, k: int = 4) -> str:
	q_emb = embed_texts([question])[0]
	hits = store.similarity_search(q_emb, k=k)
	context = '\n\n'.join([m['text'] for _, m in hits])
	prompt = f"Use the context to answer the question. Context:\n{context}\n\nQuestion: {question}\nAnswer:"
	return dummy_generate(prompt)

######################################################################
# Hybrid Retrieval: Lexical + Semantic
######################################################################

def lexical_score(query: str, text: str) -> float:
	q_tokens = set(query.lower().split())
	t_tokens = set(text.lower().split())
	return len(q_tokens & t_tokens) / (len(q_tokens) or 1)

def hybrid_retrieval(query: str, store: InMemoryVectorStore, k: int = 6, alpha: float = 0.6):
	q_emb = embed_texts([query])[0]
	semantic = store.similarity_search(q_emb, k=50)
	scored = []
	for sim, m in semantic:
		lex = lexical_score(query, m['text'])
		score = alpha * sim + (1-alpha) * lex
		scored.append((score, sim, lex, m))
	scored.sort(key=lambda x: x[0], reverse=True)
	return scored[:k]

######################################################################
# Reranking with Cross-Encoder (simulated)
######################################################################

def cross_encoder_rerank(query: str, candidates: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
	# Placeholder for cross-encoder; in prod use a transformer cross-encoder
	scored = []
	for m in candidates:
		# more overlap + length bonus
		score = lexical_score(query, m['text']) + 0.01*len(m['text'].split())
		scored.append((score, m))
	scored.sort(key=lambda x: x[0], reverse=True)
	return [m for _, m in scored]

######################################################################
# Streaming and Real-time Patterns (async, batching)
######################################################################

class SimpleCache:
	def __init__(self, ttl: int = 3600):
		self.ttl = ttl
		self.store: Dict[str, Tuple[float, Any]] = {}

	def get(self, key: str):
		v = self.store.get(key)
		if not v: return None
		ts, val = v
		if time.time() - ts > self.ttl:
			del self.store[key]
			return None
		return val

	def set(self, key: str, value: Any):
		self.store[key] = (time.time(), value)


async def batch_queries(queries: List[str], store: InMemoryVectorStore, batch_size: int = 8):
	results = {}
	for i in range(0, len(queries), batch_size):
		batch = queries[i:i+batch_size]
		# In prod: call batching endpoints for embeddings
		embs = embed_texts(batch)
		for q, emb in zip(batch, embs):
			hits = store.similarity_search(emb, k=4)
			results[q] = hits
		await asyncio.sleep(0)  # yield control
	return results

######################################################################
# Evaluation, Logging, Provenance and Safety
######################################################################

def provenance(answer: str, hits: List[Tuple[float, Dict[str,Any]]]) -> Dict[str,Any]:
	return {
		"answer": answer,
		"sources": [{"doc_id": m['doc_id'], "chunk_index": m['chunk_index'], "score": float(s)} for s,m in hits]
	}

def evaluate_exact_match(pred: str, gold: str) -> bool:
	return pred.strip().lower() == gold.strip().lower()

######################################################################
# Example usage / Patterns summary (to be adapted into services)
######################################################################

def demo_small():
	store = InMemoryVectorStore(dim=64)
	docs = [
		("doc1", "Acme Corp develops AI systems for supply chain optimization. It uses forecasting and RL."),
		("doc2", "Legal: Data privacy regulations include GDPR and CCPA. Consent and DPIA processes are required."),
	]
	ingest_documents(docs, store)
	q = "What privacy regulations should we consider for AI systems?"
	ans = rag_qa_simple(q, store)
	print(ans)


if __name__ == '__main__':
	demo_small()
 