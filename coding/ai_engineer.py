"""
Principal AI Engineering and Architecture Coding Examples
=========================================================

This module is a broad AI engineering reference for building systems that solve
complex business and real-time problems. It is intentionally broader than a
single modeling file: it covers data contracts, prompts, embeddings, RAG,
agents, evaluation, safety, serving, observability, governance, and enterprise
architecture patterns.

Design principles:
    - Start simple and readable for SME/business alignment.
    - Progress toward production-grade engineering patterns.
    - Keep optional dependencies lazy so the file can be imported anywhere.
    - Prefer explicit boundaries: data, model, policy, evaluation, serving,
      observability, and governance are separate responsibilities.

Optional install for richer demos:
    pip install numpy scikit-learn pydantic fastapi

Principal-level reminder:
    AI engineering is not only model code. It is the disciplined integration of
    data quality, user experience, model behavior, cost, latency, security,
    compliance, and measurable business impact.
"""

from __future__ import annotations

import abc
import asyncio
import dataclasses
import enum
import hashlib
import importlib
import json
import logging
import math
import queue
import random
import re
import statistics
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, Iterator, List, Optional, Protocol, Sequence, Tuple


# =============================================================================
# 0. SHARED UTILITIES
# =============================================================================

LOGGER = logging.getLogger("principal_ai_engineer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def optional_import(module_name: str) -> Any:
    """Import an optional package. Return None when unavailable."""
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


def require(module_name: str) -> Any:
    """Import a required package with a clear install instruction."""
    module = optional_import(module_name)
    if module is None:
        raise ImportError(f"Install optional dependency first: pip install {module_name}")
    return module


def now_ms() -> int:
    return int(time.time() * 1000)


def stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def timed(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for simple latency instrumentation."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                LOGGER.info("%s took %.3fms", name, (time.perf_counter() - start) * 1000)

        return wrapper

    return decorator


def normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9_]+", normalize_text(text))


# =============================================================================
# 1. SME-LEVEL AI CONCEPTS AND PROBLEM FRAMING
# =============================================================================

class AIProblemType(str, enum.Enum):
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    RANKING = "ranking"
    RECOMMENDATION = "recommendation"
    FORECASTING = "forecasting"
    ANOMALY_DETECTION = "anomaly_detection"
    SEARCH = "search"
    RAG = "retrieval_augmented_generation"
    AGENTIC_WORKFLOW = "agentic_workflow"
    DOCUMENT_AUTOMATION = "document_automation"
    MULTIMODAL = "multimodal"


@dataclass(frozen=True)
class BusinessProblem:
    name: str
    problem_type: AIProblemType
    users: List[str]
    business_kpi: str
    decision_latency_ms: int
    risk_level: str
    success_criteria: List[str]
    constraints: Dict[str, Any] = field(default_factory=dict)

    def architecture_hint(self) -> str:
        if self.problem_type == AIProblemType.RAG:
            return "Use RAG with governed sources, retrieval evaluation, citation checks, and fallback behavior."
        if self.problem_type == AIProblemType.AGENTIC_WORKFLOW:
            return "Use tools with strict schemas, policy guards, state machines, and human approval for high-impact actions."
        if self.decision_latency_ms < 200:
            return "Prefer precomputed features, compact models, caching, and synchronous low-latency serving."
        return "Batch, async, or streaming architecture may be acceptable depending on user workflow."


def sme_ai_playbook() -> Dict[str, str]:
    return {
        "start_with_business_decision": "Define what decision the AI changes and who owns the outcome.",
        "measure_baseline": "Compare AI against current process, rules, search, or classical ML.",
        "separate_model_from_policy": "The model scores; the policy decides what action is allowed.",
        "design_for_failure": "Add fallback, escalation, confidence thresholds, and graceful degradation.",
        "monitor_behavior": "Track quality, latency, cost, drift, user feedback, and business KPI movement.",
    }


# =============================================================================
# 2. DATA CONTRACTS, VALIDATION, QUALITY, AND LINEAGE
# =============================================================================

@dataclass
class FeatureSpec:
    name: str
    dtype: str
    required: bool = True
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List[Any]] = None

    def validate(self, record: Dict[str, Any]) -> List[str]:
        errors = []
        if self.name not in record:
            if self.required:
                errors.append(f"missing required feature: {self.name}")
            return errors

        value = record[self.name]
        if self.dtype == "number":
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return [f"{self.name} must be numeric"]
            if self.min_value is not None and numeric < self.min_value:
                errors.append(f"{self.name} below min {self.min_value}: {numeric}")
            if self.max_value is not None and numeric > self.max_value:
                errors.append(f"{self.name} above max {self.max_value}: {numeric}")
        elif self.dtype == "string" and not isinstance(value, str):
            errors.append(f"{self.name} must be string")
        elif self.dtype == "bool" and not isinstance(value, bool):
            errors.append(f"{self.name} must be bool")

        if self.allowed_values is not None and value not in self.allowed_values:
            errors.append(f"{self.name} not in allowed values: {value}")
        return errors


@dataclass
class DataContract:
    name: str
    version: str
    features: List[FeatureSpec]
    target: Optional[str] = None

    def validate(self, record: Dict[str, Any]) -> List[str]:
        errors = []
        for feature in self.features:
            errors.extend(feature.validate(record))
        if self.target and self.target not in record:
            errors.append(f"missing target: {self.target}")
        return errors

    def fingerprint(self) -> str:
        return stable_hash(dataclasses.asdict(self))


class DataQualityProfiler:
    """Simple data profiling for SME and engineering review."""

    def profile_records(self, records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        if not records:
            return {"rows": 0, "columns": []}

        columns = sorted({key for row in records for key in row})
        missing = {col: 0 for col in columns}
        distinct = {col: set() for col in columns}

        for row in records:
            for col in columns:
                if col not in row or row[col] is None:
                    missing[col] += 1
                else:
                    distinct[col].add(row[col])

        return {
            "rows": len(records),
            "columns": columns,
            "missing_rate": {col: missing[col] / len(records) for col in columns},
            "distinct_count": {col: len(values) for col, values in distinct.items()},
        }


@dataclass
class LineageRecord:
    dataset_name: str
    source: str
    contract_fingerprint: str
    created_at_ms: int
    row_count: int
    owner: str


class LineageStore:
    """Append-only lineage store for reproducibility and auditability."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: LineageRecord) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(dataclasses.asdict(record)) + "\n")


# =============================================================================
# 3. FEATURE ENGINEERING AND LIGHTWEIGHT MODEL BASELINES
# =============================================================================

class FeatureTransformer(abc.ABC):
    @abc.abstractmethod
    def fit(self, records: Sequence[Dict[str, Any]]) -> "FeatureTransformer":
        raise NotImplementedError

    @abc.abstractmethod
    def transform(self, records: Sequence[Dict[str, Any]]) -> List[List[float]]:
        raise NotImplementedError


class NumericFeatureTransformer(FeatureTransformer):
    """SME-friendly numeric feature transformer with mean imputation."""

    def __init__(self, feature_names: Sequence[str]):
        self.feature_names = list(feature_names)
        self.means: Dict[str, float] = {}

    def fit(self, records: Sequence[Dict[str, Any]]) -> "NumericFeatureTransformer":
        for name in self.feature_names:
            values = [float(row[name]) for row in records if name in row and row[name] is not None]
            self.means[name] = statistics.mean(values) if values else 0.0
        return self

    def transform(self, records: Sequence[Dict[str, Any]]) -> List[List[float]]:
        rows = []
        for record in records:
            rows.append([float(record.get(name, self.means[name]) or self.means[name]) for name in self.feature_names])
        return rows


class SimpleLogisticRegression:
    """From-scratch binary classifier baseline using gradient descent."""

    def __init__(self, learning_rate: float = 0.1, epochs: int = 200):
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.weights: List[float] = []
        self.bias = 0.0

    def fit(self, x: Sequence[Sequence[float]], y: Sequence[int]) -> "SimpleLogisticRegression":
        if not x:
            raise ValueError("x cannot be empty")
        n_features = len(x[0])
        self.weights = [0.0] * n_features
        self.bias = 0.0

        for _ in range(self.epochs):
            grad_w = [0.0] * n_features
            grad_b = 0.0
            for row, target in zip(x, y):
                pred = sigmoid(sum(w * v for w, v in zip(self.weights, row)) + self.bias)
                error = pred - target
                for i, value in enumerate(row):
                    grad_w[i] += error * value
                grad_b += error
            scale = 1.0 / len(x)
            self.weights = [w - self.learning_rate * grad * scale for w, grad in zip(self.weights, grad_w)]
            self.bias -= self.learning_rate * grad_b * scale
        return self

    def predict_proba(self, row: Sequence[float]) -> float:
        return sigmoid(sum(w * v for w, v in zip(self.weights, row)) + self.bias)

    def predict(self, row: Sequence[float], threshold: float = 0.5) -> int:
        return int(self.predict_proba(row) >= threshold)


def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1 / (1 + z)
    z = math.exp(x)
    return z / (1 + z)


def evaluate_binary_classifier(model: SimpleLogisticRegression, x: Sequence[Sequence[float]], y: Sequence[int]) -> Dict[str, float]:
    tp = tn = fp = fn = 0
    for row, target in zip(x, y):
        pred = model.predict(row)
        if pred == 1 and target == 1:
            tp += 1
        elif pred == 0 and target == 0:
            tn += 1
        elif pred == 1 and target == 0:
            fp += 1
        else:
            fn += 1
    total = max(tp + tn + fp + fn, 1)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    return {
        "accuracy": (tp + tn) / total,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / max(precision + recall, 1e-12),
    }


# =============================================================================
# 4. PROMPT ENGINEERING, OUTPUT CONTRACTS, AND LLM ABSTRACTIONS
# =============================================================================

@dataclass(frozen=True)
class PromptTemplate:
    name: str
    system: str
    user_template: str
    output_schema: Dict[str, Any] = field(default_factory=dict)

    def render(self, **kwargs: Any) -> List[Dict[str, str]]:
        return [
            {"role": "system", "content": self.system},
            {"role": "user", "content": self.user_template.format(**kwargs)},
        ]


class LLMClient(Protocol):
    def complete(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        ...


class RuleBasedLLMClient:
    """Local deterministic stand-in for examples and tests."""

    def complete(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        user_text = messages[-1]["content"]
        if "json" in user_text.lower():
            return json.dumps({"answer": "rule-based response", "confidence": 0.5})
        return f"Rule-based response to: {user_text[:120]}"


class OutputParser:
    """Structured output parser with defensive fallback."""

    def parse_json(self, text: str, required_keys: Sequence[str]) -> Dict[str, Any]:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return {"_parse_error": True, "raw": text}
        missing = [key for key in required_keys if key not in payload]
        if missing:
            payload["_missing_keys"] = missing
        return payload


class PromptRegistry:
    def __init__(self):
        self.templates: Dict[str, PromptTemplate] = {}

    def register(self, template: PromptTemplate) -> None:
        self.templates[template.name] = template

    def get(self, name: str) -> PromptTemplate:
        return self.templates[name]


def prompt_injection_guard(user_input: str) -> Dict[str, Any]:
    risky_patterns = [
        r"ignore previous instructions",
        r"system prompt",
        r"developer message",
        r"exfiltrate",
        r"disable safety",
        r"jailbreak",
    ]
    matches = [pattern for pattern in risky_patterns if re.search(pattern, user_input, re.IGNORECASE)]
    return {"allowed": not matches, "matches": matches}


# =============================================================================
# 5. EMBEDDINGS, VECTOR SEARCH, AND RAG
# =============================================================================

@dataclass
class Document:
    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    id: str
    document_id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


def chunk_text(document: Document, chunk_size: int = 120, overlap: int = 20) -> List[Chunk]:
    tokens = tokenize(document.text)
    chunks = []
    start = 0
    index = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        text = " ".join(tokens[start:end])
        chunk_id = f"{document.id}-{index}"
        chunks.append(Chunk(id=chunk_id, document_id=document.id, text=text, metadata=dict(document.metadata)))
        if end == len(tokens):
            break
        start = max(end - overlap, start + 1)
        index += 1
    return chunks


class HashEmbeddingModel:
    """Dependency-free embedding model for demos and tests."""

    def __init__(self, dimensions: int = 128):
        self.dimensions = dimensions

    def embed(self, text: str) -> List[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            index = int(digest[:8], 16) % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


class InMemoryVectorStore:
    def __init__(self, embedding_model: HashEmbeddingModel):
        self.embedding_model = embedding_model
        self.rows: List[Tuple[Chunk, List[float]]] = []

    def add(self, chunks: Sequence[Chunk]) -> None:
        for chunk in chunks:
            self.rows.append((chunk, self.embedding_model.embed(chunk.text)))

    def search(self, query: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Tuple[Chunk, float]]:
        query_vector = self.embedding_model.embed(query)
        results = []
        for chunk, vector in self.rows:
            if filters and any(chunk.metadata.get(k) != v for k, v in filters.items()):
                continue
            results.append((chunk, cosine_similarity(query_vector, vector)))
        return sorted(results, key=lambda item: item[1], reverse=True)[:top_k]


class RAGPipeline:
    """Retrieval augmented generation with citations and policy hooks."""

    def __init__(self, vector_store: InMemoryVectorStore, llm: LLMClient):
        self.vector_store = vector_store
        self.llm = llm

    def answer(self, question: str, top_k: int = 4) -> Dict[str, Any]:
        guard = prompt_injection_guard(question)
        if not guard["allowed"]:
            return {"answer": "Request blocked by prompt safety policy.", "blocked": True, "policy": guard}

        retrieved = self.vector_store.search(question, top_k=top_k)
        context = "\n\n".join(f"[{chunk.id}] {chunk.text}" for chunk, _ in retrieved)
        messages = [
            {"role": "system", "content": "Answer using only provided context. Cite chunk ids."},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ]
        answer = self.llm.complete(messages)
        return {
            "answer": answer,
            "blocked": False,
            "citations": [chunk.id for chunk, _ in retrieved],
            "retrieval_scores": {chunk.id: score for chunk, score in retrieved},
        }


def evaluate_retrieval(queries: Sequence[Tuple[str, str]], vector_store: InMemoryVectorStore, top_k: int = 5) -> Dict[str, float]:
    """queries are (query_text, expected_document_id)."""
    hits = 0
    reciprocal_ranks = []
    for query, expected_doc in queries:
        results = vector_store.search(query, top_k=top_k)
        rank = None
        for i, (chunk, _) in enumerate(results, start=1):
            if chunk.document_id == expected_doc:
                rank = i
                break
        if rank is not None:
            hits += 1
            reciprocal_ranks.append(1 / rank)
        else:
            reciprocal_ranks.append(0.0)
    return {
        "hit_rate": hits / max(len(queries), 1),
        "mrr": statistics.mean(reciprocal_ranks) if reciprocal_ranks else 0.0,
    }


# =============================================================================
# 6. AGENTS, TOOLS, ORCHESTRATION, AND HUMAN-IN-THE-LOOP
# =============================================================================

@dataclass
class ToolResult:
    name: str
    output: Any
    success: bool
    error: Optional[str] = None


class Tool(abc.ABC):
    name: str
    description: str

    @abc.abstractmethod
    def run(self, **kwargs: Any) -> ToolResult:
        raise NotImplementedError


class CalculatorTool(Tool):
    name = "calculator"
    description = "Safely evaluate simple arithmetic expressions."

    def run(self, **kwargs: Any) -> ToolResult:
        expression = kwargs.get("expression", "")
        if not re.fullmatch(r"[0-9+\-*/().\s]+", expression):
            return ToolResult(self.name, None, False, "unsafe expression")
        try:
            return ToolResult(self.name, eval(expression, {"__builtins__": {}}, {}), True)
        except Exception as exc:
            return ToolResult(self.name, None, False, str(exc))


class KnowledgeBaseTool(Tool):
    name = "knowledge_base_search"
    description = "Search internal documents."

    def __init__(self, vector_store: InMemoryVectorStore):
        self.vector_store = vector_store

    def run(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "")
        results = self.vector_store.search(query, top_k=int(kwargs.get("top_k", 3)))
        return ToolResult(self.name, [{"chunk_id": c.id, "text": c.text, "score": s} for c, s in results], True)


class AgentState(str, enum.Enum):
    PLAN = "plan"
    ACT = "act"
    OBSERVE = "observe"
    FINISH = "finish"
    ESCALATE = "escalate"


@dataclass
class AgentStep:
    state: AgentState
    thought: str
    action: Optional[str] = None
    observation: Optional[Any] = None


class SimpleToolAgent:
    """Small, deterministic agent pattern with strict tool routing."""

    def __init__(self, tools: Sequence[Tool], max_steps: int = 4):
        self.tools = {tool.name: tool for tool in tools}
        self.max_steps = max_steps

    def run(self, task: str) -> Dict[str, Any]:
        steps = [AgentStep(AgentState.PLAN, f"Understand task: {task}")]
        if ("calculate" in task.lower() or re.search(r"\d+\s*[+\-*/]\s*\d+", task)) and "calculator" in self.tools:
            expression = re.findall(r"[0-9+\-*/().\s]+", task)[0].strip()
            result = self.tools["calculator"].run(expression=expression)
            steps.append(AgentStep(AgentState.ACT, "Use calculator for arithmetic.", "calculator", result.output))
            return {"answer": result.output, "steps": [dataclasses.asdict(step) for step in steps]}

        if "search" in task.lower() and "knowledge_base_search" in self.tools:
            result = self.tools["knowledge_base_search"].run(query=task)
            steps.append(AgentStep(AgentState.ACT, "Use knowledge base search.", "knowledge_base_search", result.output))
            return {"answer": result.output, "steps": [dataclasses.asdict(step) for step in steps]}

        steps.append(AgentStep(AgentState.ESCALATE, "No safe deterministic route found. Ask human reviewer."))
        return {"answer": "Escalated for human review.", "steps": [dataclasses.asdict(step) for step in steps]}


class HumanApprovalGate:
    """Gate high-impact actions behind explicit approval."""

    def __init__(self, risk_threshold: str = "high"):
        self.risk_threshold = risk_threshold

    def requires_approval(self, action: Dict[str, Any]) -> bool:
        return action.get("risk") in {"high", "critical"} or action.get("moves_money", False)


# =============================================================================
# 7. EVALUATION, EXPERIMENTATION, AND QUALITY GATES
# =============================================================================

@dataclass
class EvaluationCase:
    id: str
    input: str
    expected: Any
    tags: List[str] = field(default_factory=list)


class Evaluator(abc.ABC):
    @abc.abstractmethod
    def evaluate(self, prediction: Any, expected: Any) -> float:
        raise NotImplementedError


class ExactMatchEvaluator(Evaluator):
    def evaluate(self, prediction: Any, expected: Any) -> float:
        return float(str(prediction).strip().lower() == str(expected).strip().lower())


class ContainsEvaluator(Evaluator):
    def evaluate(self, prediction: Any, expected: Any) -> float:
        return float(str(expected).lower() in str(prediction).lower())


class EvaluationRunner:
    def __init__(self, evaluator: Evaluator):
        self.evaluator = evaluator

    def run(self, cases: Sequence[EvaluationCase], predict: Callable[[str], Any]) -> Dict[str, Any]:
        rows = []
        for case in cases:
            prediction = predict(case.input)
            score = self.evaluator.evaluate(prediction, case.expected)
            rows.append({"id": case.id, "score": score, "prediction": prediction, "expected": case.expected, "tags": case.tags})
        return {
            "average_score": statistics.mean([row["score"] for row in rows]) if rows else 0.0,
            "cases": rows,
            "by_tag": self._by_tag(rows),
        }

    def _by_tag(self, rows: Sequence[Dict[str, Any]]) -> Dict[str, float]:
        scores: Dict[str, List[float]] = defaultdict(list)
        for row in rows:
            for tag in row["tags"]:
                scores[tag].append(row["score"])
        return {tag: statistics.mean(values) for tag, values in scores.items()}


class ABTestRouter:
    """Stable assignment for A/B tests or champion/challenger rollouts."""

    def __init__(self, variants: Dict[str, float]):
        if abs(sum(variants.values()) - 1.0) > 1e-6:
            raise ValueError("variant weights must sum to 1.0")
        self.variants = variants

    def assign(self, user_id: str) -> str:
        bucket = int(hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
        cumulative = 0.0
        for variant, weight in self.variants.items():
            cumulative += weight
            if bucket <= cumulative:
                return variant
        return list(self.variants)[-1]


class QualityGate:
    """Promotion gate for model/prompt releases."""

    def __init__(self, thresholds: Dict[str, float]):
        self.thresholds = thresholds

    def check(self, metrics: Dict[str, float]) -> Dict[str, Any]:
        failures = {
            metric: {"actual": metrics.get(metric), "required": required}
            for metric, required in self.thresholds.items()
            if metrics.get(metric, -math.inf) < required
        }
        return {"passed": not failures, "failures": failures}


# =============================================================================
# 8. SAFETY, SECURITY, PRIVACY, AND POLICY CONTROLS
# =============================================================================

class PiiRedactor:
    """Basic PII redactor for logs, prompts, and support workflows."""

    EMAIL = re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
    PHONE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")

    def redact(self, text: str) -> str:
        text = self.EMAIL.sub("[EMAIL]", text)
        text = self.PHONE.sub("[PHONE]", text)
        return text


class SafetyClassifier:
    """Rule-based safety classifier for examples; replace with policy service in production."""

    def __init__(self):
        self.block_patterns = [
            r"\bcredential\b",
            r"\bpassword\b",
            r"\bapi key\b",
            r"\bexfiltrate\b",
            r"\bmalware\b",
            r"\bself harm\b",
        ]

    def classify(self, text: str) -> Dict[str, Any]:
        matches = [pattern for pattern in self.block_patterns if re.search(pattern, text, re.IGNORECASE)]
        return {"allowed": not matches, "matches": matches}


class PolicyEngine:
    """Central policy decision layer. Keep this separate from model scoring."""

    def __init__(self, safety: SafetyClassifier, redactor: PiiRedactor):
        self.safety = safety
        self.redactor = redactor

    def inspect_request(self, text: str) -> Dict[str, Any]:
        safety = self.safety.classify(text)
        injection = prompt_injection_guard(text)
        return {
            "allowed": safety["allowed"] and injection["allowed"],
            "safety": safety,
            "prompt_injection": injection,
            "redacted_text": self.redactor.redact(text),
        }


class SecretScanner:
    SECRET_PATTERNS = [
        re.compile(r"sk-[A-Za-z0-9]{20,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
    ]

    def scan(self, text: str) -> Dict[str, Any]:
        findings = []
        for pattern in self.SECRET_PATTERNS:
            findings.extend(match.group(0) for match in pattern.finditer(text))
        return {"has_secret": bool(findings), "count": len(findings)}


# =============================================================================
# 9. SERVING, REAL-TIME ARCHITECTURE, CACHING, AND RESILIENCE
# =============================================================================

@dataclass
class AIRequest:
    request_id: str
    user_id: str
    input_text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIResponse:
    request_id: str
    output: Any
    model_version: str
    latency_ms: float
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TTLCache:
    def __init__(self, ttl_seconds: int = 300, max_items: int = 1024):
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self.values: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        item = self.values.get(key)
        if item is None:
            return None
        expires_at, value = item
        if time.time() > expires_at:
            self.values.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        if len(self.values) >= self.max_items:
            oldest = min(self.values.items(), key=lambda item: item[1][0])[0]
            self.values.pop(oldest, None)
        self.values[key] = (time.time() + self.ttl_seconds, value)


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_seconds: int = 30):
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self.failures = 0
        self.opened_at: Optional[float] = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if time.time() - self.opened_at > self.reset_seconds:
            self.failures = 0
            self.opened_at = None
            return True
        return False

    def success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.time()


class AIService:
    """Production-shaped request path with policy, cache, model, and audit hooks."""

    def __init__(
        self,
        model_version: str,
        llm: LLMClient,
        policy: PolicyEngine,
        cache: Optional[TTLCache] = None,
    ):
        self.model_version = model_version
        self.llm = llm
        self.policy = policy
        self.cache = cache or TTLCache()
        self.breaker = CircuitBreaker()

    def handle(self, request: AIRequest) -> AIResponse:
        start = time.perf_counter()
        inspection = self.policy.inspect_request(request.input_text)
        if not inspection["allowed"]:
            return AIResponse(
                request_id=request.request_id,
                output="Request blocked by policy.",
                model_version=self.model_version,
                latency_ms=(time.perf_counter() - start) * 1000,
                confidence=1.0,
                metadata={"policy": inspection},
            )

        cache_key = stable_hash({"model": self.model_version, "input": request.input_text})
        cached = self.cache.get(cache_key)
        if cached is not None:
            cached.metadata["cache_hit"] = True
            return cached

        if not self.breaker.allow():
            return AIResponse(request.request_id, "Service temporarily degraded.", self.model_version, 0.0, metadata={"fallback": True})

        try:
            messages = [{"role": "user", "content": request.input_text}]
            output = self.llm.complete(messages)
            response = AIResponse(
                request_id=request.request_id,
                output=output,
                model_version=self.model_version,
                latency_ms=(time.perf_counter() - start) * 1000,
                confidence=0.7,
                metadata={"cache_hit": False},
            )
            self.cache.set(cache_key, response)
            self.breaker.success()
            return response
        except Exception as exc:
            self.breaker.failure()
            return AIResponse(request.request_id, "Fallback response.", self.model_version, 0.0, metadata={"error": str(exc)})


class MicroBatcher:
    """Collect requests into short windows for higher model throughput."""

    def __init__(self, max_batch_size: int = 16, max_wait_ms: int = 20):
        self.max_batch_size = max_batch_size
        self.max_wait_ms = max_wait_ms
        self.items: Deque[Tuple[int, AIRequest]] = deque()

    def add(self, request: AIRequest) -> None:
        self.items.append((now_ms(), request))

    def should_flush(self) -> bool:
        if len(self.items) >= self.max_batch_size:
            return True
        if not self.items:
            return False
        oldest_ms = self.items[0][0]
        return now_ms() - oldest_ms >= self.max_wait_ms

    def flush(self) -> List[AIRequest]:
        batch = []
        while self.items and len(batch) < self.max_batch_size:
            _, request = self.items.popleft()
            batch.append(request)
        return batch


class AsyncWorkerPool:
    """Async queue worker pattern for background AI jobs."""

    def __init__(self, handler: Callable[[AIRequest], AIResponse], workers: int = 2):
        self.handler = handler
        self.queue: asyncio.Queue[AIRequest] = asyncio.Queue()
        self.workers = workers
        self.results: Dict[str, AIResponse] = {}

    async def submit(self, request: AIRequest) -> None:
        await self.queue.put(request)

    async def run_once(self) -> None:
        async def worker() -> None:
            while not self.queue.empty():
                request = await self.queue.get()
                self.results[request.request_id] = self.handler(request)
                self.queue.task_done()

        await asyncio.gather(*(worker() for _ in range(self.workers)))


# =============================================================================
# 10. OBSERVABILITY, COST, DRIFT, AND FEEDBACK LOOPS
# =============================================================================

class MetricStore:
    def __init__(self):
        self.metrics: Dict[str, List[float]] = defaultdict(list)

    def record(self, name: str, value: float) -> None:
        self.metrics[name].append(float(value))

    def summary(self) -> Dict[str, Dict[str, float]]:
        result = {}
        for name, values in self.metrics.items():
            result[name] = {
                "count": len(values),
                "avg": statistics.mean(values),
                "p95": percentile(values, 95),
                "max": max(values),
            }
        return result


def percentile(values: Sequence[float], pct: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = math.ceil((pct / 100) * len(ordered)) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


class CostTracker:
    """Token/cost accounting for LLM products."""

    def __init__(self, input_cost_per_1k: float, output_cost_per_1k: float):
        self.input_cost_per_1k = input_cost_per_1k
        self.output_cost_per_1k = output_cost_per_1k
        self.rows: List[Dict[str, Any]] = []

    def record(self, request_id: str, input_tokens: int, output_tokens: int) -> float:
        cost = input_tokens / 1000 * self.input_cost_per_1k + output_tokens / 1000 * self.output_cost_per_1k
        self.rows.append({"request_id": request_id, "input_tokens": input_tokens, "output_tokens": output_tokens, "cost": cost})
        return cost

    def total_cost(self) -> float:
        return sum(row["cost"] for row in self.rows)


class DriftMonitor:
    """Text drift via token distribution changes."""

    def __init__(self, reference_texts: Sequence[str]):
        self.reference_distribution = self._distribution(reference_texts)

    def score(self, current_texts: Sequence[str]) -> Dict[str, float]:
        current = self._distribution(current_texts)
        vocabulary = set(self.reference_distribution) | set(current)
        l1 = sum(abs(self.reference_distribution.get(tok, 0.0) - current.get(tok, 0.0)) for tok in vocabulary)
        return {"token_distribution_l1": l1, "drifted": float(l1 > 0.5)}

    def _distribution(self, texts: Sequence[str]) -> Dict[str, float]:
        counts = Counter(token for text in texts for token in tokenize(text))
        total = sum(counts.values()) or 1
        return {token: count / total for token, count in counts.items()}


@dataclass
class FeedbackEvent:
    request_id: str
    user_id: str
    rating: int
    comment: str
    created_at_ms: int = field(default_factory=now_ms)


class FeedbackStore:
    def __init__(self):
        self.events: List[FeedbackEvent] = []

    def add(self, event: FeedbackEvent) -> None:
        self.events.append(event)

    def summary(self) -> Dict[str, Any]:
        ratings = [event.rating for event in self.events]
        return {
            "count": len(ratings),
            "avg_rating": statistics.mean(ratings) if ratings else 0.0,
            "low_rating_count": sum(1 for rating in ratings if rating <= 2),
        }


# =============================================================================
# 11. MODEL REGISTRY, GOVERNANCE, AUDIT, AND RELEASE MANAGEMENT
# =============================================================================

@dataclass
class ModelArtifact:
    name: str
    version: str
    path: str
    metrics: Dict[str, float]
    owner: str
    approved: bool = False
    created_at_ms: int = field(default_factory=now_ms)


class ModelRegistry:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.artifacts: Dict[str, ModelArtifact] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    artifact = ModelArtifact(**json.loads(line))
                    self.artifacts[f"{artifact.name}:{artifact.version}"] = artifact

    def register(self, artifact: ModelArtifact) -> None:
        key = f"{artifact.name}:{artifact.version}"
        self.artifacts[key] = artifact
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(dataclasses.asdict(artifact)) + "\n")

    def get(self, name: str, version: str) -> ModelArtifact:
        return self.artifacts[f"{name}:{version}"]


class AuditLog:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event_type: str, actor: str, payload: Dict[str, Any]) -> None:
        row = {
            "event_type": event_type,
            "actor": actor,
            "payload": payload,
            "payload_hash": stable_hash(payload),
            "created_at_ms": now_ms(),
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")


class ReleaseStrategy(str, enum.Enum):
    SHADOW = "shadow"
    CANARY = "canary"
    BLUE_GREEN = "blue_green"
    FULL = "full"


@dataclass
class ReleasePlan:
    artifact: ModelArtifact
    strategy: ReleaseStrategy
    quality_gate: Dict[str, float]
    rollback_plan: str
    monitoring_window_minutes: int

    def is_ready(self) -> bool:
        return self.artifact.approved and all(
            self.artifact.metrics.get(metric, -math.inf) >= threshold
            for metric, threshold in self.quality_gate.items()
        )


# =============================================================================
# 12. ENTERPRISE ARCHITECTURE BLUEPRINTS
# =============================================================================

class AIArchitectureBlueprint:
    def __init__(self, problem: BusinessProblem):
        self.problem = problem

    def generate(self) -> Dict[str, Any]:
        return {
            "problem": dataclasses.asdict(self.problem),
            "architecture_hint": self.problem.architecture_hint(),
            "layers": {
                "experience": ["UX flows", "human review", "feedback capture"],
                "policy": ["prompt safety", "PII redaction", "authorization", "high-impact approval"],
                "orchestration": ["RAG", "tools", "state machines", "fallbacks"],
                "model": ["baseline", "LLM/deep model", "evaluation suite", "model registry"],
                "data": ["contracts", "lineage", "feature store", "vector index"],
                "platform": ["serving", "observability", "cost control", "release management"],
            },
            "slo_examples": {
                "latency_p95_ms": self.problem.decision_latency_ms,
                "availability": "99.9%",
                "blocked_unsafe_requests": "tracked",
                "business_kpi": self.problem.business_kpi,
            },
            "principal_review_questions": [
                "What failure mode causes customer, financial, safety, or compliance harm?",
                "Which quality metric predicts business value?",
                "What is the fallback when the model, retrieval, tool, or feature store fails?",
                "How are drift, cost, latency, and user feedback monitored?",
                "Who can approve model/prompt changes and rollbacks?",
            ],
        }


def pattern_catalog() -> Dict[str, List[str]]:
    return {
        "rag": ["chunking", "embedding", "hybrid search", "reranking", "citation validation", "answer evaluation"],
        "agents": ["tool schemas", "state machines", "human approval", "timeouts", "sandboxing", "audit trails"],
        "real_time": ["low-latency serving", "micro-batching", "cache", "circuit breaker", "fallback model"],
        "batch_ai": ["data contracts", "idempotent jobs", "checkpointing", "quality gates", "lineage"],
        "governance": ["model cards", "release plans", "approval workflow", "audit logs", "risk tiering"],
        "observability": ["latency", "quality", "drift", "cost", "error budget", "business KPI"],
    }


def principal_ai_engineer_competency_map() -> Dict[str, List[str]]:
    return {
        "business": ["problem framing", "KPI design", "risk management", "stakeholder communication"],
        "data": ["contracts", "quality", "lineage", "privacy", "feature engineering"],
        "modeling": ["classical ML", "deep learning", "LLMs", "RAG", "evaluation", "optimization"],
        "systems": ["serving", "distributed systems", "streaming", "resilience", "observability"],
        "security": ["prompt injection", "PII", "secrets", "authorization", "supply chain"],
        "governance": ["model cards", "audit", "approvals", "monitoring", "incident response"],
    }


# =============================================================================
# 13. END-TO-END LIGHTWEIGHT DEMO
# =============================================================================

def build_demo_rag() -> RAGPipeline:
    docs = [
        Document("policy-1", "Refunds are available within 30 days when the customer has a receipt.", {"domain": "support"}),
        Document("policy-2", "Enterprise customers receive priority support and dedicated onboarding.", {"domain": "support"}),
        Document("risk-1", "High risk financial actions require human approval before execution.", {"domain": "governance"}),
    ]
    embedder = HashEmbeddingModel(dimensions=64)
    store = InMemoryVectorStore(embedder)
    for doc in docs:
        store.add(chunk_text(doc, chunk_size=30, overlap=5))
    return RAGPipeline(store, RuleBasedLLMClient())


def run_lightweight_demo() -> Dict[str, Any]:
    """Runs without external dependencies."""
    problem = BusinessProblem(
        name="real-time customer support copilot",
        problem_type=AIProblemType.RAG,
        users=["support agents", "operations managers"],
        business_kpi="first contact resolution",
        decision_latency_ms=800,
        risk_level="medium",
        success_criteria=["grounded answers", "lower handle time", "safe escalation"],
    )

    records = [
        {"age": 35, "income": 80000, "late_payments": 0, "approved": 1},
        {"age": 22, "income": 32000, "late_payments": 3, "approved": 0},
        {"age": 48, "income": 120000, "late_payments": 1, "approved": 1},
        {"age": 29, "income": 45000, "late_payments": 2, "approved": 0},
    ]
    contract = DataContract(
        "credit_decision",
        "1.0",
        [
            FeatureSpec("age", "number", min_value=18, max_value=100),
            FeatureSpec("income", "number", min_value=0),
            FeatureSpec("late_payments", "number", min_value=0),
        ],
        target="approved",
    )
    validation_errors = [contract.validate(row) for row in records]
    transformer = NumericFeatureTransformer(["age", "income", "late_payments"]).fit(records)
    x = transformer.transform(records)
    y = [row["approved"] for row in records]
    model = SimpleLogisticRegression(epochs=50).fit(x, y)

    rag = build_demo_rag()
    rag_answer = rag.answer("Can an enterprise customer get priority support?")

    service = AIService(
        "rule-llm-v1",
        RuleBasedLLMClient(),
        PolicyEngine(SafetyClassifier(), PiiRedactor()),
    )
    response = service.handle(AIRequest("req-1", "user-1", "Return JSON with a short support answer."))

    return {
        "sme_playbook": sme_ai_playbook(),
        "competency_map": principal_ai_engineer_competency_map(),
        "contract_fingerprint": contract.fingerprint(),
        "validation_errors": validation_errors,
        "data_profile": DataQualityProfiler().profile_records(records),
        "baseline_metrics": evaluate_binary_classifier(model, x, y),
        "rag_answer": rag_answer,
        "service_response": dataclasses.asdict(response),
        "architecture": AIArchitectureBlueprint(problem).generate(),
        "patterns": pattern_catalog(),
    }


if __name__ == "__main__":
    print(json.dumps(run_lightweight_demo(), indent=2, default=str))
