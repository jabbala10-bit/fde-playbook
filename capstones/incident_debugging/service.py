"""The instrumented service layer from reference-architecture.md, as real
code: Gateway -> Input Guardrails -> Router -> Model Call -> Output
Guardrails -> Logging -> Eval Sampling.

Pass `fault=` (see faults.py) to activate one seeded bug for the debugging
capstone. With `fault=None` this is the reference-correct implementation —
that's also what "fixed" should look like once a candidate patches a bug.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

PII_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")  # SSN-shaped, for demo purposes
INJECTION_MARKERS = ("ignore previous instructions", "disregard the system prompt")

MODEL_REGISTRY = {
    "support-classifier": {"primary": "model-a", "fallback": "model-b"},
}

# Approximated as a word count so this stays dependency-free; a real service
# layer would use the provider SDK's tokenizer.
TOKEN_CAP = 20


@dataclass
class LogRecord:
    request_id: str
    tenant_id: str
    logical_model: str
    input_redacted: str
    output: str
    latency_ms: float
    cost_tokens: int
    guardrail_flags: List[str] = field(default_factory=list)
    eval_score: Optional[float] = None


class ModelBackend:
    """Mock model call — deterministic, offline."""

    def __init__(self, name: str, degraded: bool = False):
        self.name = name
        self.degraded = degraded

    def call(self, prompt: str) -> str:
        if self.degraded:
            raise RuntimeError(f"backend {self.name!r} is degraded")
        return f"[{self.name}] response to: {prompt[:50]}"


class ServiceLayer:
    def __init__(self, fault: Optional[str] = None):
        self.fault = fault
        self.logs: List[LogRecord] = []
        self._backends = {
            "model-a": ModelBackend("model-a", degraded=(fault == "fallback_never_fires")),
            "model-b": ModelBackend("model-b"),
        }

    def handle_request(self, tenant_id: str, logical_model: str, prompt: str) -> Dict[str, Any]:
        start = time.perf_counter()
        request_id = str(uuid.uuid4())
        guardrail_flags: List[str] = []

        # --- input guardrails ---
        redacted = self._redact_pii(prompt)
        if self._is_injection(prompt):
            guardrail_flags.append("prompt_injection_blocked")
            return self._finalize(
                request_id, tenant_id, logical_model, redacted, "", start, 0, guardrail_flags, blocked=True
            )

        # --- router ---
        backend = self._route(logical_model)

        # --- model call ---
        words = redacted.split()
        if self.fault == "missing_token_cap":
            truncated_prompt = redacted  # BUG: token cap not applied before the model call
        else:
            truncated_prompt = " ".join(words[:TOKEN_CAP])
        output = backend.call(truncated_prompt)
        cost_tokens = len(truncated_prompt.split())

        # --- output guardrails ---
        if len(output) < 5:
            guardrail_flags.append("low_confidence_routed_to_human")

        return self._finalize(
            request_id, tenant_id, logical_model, redacted, output, start, cost_tokens, guardrail_flags
        )

    def _redact_pii(self, text: str) -> str:
        if self.fault == "pii_redaction_bypass":
            return text  # BUG: redaction silently skipped
        return PII_PATTERN.sub("[REDACTED-SSN]", text)

    def _is_injection(self, text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in INJECTION_MARKERS)

    def _route(self, logical_model: str) -> ModelBackend:
        entry = MODEL_REGISTRY[logical_model]
        primary = self._backends[entry["primary"]]
        fallback = self._backends[entry["fallback"]]
        if not primary.degraded:
            return primary
        if self.fault == "fallback_never_fires":
            # BUG: the fallback chain is defined in MODEL_REGISTRY but never
            # actually consulted here when the primary is degraded.
            return primary
        return fallback

    def _finalize(
        self,
        request_id: str,
        tenant_id: str,
        logical_model: str,
        redacted: str,
        output: str,
        start: float,
        cost_tokens: int,
        guardrail_flags: List[str],
        blocked: bool = False,
    ) -> Dict[str, Any]:
        eval_score = None
        if self.fault == "eval_sampling_blocks_path":
            # BUG: eval sampling should be async / off the critical path
            # (reference-architecture.md says "async" three times on
            # purpose) — this blocks the response instead.
            time.sleep(0.05)
            eval_score = 0.9

        latency_ms = (time.perf_counter() - start) * 1000
        record = LogRecord(
            request_id=request_id,
            tenant_id=tenant_id,
            logical_model=logical_model,
            input_redacted=redacted,
            output=output,
            latency_ms=latency_ms,
            cost_tokens=cost_tokens,
            guardrail_flags=guardrail_flags,
            eval_score=eval_score,
        )
        self.logs.append(record)
        return {
            "request_id": request_id,
            "output": output,
            "blocked": blocked,
            "latency_ms": latency_ms,
            "cost_tokens": cost_tokens,
            "guardrail_flags": guardrail_flags,
        }
