"""
Production-oriented LangGraph integration patterns.

The client below is intentionally self-contained and uses mocked model responses so
the file can run without external services. Replace ``_infer_once`` and
``stream_infer`` internals with the real SDK or HTTP client calls in production.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Iterator, Mapping, Optional, Protocol


DEFAULT_ENDPOINT = "https://api.langgraph.example"
DEFAULT_MAX_INPUT_CHARS = 5_000
DEFAULT_MAX_TOKENS = 256
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_VECTOR_DIMENSIONS = 16
SYSTEM_PROMPT = "You are an expert AI Architect. Produce concise, traceable answers."

logger = logging.getLogger(__name__)


class LangGraphError(Exception):
    """Base exception for LangGraph integration failures."""


class InputValidationError(ValueError, LangGraphError):
    """Raised when caller input does not satisfy the public contract."""


class InferenceError(LangGraphError):
    """Raised when an inference request fails after retry handling."""


class BatchClosedError(LangGraphError):
    """Raised when work is submitted after the batcher has been closed."""


@dataclass(frozen=True)
class LangGraphConfig:
    """Configuration for a model client instance."""

    api_key: str
    endpoint: str = DEFAULT_ENDPOINT
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_retries: int = 2
    stream_delay_seconds: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "api_key", safe_input(self.api_key, field_name="api_key", max_len=1_000))
        object.__setattr__(
            self,
            "endpoint",
            safe_input(self.endpoint, field_name="endpoint", max_len=2_000),
        )
        object.__setattr__(
            self,
            "timeout_seconds",
            _validate_positive_float(self.timeout_seconds, "timeout_seconds"),
        )
        object.__setattr__(
            self,
            "max_retries",
            _validate_non_negative_int(self.max_retries, "max_retries"),
        )
        object.__setattr__(
            self,
            "stream_delay_seconds",
            _validate_non_negative_float(self.stream_delay_seconds, "stream_delay_seconds"),
        )

    @classmethod
    def from_env(cls) -> "LangGraphConfig":
        api_key = os.getenv("LANGGRAPH_API_KEY")
        if not api_key:
            raise InputValidationError("LANGGRAPH_API_KEY is required")

        return cls(
            api_key=api_key,
            endpoint=os.getenv("LANGGRAPH_ENDPOINT", DEFAULT_ENDPOINT),
            timeout_seconds=_parse_float_env("LANGGRAPH_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS),
            max_retries=_parse_int_env("LANGGRAPH_MAX_RETRIES", 2),
        )


@dataclass(frozen=True)
class InferenceMeta:
    """Metadata returned with every model response."""

    latency_ms: float
    tokens: int
    model: str = "mock-langgraph"
    retries: int = 0


@dataclass(frozen=True)
class InferenceResponse:
    """Typed response shape for synchronous inference."""

    output: str
    meta: InferenceMeta

    def as_dict(self) -> dict[str, Any]:
        return {"output": self.output, "meta": self.meta.__dict__}


@dataclass(frozen=True)
class Document:
    """Single document stored in the example vector store."""

    doc_id: str
    text: str
    embedding: tuple[float, ...]


class ModelClient(Protocol):
    """Small protocol used by examples and orchestration helpers."""

    def infer(
        self,
        prompt: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = 0.0,
    ) -> InferenceResponse:
        ...

    def stream_infer(self, prompt: str, chunk_size: int = 16) -> Iterator[str]:
        ...

    def embed(self, texts: Iterable[str]) -> list[list[float]]:
        ...


class LangGraphClient:
    """Thin, validated client wrapper around a LangGraph-compatible model API."""

    def __init__(
        self,
        api_key: str,
        endpoint: str = DEFAULT_ENDPOINT,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = 2,
        stream_delay_seconds: float = 0.0,
        log: Optional[logging.Logger] = None,
    ) -> None:
        self.config = LangGraphConfig(
            api_key=safe_input(api_key, field_name="api_key", max_len=1_000),
            endpoint=safe_input(endpoint, field_name="endpoint", max_len=2_000),
            timeout_seconds=_validate_positive_float(timeout_seconds, "timeout_seconds"),
            max_retries=_validate_non_negative_int(max_retries, "max_retries"),
            stream_delay_seconds=_validate_non_negative_float(
                stream_delay_seconds,
                "stream_delay_seconds",
            ),
        )
        self._logger = log or logger

    @classmethod
    def from_config(cls, config: LangGraphConfig) -> "LangGraphClient":
        return cls(
            api_key=config.api_key,
            endpoint=config.endpoint,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
            stream_delay_seconds=config.stream_delay_seconds,
        )

    def infer(
        self,
        prompt: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = 0.0,
    ) -> InferenceResponse:
        prompt = safe_input(prompt, field_name="prompt")
        max_tokens = _validate_positive_int(max_tokens, "max_tokens")
        temperature = _validate_temperature(temperature)

        last_error: Optional[Exception] = None
        for attempt in range(self.config.max_retries + 1):
            started = time.perf_counter()
            try:
                response = self._infer_once(prompt, max_tokens=max_tokens, temperature=temperature)
                latency_ms = (time.perf_counter() - started) * 1_000
                result = InferenceResponse(
                    output=response.output,
                    meta=InferenceMeta(
                        latency_ms=round(latency_ms, 3),
                        tokens=response.meta.tokens,
                        model=response.meta.model,
                        retries=attempt,
                    ),
                )
                self._logger.info(
                    "langgraph.infer.completed",
                    extra={
                        "latency_ms": result.meta.latency_ms,
                        "tokens": result.meta.tokens,
                        "retries": attempt,
                    },
                )
                return result
            except Exception as exc:  # Real clients should narrow this to SDK/network errors.
                last_error = exc
                self._logger.warning(
                    "langgraph.infer.retry",
                    extra={"attempt": attempt + 1, "max_retries": self.config.max_retries},
                    exc_info=True,
                )
                if attempt >= self.config.max_retries:
                    break
                time.sleep(_retry_delay(attempt))

        raise InferenceError("Inference failed after retry handling") from last_error

    def stream_infer(self, prompt: str, chunk_size: int = 16) -> Iterator[str]:
        prompt = safe_input(prompt, field_name="prompt")
        chunk_size = _validate_positive_int(chunk_size, "chunk_size")

        text = f"[streamed response for prompt: {prompt[:60]!r}]"
        for start in range(0, len(text), chunk_size):
            if self.config.stream_delay_seconds:
                time.sleep(self.config.stream_delay_seconds)
            yield text[start : start + chunk_size]

    def embed(self, texts: Iterable[str]) -> list[list[float]]:
        normalized_texts = [safe_input(text, field_name="text") for text in texts]
        return [_deterministic_embedding(text) for text in normalized_texts]

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "endpoint": self.config.endpoint,
            "version": "mock-1.0",
        }

    def _infer_once(self, prompt: str, *, max_tokens: int, temperature: float) -> InferenceResponse:
        del temperature  # The mock response is deterministic; real clients should pass this through.
        estimated_tokens = min(max(len(prompt) // 4 + 10, 1), max_tokens)
        return InferenceResponse(
            output=f"[mocked response for prompt starting: {prompt[:40]!r}]",
            meta=InferenceMeta(latency_ms=0.0, tokens=estimated_tokens),
        )


def safe_input(
    text: str,
    max_len: int = DEFAULT_MAX_INPUT_CHARS,
    *,
    field_name: str = "input",
) -> str:
    if not isinstance(text, str):
        raise InputValidationError(f"{field_name} must be a string")

    cleaned = text.strip()
    if not cleaned:
        raise InputValidationError(f"{field_name} must be a non-empty string")

    if len(cleaned) > max_len:
        raise InputValidationError(f"{field_name} is too long ({len(cleaned)} > {max_len})")

    return cleaned


def template_chain(prompt_vars: Mapping[str, str]) -> str:
    required_keys = {"title", "context", "question"}
    missing = required_keys.difference(prompt_vars)
    if missing:
        raise InputValidationError(f"Missing prompt template keys: {', '.join(sorted(missing))}")

    title = safe_input(prompt_vars["title"], field_name="title")
    context = safe_input(prompt_vars["context"], field_name="context")
    question = safe_input(prompt_vars["question"], field_name="question")

    return (
        f"{SYSTEM_PROMPT}\n"
        "Constraints:\n"
        "- Provide bullet list insights\n"
        "- Limit to 200 words\n\n"
        f"Input:\nTitle: {title}\nContext: {context}\nQuestion: {question}\n"
    )


class InMemoryVectorStore:
    """Small deterministic vector store for examples and tests."""

    def __init__(self) -> None:
        self._docs: list[Document] = []

    def add(self, doc_id: str, text: str, embedding: Iterable[float]) -> None:
        embedding_tuple = tuple(float(value) for value in embedding)
        if not embedding_tuple:
            raise InputValidationError("embedding must not be empty")

        self._docs.append(
            Document(
                doc_id=safe_input(doc_id, field_name="doc_id", max_len=300),
                text=safe_input(text, field_name="text"),
                embedding=embedding_tuple,
            )
        )

    def query(self, embedding: Iterable[float], top_k: int = 3) -> list[str]:
        top_k = _validate_positive_int(top_k, "top_k")
        query_embedding = tuple(float(value) for value in embedding)
        if not query_embedding:
            raise InputValidationError("embedding must not be empty")

        scored = [
            (_cosine_similarity(query_embedding, doc.embedding), doc.text)
            for doc in self._docs
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [text for _, text in scored[:top_k]]

    def __len__(self) -> int:
        return len(self._docs)


class BatchFuture:
    """Minimal future abstraction for batch submissions."""

    def __init__(self) -> None:
        self._queue: queue.Queue[InferenceResponse | BaseException] = queue.Queue(maxsize=1)

    def set_result(self, result: InferenceResponse) -> None:
        self._queue.put(result)

    def set_exception(self, error: BaseException) -> None:
        self._queue.put(error)

    def result(self, timeout: Optional[float] = None) -> InferenceResponse:
        try:
            item = self._queue.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError("Timed out while waiting for batch result") from exc

        if isinstance(item, BaseException):
            raise item
        return item


@dataclass(frozen=True)
class BatchItem:
    prompt: str
    future: BatchFuture


class SimpleBatcher:
    """Threaded batcher with bounded queueing and graceful shutdown."""

    def __init__(
        self,
        client: ModelClient,
        batch_size: int = 8,
        interval: float = 0.05,
        max_queue_size: int = 1_000,
    ) -> None:
        self.client = client
        self.batch_size = _validate_positive_int(batch_size, "batch_size")
        self.interval = _validate_positive_float(interval, "interval")
        self._queue: queue.Queue[BatchItem] = queue.Queue(
            maxsize=_validate_positive_int(max_queue_size, "max_queue_size")
        )
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, name="langgraph-batcher", daemon=True)
        self._thread.start()

    def submit(self, prompt: str, timeout: Optional[float] = None) -> BatchFuture:
        if self._stop_event.is_set():
            raise BatchClosedError("Batcher is closed")

        future = BatchFuture()
        item = BatchItem(prompt=safe_input(prompt, field_name="prompt"), future=future)
        try:
            self._queue.put(item, timeout=timeout)
        except queue.Full as exc:
            raise TimeoutError("Timed out while queueing batch request") from exc
        return future

    def close(self, timeout: Optional[float] = 5.0) -> None:
        self._stop_event.set()
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            raise TimeoutError("Timed out while stopping batcher thread")

    def __enter__(self) -> "SimpleBatcher":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def _run(self) -> None:
        while not self._stop_event.is_set() or not self._queue.empty():
            batch = self._collect_batch()
            if not batch:
                continue

            for item in batch:
                try:
                    item.future.set_result(self.client.infer(item.prompt))
                except Exception as exc:
                    item.future.set_exception(exc)

    def _collect_batch(self) -> list[BatchItem]:
        batch: list[BatchItem] = []
        try:
            batch.append(self._queue.get(timeout=self.interval))
        except queue.Empty:
            return batch

        deadline = time.monotonic() + self.interval
        while len(batch) < self.batch_size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                batch.append(self._queue.get(timeout=remaining))
            except queue.Empty:
                break
        return batch


def example_minimal(api_key: str) -> str:
    client = LangGraphClient(api_key)
    response = client.infer("Summarize the following product requirements: ...")
    logger.info("minimal_infer", extra={"tokens": response.meta.tokens})
    return response.output


def example_prompt_templates(api_key: str) -> str:
    client = LangGraphClient(api_key)
    prompt = template_chain(
        {
            "title": "Realtime Price Engine",
            "context": "low latency\nmulti-tenant",
            "question": "How to ensure correctness under high load?",
        }
    )
    response = client.infer(prompt, temperature=0.1)
    logger.info("template_infer", extra={"tokens": response.meta.tokens})
    return response.output


def example_rag(api_key: str) -> str:
    client = LangGraphClient(api_key)
    store = InMemoryVectorStore()

    docs = {
        "d1": "Latency budgets and SLA design.",
        "d2": "Circuit breaker patterns.",
        "d3": "Feature flags and canary rollouts.",
    }
    for (doc_id, text), embedding in zip(docs.items(), client.embed(docs.values())):
        store.add(doc_id, text, embedding)

    query = "How to design SLAs for a real-time inference API?"
    hits = store.query(client.embed([query])[0], top_k=2)
    synth_prompt = f"{SYSTEM_PROMPT}\nUse the following docs:\n{chr(10).join(hits)}\nAnswer: {query}"
    response = client.infer(synth_prompt)
    logger.info("rag_infer", extra={"retrieved_docs": len(hits), "tokens": response.meta.tokens})
    return response.output


def example_streaming(
    api_key: str,
    prompt: str,
    on_chunk: Optional[Callable[[str], None]] = None,
) -> str:
    client = LangGraphClient(api_key)
    chunks: list[str] = []

    for chunk in client.stream_infer(prompt, chunk_size=8):
        chunks.append(chunk)
        if on_chunk is not None:
            on_chunk(chunk)

    full_response = "".join(chunks)
    logger.info("stream_complete", extra={"length": len(full_response)})
    return full_response


def example_batching(api_key: str) -> list[InferenceResponse]:
    client = LangGraphClient(api_key)
    with SimpleBatcher(client, batch_size=4, interval=0.02) as batcher:
        futures = [batcher.submit(f"batch prompt {index}") for index in range(6)]
        results = [future.result(timeout=2) for future in futures]

    logger.info("batch_results", extra={"count": len(results)})
    return results


def example_observability(api_key: str) -> InferenceResponse:
    client = LangGraphClient(api_key)
    response = client.infer("Check observability patterns")
    logger.info(
        "metric.langgraph.request",
        extra={"latency_ms": response.meta.latency_ms, "tokens": response.meta.tokens},
    )
    return response


def example_secure_infer(api_key: str, user_role: str, user_input: str) -> InferenceResponse:
    safe_text = safe_input(user_input, field_name="user_input")
    safe_role = safe_input(user_role, field_name="user_role", max_len=100)

    if safe_role != "model_admin" and len(safe_text) > 1_000:
        raise PermissionError("Insufficient privileges for long content")

    return LangGraphClient(api_key).infer(safe_text)


def orchestrate_models(
    primary: ModelClient,
    fallback: ModelClient,
    prompt: str,
) -> dict[str, InferenceResponse | str]:
    try:
        response = primary.infer(prompt)
        if response.meta.tokens < 5:
            raise InferenceError("Primary response did not meet the confidence threshold")
        return {"model": "primary", "response": response}
    except LangGraphError:
        logger.warning("fallback_triggered", exc_info=True)
        return {"model": "fallback", "response": fallback.infer(prompt)}


def canary_test_and_promote(
    primary: ModelClient,
    canary: ModelClient,
    test_prompts: list[str],
    threshold: float = 0.8,
) -> dict[str, bool | float]:
    if not test_prompts:
        raise InputValidationError("test_prompts must not be empty")

    threshold = _validate_threshold(threshold)

    def score(response: InferenceResponse) -> float:
        return min(1.0, len(response.output) / 100.0)

    primary_scores = [score(primary.infer(prompt)) for prompt in test_prompts]
    canary_scores = [score(canary.infer(prompt)) for prompt in test_prompts]
    primary_avg = sum(primary_scores) / len(primary_scores)
    canary_avg = sum(canary_scores) / len(canary_scores)

    logger.info(
        "canary_scores",
        extra={"primary_avg": primary_avg, "canary_avg": canary_avg},
    )
    return {
        "promote_canary": canary_avg >= max(threshold, primary_avg),
        "primary_avg": primary_avg,
        "canary_avg": canary_avg,
    }


def demo_all(api_key: str) -> None:
    print("--- minimal ---")
    print(example_minimal(api_key))
    print("--- template ---")
    print(example_prompt_templates(api_key))
    print("--- rag ---")
    print(example_rag(api_key))
    print("--- streaming ---")
    print(example_streaming(api_key, "streaming demo prompt"))
    print("--- batching ---")
    print([result.as_dict() for result in example_batching(api_key)])
    print("--- observability ---")
    print(example_observability(api_key).as_dict())


def _deterministic_embedding(text: str, dimensions: int = DEFAULT_VECTOR_DIMENSIONS) -> list[float]:
    vector = [0.0] * dimensions
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = digest[0] % dimensions
        vector[index] += 1.0 + digest[1] / 255.0

    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


def _cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise InputValidationError("embedding dimensions must match")

    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0

    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def _retry_delay(attempt: int) -> float:
    return min(0.1 * (2**attempt), 2.0)


def _parse_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return _validate_positive_float(float(raw), name)
    except ValueError as exc:
        raise InputValidationError(f"{name} must be a valid number") from exc


def _parse_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return _validate_non_negative_int(int(raw), name)
    except ValueError as exc:
        raise InputValidationError(f"{name} must be a valid integer") from exc


def _validate_temperature(value: float) -> float:
    if not isinstance(value, (int, float)):
        raise InputValidationError("temperature must be numeric")
    numeric = float(value)
    if not 0.0 <= numeric <= 2.0:
        raise InputValidationError("temperature must be between 0.0 and 2.0")
    return numeric


def _validate_threshold(value: float) -> float:
    if not isinstance(value, (int, float)):
        raise InputValidationError("threshold must be numeric")
    numeric = float(value)
    if not 0.0 <= numeric <= 1.0:
        raise InputValidationError("threshold must be between 0.0 and 1.0")
    return numeric


def _validate_positive_int(value: int, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise InputValidationError(f"{field_name} must be a positive integer")
    return value


def _validate_non_negative_int(value: int, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise InputValidationError(f"{field_name} must be a non-negative integer")
    return value


def _validate_positive_float(value: float, field_name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise InputValidationError(f"{field_name} must be a positive number")
    return float(value)


def _validate_non_negative_float(value: float, field_name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise InputValidationError(f"{field_name} must be a non-negative number")
    return float(value)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    demo_all(os.getenv("LANGGRAPH_API_KEY", "mock-key"))
