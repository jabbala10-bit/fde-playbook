"""
Comprehensive LangChain usage examples for Principal-level AI Engineering / Architecture.

This single-file collection demonstrates patterns from simple prototyping to
production-ready practices: basic LLM usage, prompt engineering, chains,
retrieval-augmented generation (RAG) with vector stores, agents, streaming,
callbacks/monitoring, async patterns, evaluation, batching, and deployment tips.

Notes:
- Replace placeholders (API keys, endpoints, paths) with real values.
- Keep dependencies up-to-date (langchain, openai/other LLM SDKs, faiss, weaviate, etc.).
- Designed as runnable examples; many functions are illustrative and safe to run.
"""

from typing import List, Dict, Any, Optional
import asyncio
import os
import json

# Core LLM usage (sync and async)
def basic_llm_example():
	"""Simple LLM call pattern using LangChain LLM wrapper.

	Replace with the provider you use (OpenAI, Anthropic Claude, Azure, etc.).
	"""
	try:
		# Example using a generic LLM interface (pseudo-code; adapt to your provider)
		from langchain.llms import OpenAI

		llm = OpenAI(model_name="gpt-4o-mini", temperature=0.0, max_tokens=300)
		prompt = "Summarize the following text in one sentence:\n" + (
			"LangChain provides composable abstractions for building LLM applications."
		)
		resp = llm(prompt)
		print("Basic LLM response:\n", resp)
	except Exception as e:
		print("basic_llm_example skipped (missing deps) or error:", e)


async def basic_llm_example_async():
	try:
		from langchain.llms import OpenAI

		llm = OpenAI(model_name="gpt-4o-mini", temperature=0.0, max_tokens=300)
		resp = await llm.apredict("Give me three bullet points about LangChain")
		print("Async LLM response:\n", resp)
	except Exception as e:
		print("basic_llm_example_async skipped or error:", e)


# Chains and prompt templates
def chains_and_prompt_templates():
	try:
		from ai.langchain import LLMChain, PromptTemplate
		from langchain.llms import OpenAI

		template = """
		You are an expert systems architect. Given the requirement: {requirement},
		produce: 1) a short goal statement, 2) key constraints, 3) a high-level design.
		"""
		prompt = PromptTemplate(template=template, input_variables=["requirement"])
		llm = OpenAI(model_name="gpt-4o-mini", temperature=0.2)
		chain = LLMChain(llm=llm, prompt=prompt)
		out = chain.run(requirement="Real-time personalized recommendations for e-commerce")
		print("Chain output:\n", out)
	except Exception as e:
		print("chains_and_prompt_templates skipped or error:", e)


# Retrieval-Augmented Generation (RAG) pattern
def rag_with_vectorstore_example():
	try:
		from langchain.embeddings import OpenAIEmbeddings
		from langchain.vectorstores import FAISS
		from langchain.chains import RetrievalQA
		from langchain.llms import OpenAI

		docs = [
			("doc1", "Design patterns for real-time systems: partitioning, backpressure."),
			("doc2", "Monitoring and observability best practices."),
		]

		texts = [t for _, t in docs]
		embeddings = OpenAIEmbeddings()
		# Build a FAISS index in-memory (for production choose persistent store)
		vect = FAISS.from_texts(texts, embeddings)

		retriever = vect.as_retriever(search_kwargs={"k": 2})
		qa = RetrievalQA.from_chain_type(
			llm=OpenAI(model_name="gpt-4o-mini", temperature=0.0),
			chain_type="stuff",
			retriever=retriever,
		)
		answer = qa.run("How should I design monitoring for a streaming system?")
		print("RAG answer:\n", answer)
	except Exception as e:
		print("rag_with_vectorstore_example skipped or error:", e)


# Agent patterns (tooling + orchestration)
def agent_with_tools_example():
	try:
		from langchain.agents import create_openai_functions_agent
		from langchain.tools import Tool
		from langchain.llms import OpenAI

		# Define a synchronous tool that wraps an internal function
		def search_docs(query: str) -> str:
			# In production, this calls a real index or database.
			return f"Found docs for {query}: doc1, doc2"

		tools = [Tool(name="search_docs", func=search_docs, description="Search docs")]

		agent = create_openai_functions_agent(OpenAI(model_name="gpt-4o-mini"), tools)
		res = agent.run("Find design docs about backpressure and summarize them")
		print("Agent result:\n", res)
	except Exception as e:
		print("agent_with_tools_example skipped or error:", e)


# Streaming responses and callbacks for observability
def streaming_and_callbacks_example():
	try:
		from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
		from langchain.llms import OpenAI

		streaming_handler = StreamingStdOutCallbackHandler()
		llm = OpenAI(model_name="gpt-4o-mini", streaming=True, callbacks=[streaming_handler])
		# This will stream tokens to stdout
		_ = llm("Explain backpressure in under 40 words")
	except Exception as e:
		print("streaming_and_callbacks_example skipped or error:", e)


# Async batch requests & concurrency patterns
async def batch_embeddings_async(texts: List[str]):
	try:
		from langchain.embeddings import OpenAIEmbeddings

		emb = OpenAIEmbeddings()
		# Many embedding classes provide async methods; this is illustrative
		results = [emb.embed_query(t) for t in texts]
		print("Embeddings count:", len(results))
	except Exception as e:
		print("batch_embeddings_async skipped or error:", e)


# Evaluation example (simple automated eval harness)
def evaluation_example():
	try:
		# Very small evaluation harness: compare expected output to model output
		expected = "Backpressure is controlling the flow when downstream is slow."
		out = "Backpressure is a mechanism to slow producers when consumers are overwhelmed."
		# Keyword-overlap score: fraction of expected's significant words present in out
		stopwords = {"is", "a", "the", "when", "of", "to"}
		expected_words = {w.strip(".,") for w in expected.lower().split()} - stopwords
		out_words = {w.strip(".,") for w in out.lower().split()}
		overlap = expected_words & out_words
		score = len(overlap) / len(expected_words)
		print(f"Evaluation score: {score:.2f} (matched: {sorted(overlap)})")
	except Exception as e:
		print("evaluation_example skipped or error:", e)


# Production considerations: retries, backoff, rate limiting (illustrative)
def production_resilience_wrapper(callable_fn, *args, retries=3, **kwargs):
	import time
	import random

	for attempt in range(1, retries + 1):
		try:
			return callable_fn(*args, **kwargs)
		except Exception as e:
			wait = (2 ** attempt) + random.random()
			print(f"Call failed (attempt {attempt}), retrying in {wait:.1f}s: {e}")
			time.sleep(wait)
	raise RuntimeError("All retries failed")


def deployment_notes():
	notes = {
		"secrets": "Use a secrets manager (Vault, Azure KeyVault, AWS Secrets Manager).",
		"monitoring": "Emit traces, metrics; use structured logs and sampling.",
		"vectorstore": "Persist indexes, shard for scale, use incremental updates.",
		"cost": "Cache responses, use smaller models for simple tasks.",
	}
	print("Deployment notes:\n", json.dumps(notes, indent=2))


def main():
	print("=== Basic LLM ===")
	basic_llm_example()
	print("=== Chains & Prompts ===")
	chains_and_prompt_templates()
	print("=== RAG / VectorStore ===")
	rag_with_vectorstore_example()
	print("=== Agents ===")
	agent_with_tools_example()
	print("=== Streaming ===")
	streaming_and_callbacks_example()
	print("=== Evaluation ===")
	evaluation_example()
	print("=== Deployment ===")
	deployment_notes()


if __name__ == "__main__":
	# Run sync demos and key async demos
	main()
	asyncio.run(basic_llm_example_async())
	asyncio.run(batch_embeddings_async(["hello world", "langchain patterns"]))

