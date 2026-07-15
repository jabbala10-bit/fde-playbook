"""
A2A coding-agent examples from basic to advanced.

A2A (Agent2Agent) is a protocol for agent discovery and collaboration. Unlike
CrewAI or Google ADK, A2A is not primarily an in-process orchestration framework:
it is a wire protocol for delegating work to remote agents through Agent Cards and
standard message/task operations.

This module demonstrates:

1. Single remote coding agent call.
2. Multi-agent design -> implementation -> review workflow.
3. Complex production workflow with parallel remote reviews and refinement.
4. Agent Card generation for A2A coding agents.

Dry-run mode works without remote A2A servers:
    python ai/a2a_coding.py --mode pair --dry-run

Live mode expects A2A HTTP+JSON endpoints, for example:
    python ai/a2a_coding.py --mode single --base-url http://localhost:8000/a2a/coder
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from textwrap import dedent
from typing import Any, Callable, Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


AGENT_CARD_WELL_KNOWN_PATH = "/.well-known/agent-card.json"
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_PROTOCOL_VERSION = "1.0"
DEFAULT_INPUT_MODES = ("text/plain",)
DEFAULT_OUTPUT_MODES = ("text/plain", "application/json")
logger = logging.getLogger(__name__)


class Difficulty(str, Enum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass(frozen=True)
class CodingProblem:
    """Structured coding problem passed between A2A agents."""

    title: str
    prompt: str
    language: str = "Python"
    difficulty: Difficulty = Difficulty.BASIC
    constraints: tuple[str, ...] = field(default_factory=tuple)
    deliverables: tuple[str, ...] = (
        "approach",
        "production-quality code",
        "complexity analysis",
        "tests",
    )

    def to_prompt(self) -> str:
        return dedent(
            f"""
            Title: {self.title}
            Difficulty: {self.difficulty.value}
            Language: {self.language}

            Problem:
            {self.prompt}

            Constraints:
            {_format_bullets(self.constraints)}

            Required deliverables:
            {_format_bullets(self.deliverables)}
            """
        ).strip()


@dataclass(frozen=True)
class A2AConfig:
    """HTTP client settings for A2A calls."""

    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    bearer_token: Optional[str] = None
    protocol_version: str = DEFAULT_PROTOCOL_VERSION
    dry_run: bool = False

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        _require_text(self.protocol_version, "protocol_version")


@dataclass(frozen=True)
class A2AAgentRef:
    """Local reference to a remote A2A agent."""

    name: str
    base_url: str
    skill_id: str
    instructions: str
    local_tools: tuple[Callable[[str], dict[str, list[str]]], ...] = ()
    accepted_output_modes: tuple[str, ...] = DEFAULT_OUTPUT_MODES

    def __post_init__(self) -> None:
        _require_text(self.name, "name")
        _require_text(self.base_url, "base_url")
        _require_text(self.skill_id, "skill_id")
        _require_text(self.instructions, "instructions")


@dataclass(frozen=True)
class A2AResult:
    agent_name: str
    output: str
    elapsed_ms: float
    request: dict[str, Any]
    response: dict[str, Any]
    local_observations: dict[str, Any] = field(default_factory=dict)


def static_code_risk_scan(code: str) -> dict[str, list[str]]:
    """Deterministic local review before sending work to a remote coding agent."""

    lowered = code.lower()
    risks: list[str] = []
    checks = {
        "eval(": "Avoid eval; parse inputs explicitly or use a constrained parser.",
        "exec(": "Avoid exec; prefer explicit functions and whitelisted behavior.",
        "shell=true": "Avoid shell=True unless all command inputs are trusted.",
        "password": "Check for hard-coded secrets or sensitive identifiers.",
        "api_key": "Load API keys from environment or a secret manager.",
        "todo": "Resolve TODOs or convert them into tracked follow-up work.",
    }

    for needle, message in checks.items():
        if needle in lowered:
            risks.append(message)

    if "def test_" not in lowered and "pytest" not in lowered and "unittest" not in lowered:
        risks.append("Add tests for success paths, edge cases, and invalid inputs.")
    if "logging" not in lowered:
        risks.append("Add structured logging where operational failures matter.")
    if "typing" not in lowered and "from __future__ import annotations" not in lowered:
        risks.append("Add type hints for public functions and data structures.")

    return {"risks": risks or ["No obvious static risks found."]}


def complexity_probe(solution_plan: str) -> dict[str, list[str]]:
    """Deterministic local complexity review."""

    plan = solution_plan.lower()
    observations: list[str] = []

    if "nested loop" in plan or "for each" in plan:
        observations.append("Watch for O(n^2) behavior; justify or improve it.")
    if "sort" in plan:
        observations.append("Sorting usually implies O(n log n) time.")
    if "dict" in plan or "hash" in plan or "map" in plan:
        observations.append("Hash maps can reduce lookup cost to average O(1).")
    if "recursion" in plan:
        observations.append("Define recursion depth, base cases, and stack risks.")
    if "cache" in plan or "memo" in plan:
        observations.append("Document cache key design and memory growth.")

    return {"observations": observations or ["No major complexity flags detected."]}


class A2AHttpClient:
    """Minimal HTTP+JSON A2A client using only the Python standard library."""

    def __init__(self, config: Optional[A2AConfig] = None) -> None:
        self.config = config or A2AConfig()

    def fetch_agent_card(self, base_url: str) -> dict[str, Any]:
        card_url = urljoin(_ensure_trailing_slash(base_url), AGENT_CARD_WELL_KNOWN_PATH.lstrip("/"))
        return self._request_json("GET", card_url)

    def send_message(
        self,
        agent: A2AAgentRef,
        message_text: str,
        *,
        task_id: Optional[str] = None,
        context_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        message = {
            "messageId": f"msg-{uuid.uuid4()}",
            "role": "ROLE_USER",
            "parts": [{"text": message_text}],
        }
        if task_id:
            message["taskId"] = task_id
        if context_id:
            message["contextId"] = context_id

        payload = {
            "message": message,
            "configuration": {
                "acceptedOutputModes": list(agent.accepted_output_modes),
            },
            "metadata": metadata or {},
        }

        if self.config.dry_run:
            response = {
                "task": {
                    "id": f"dry-task-{uuid.uuid4()}",
                    "status": {"state": "TASK_STATE_COMPLETED"},
                    "artifacts": [
                        {
                            "parts": [
                                {
                                    "text": (
                                        f"[dry-run] {agent.name} would process "
                                        f"skill '{agent.skill_id}'."
                                    )
                                }
                            ]
                        }
                    ],
                }
            }
            return payload, response

        endpoint = urljoin(_ensure_trailing_slash(agent.base_url), "message:send")
        return payload, self._request_json("POST", endpoint, payload)

    def _request_json(
        self,
        method: str,
        url: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {
            "Accept": "application/a2a+json, application/json",
            "A2A-Version": self.config.protocol_version,
        }
        if payload is not None:
            headers["Content-Type"] = "application/a2a+json"
        if self.config.bearer_token:
            headers["Authorization"] = f"Bearer {self.config.bearer_token}"

        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"A2A HTTP {exc.code} from {url}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"A2A request failed for {url}: {exc}") from exc


class A2ACodingOrchestrator:
    """A2A workflow orchestrator for coding-agent delegation."""

    def __init__(
        self,
        config: Optional[A2AConfig] = None,
        client: Optional[A2AHttpClient] = None,
    ) -> None:
        self.config = config or A2AConfig()
        self.client = client or A2AHttpClient(self.config)

    def run_single_agent(self, problem: CodingProblem, agent: A2AAgentRef) -> A2AResult:
        return self._run_agent(agent, problem.to_prompt())

    def run_pair_programming(
        self,
        problem: CodingProblem,
        *,
        architect: A2AAgentRef,
        engineer: A2AAgentRef,
        reviewer: A2AAgentRef,
    ) -> dict[str, A2AResult]:
        design = self._run_agent(architect, problem.to_prompt())
        implementation = self._run_agent(
            engineer,
            _join_context(problem.to_prompt(), {"design_notes": design.output}),
        )
        review = self._run_agent(
            reviewer,
            _join_context(
                problem.to_prompt(),
                {
                    "design_notes": design.output,
                    "implementation_package": implementation.output,
                },
            ),
        )
        return {
            "design": design,
            "implementation": implementation,
            "review": review,
        }

    def run_complex_delivery(
        self,
        problem: CodingProblem,
        *,
        requirements: A2AAgentRef,
        architect: A2AAgentRef,
        engineer: A2AAgentRef,
        correctness_reviewer: A2AAgentRef,
        test_reviewer: A2AAgentRef,
        security_reviewer: A2AAgentRef,
        refactorer: A2AAgentRef,
        final_writer: A2AAgentRef,
        max_refinement_rounds: int = 2,
    ) -> dict[str, Any]:
        requirements_result = self._run_agent(requirements, problem.to_prompt())
        architecture = self._run_agent(
            architect,
            _join_context(problem.to_prompt(), {"requirements": requirements_result.output}),
        )
        candidate = self._run_agent(
            engineer,
            _join_context(
                problem.to_prompt(),
                {
                    "requirements": requirements_result.output,
                    "architecture": architecture.output,
                },
            ),
        )

        refinement_history: list[dict[str, A2AResult]] = []
        for round_number in range(1, max_refinement_rounds + 1):
            review_context = _join_context(
                problem.to_prompt(),
                {
                    "requirements": requirements_result.output,
                    "architecture": architecture.output,
                    "candidate_code": candidate.output,
                    "round": str(round_number),
                },
            )
            reviews = self._run_reviews_parallel(
                [correctness_reviewer, test_reviewer, security_reviewer],
                review_context,
            )
            candidate = self._run_agent(
                refactorer,
                _join_context(
                    problem.to_prompt(),
                    {
                        "candidate_code": candidate.output,
                        "correctness_review": reviews["correctness_reviewer"].output,
                        "test_review": reviews["test_reviewer"].output,
                        "security_review": reviews["security_reliability_reviewer"].output,
                    },
                ),
            )
            refinement_history.append(reviews | {"refactor": candidate})
            if _looks_approved(candidate.output):
                break

        final = self._run_agent(
            final_writer,
            _join_context(
                problem.to_prompt(),
                {
                    "requirements": requirements_result.output,
                    "architecture": architecture.output,
                    "final_candidate": candidate.output,
                },
            ),
        )

        return {
            "requirements": requirements_result,
            "architecture": architecture,
            "final_candidate": candidate,
            "refinement_history": refinement_history,
            "final": final,
        }

    def _run_reviews_parallel(
        self,
        agents: list[A2AAgentRef],
        prompt: str,
    ) -> dict[str, A2AResult]:
        if self.config.dry_run:
            return {agent.name: self._run_agent(agent, prompt) for agent in agents}

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(agents)) as executor:
            futures = {
                executor.submit(self._run_agent, agent, prompt): agent.name
                for agent in agents
            }
            return {
                agent_name: future.result()
                for future, agent_name in futures.items()
            }

    def _run_agent(self, agent: A2AAgentRef, prompt: str) -> A2AResult:
        local_observations = _run_local_tools(agent.local_tools, prompt)
        message = _join_context(
            prompt,
            {
                "remote_agent_role": agent.name,
                "skill_id": agent.skill_id,
                "instructions": agent.instructions,
                "local_observations": json.dumps(local_observations, indent=2),
            },
        )
        started = time.perf_counter()
        request_payload, response_payload = self.client.send_message(
            agent,
            message,
            metadata={"skillId": agent.skill_id, "orchestrator": "a2a_coding"},
        )
        elapsed_ms = (time.perf_counter() - started) * 1_000
        output = extract_text_from_a2a_response(response_payload)
        logger.info(
            "a2a.agent.completed",
            extra={"agent": agent.name, "elapsed_ms": round(elapsed_ms, 3)},
        )
        return A2AResult(
            agent_name=agent.name,
            output=output,
            elapsed_ms=round(elapsed_ms, 3),
            request=request_payload,
            response=response_payload,
            local_observations=local_observations,
        )


def build_default_agent_refs(base_url: str) -> dict[str, A2AAgentRef]:
    """Create role-specific remote refs, all pointing to one A2A endpoint."""

    base_url = _normalize_base_url(base_url)
    return {
        "single": A2AAgentRef(
            name="single_coding_solver",
            base_url=base_url,
            skill_id="solve-coding-problem",
            instructions=(
                "Solve the coding problem with approach, code, tests, edge cases, "
                "and complexity analysis."
            ),
            local_tools=(complexity_probe, static_code_risk_scan),
        ),
        "architect": A2AAgentRef(
            name="algorithm_architect",
            base_url=base_url,
            skill_id="design-coding-solution",
            instructions=(
                "Create implementation-ready design notes: assumptions, algorithm, "
                "data structures, edge cases, and complexity."
            ),
            local_tools=(complexity_probe,),
        ),
        "engineer": A2AAgentRef(
            name="implementation_engineer",
            base_url=base_url,
            skill_id="implement-coding-solution",
            instructions="Write clean, typed, testable code from the provided design.",
            local_tools=(static_code_risk_scan,),
        ),
        "reviewer": A2AAgentRef(
            name="code_reviewer",
            base_url=base_url,
            skill_id="review-coding-solution",
            instructions=(
                "Review correctness, security, maintainability, and test coverage. "
                "Return corrected code if issues exist."
            ),
            local_tools=(static_code_risk_scan,),
        ),
        "requirements": A2AAgentRef(
            name="requirements_analyst",
            base_url=base_url,
            skill_id="extract-acceptance-criteria",
            instructions="Extract acceptance criteria, edge cases, non-goals, and test strategy.",
        ),
        "correctness_reviewer": A2AAgentRef(
            name="correctness_reviewer",
            base_url=base_url,
            skill_id="review-correctness",
            instructions="Review functional correctness and edge cases. Return concrete fixes.",
        ),
        "test_reviewer": A2AAgentRef(
            name="test_reviewer",
            base_url=base_url,
            skill_id="review-tests",
            instructions="Review test quality and missing coverage. Return concrete fixes.",
        ),
        "security_reviewer": A2AAgentRef(
            name="security_reliability_reviewer",
            base_url=base_url,
            skill_id="review-security-reliability",
            instructions="Review security, reliability, performance, and maintainability risks.",
            local_tools=(static_code_risk_scan,),
        ),
        "refactorer": A2AAgentRef(
            name="refactor_engineer",
            base_url=base_url,
            skill_id="refactor-from-review",
            instructions=(
                "Apply review feedback. Return corrected code and tests. "
                "If no changes are needed, say 'approved: no changes are needed'."
            ),
            local_tools=(static_code_risk_scan,),
        ),
        "final_writer": A2AAgentRef(
            name="final_handoff_writer",
            base_url=base_url,
            skill_id="write-final-handoff",
            instructions=(
                "Create final handoff with code, tests, explanation, complexity, "
                "run instructions, limitations, and production notes."
            ),
        ),
    }


def create_coding_agent_card(base_url: str) -> dict[str, Any]:
    """Create a v1-style A2A Agent Card for a coding agent endpoint."""

    base_url = _normalize_base_url(base_url)
    return {
        "name": "coding-a2a-agent",
        "description": "A2A-capable agent for coding problem solving, implementation, and review.",
        "version": "1.0.0",
        "provider": {
            "organization": "Local Examples",
            "url": "https://example.local/a2a-coding",
        },
        "supportedInterfaces": [
            {
                "url": base_url,
                "protocolBinding": "HTTP+JSON",
                "protocolVersion": DEFAULT_PROTOCOL_VERSION,
            }
        ],
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "extendedAgentCard": False,
        },
        "defaultInputModes": list(DEFAULT_INPUT_MODES),
        "defaultOutputModes": list(DEFAULT_OUTPUT_MODES),
        "skills": [
            {
                "id": "solve-coding-problem",
                "name": "Solve Coding Problem",
                "description": "Solve a focused coding problem with code, tests, and complexity analysis.",
                "tags": ["coding", "algorithms", "tests"],
                "examples": ["Solve Two Sum in Python with tests."],
            },
            {
                "id": "design-coding-solution",
                "name": "Design Coding Solution",
                "description": "Create an implementation-ready design before coding.",
                "tags": ["architecture", "design", "complexity"],
                "examples": ["Design a sliding-window rate limiter."],
            },
            {
                "id": "implement-coding-solution",
                "name": "Implement Coding Solution",
                "description": "Write production-minded implementation code from a design.",
                "tags": ["implementation", "typing", "tests"],
                "examples": ["Implement a priority job scheduler."],
            },
            {
                "id": "review-coding-solution",
                "name": "Review Coding Solution",
                "description": "Review code for correctness, security, maintainability, and coverage.",
                "tags": ["review", "security", "quality"],
                "examples": ["Review this rate limiter for race conditions and missing tests."],
            },
        ],
    }


def create_google_adk_remote_a2a_snippet(
    *,
    agent_name: str = "coding_a2a_agent",
    base_url: str = "http://localhost:8000/a2a/coding",
) -> str:
    """Return an ADK snippet matching the A2A style used elsewhere in this repo."""

    return dedent(
        f"""
        from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH, RemoteA2aAgent

        {agent_name} = RemoteA2aAgent(
            name="{agent_name}",
            agent_card=f"{base_url}{{AGENT_CARD_WELL_KNOWN_PATH}}",
        )
        """
    ).strip()


def extract_text_from_a2a_response(response: dict[str, Any]) -> str:
    """Extract readable text from common A2A response shapes."""

    if "result" in response and isinstance(response["result"], dict):
        response = response["result"]

    texts: list[str] = []
    message = response.get("message")
    if isinstance(message, dict):
        texts.extend(_extract_text_from_parts(message.get("parts", [])))

    task = response.get("task")
    if isinstance(task, dict):
        status = task.get("status", {})
        if isinstance(status, dict):
            status_message = status.get("message")
            if isinstance(status_message, dict):
                texts.extend(_extract_text_from_parts(status_message.get("parts", [])))

        for artifact in task.get("artifacts", []) or []:
            if isinstance(artifact, dict):
                texts.extend(_extract_text_from_parts(artifact.get("parts", [])))

    if texts:
        return "\n".join(texts)
    return json.dumps(response, indent=2)


def example_basic_two_sum() -> CodingProblem:
    return CodingProblem(
        title="Two Sum",
        prompt=(
            "Given a list of integers nums and an integer target, return indices "
            "of the two numbers such that they add up to target. Each input has "
            "exactly one solution, and the same element cannot be used twice."
        ),
        difficulty=Difficulty.BASIC,
        constraints=(
            "Return indices, not values.",
            "Prefer O(n) time.",
            "Handle duplicate numbers correctly.",
        ),
    )


def example_intermediate_rate_limiter() -> CodingProblem:
    return CodingProblem(
        title="Sliding Window Rate Limiter",
        prompt=(
            "Design a rate limiter that allows at most N requests per user within "
            "a rolling time window. Provide code that can be unit tested without sleeping."
        ),
        difficulty=Difficulty.INTERMEDIATE,
        constraints=(
            "Inject a clock/time provider.",
            "Avoid global mutable state.",
            "Evict old timestamps to prevent memory growth.",
        ),
    )


def example_advanced_job_scheduler() -> CodingProblem:
    return CodingProblem(
        title="Priority Job Scheduler",
        prompt=(
            "Build an in-memory job scheduler that supports adding jobs with priority "
            "and scheduled time, claiming the next runnable job, marking jobs complete "
            "or failed, and retrying failed jobs up to a maximum."
        ),
        difficulty=Difficulty.ADVANCED,
        constraints=(
            "Make state transitions explicit.",
            "Prevent claiming jobs before scheduled time.",
            "Include retry exhaustion and tie-breaking tests.",
            "Keep the design adaptable for persistent storage later.",
        ),
    )


def describe_available_examples() -> str:
    return dedent(
        """
        Available A2A coding examples:

        1. single
           Send one A2A message to a coding agent.

        2. pair
           A2A workflow: architect -> implementation engineer -> reviewer.

        3. complex
           Production-style workflow:
           requirements -> architecture -> implementation -> parallel remote reviews
           -> refinement -> final handoff.

        4. card
           Print an A2A Agent Card for a coding agent endpoint.

        5. adk-snippet
           Print Google ADK RemoteA2aAgent wiring for this coding agent.

        Example commands:
            python ai/a2a_coding.py --mode guide
            python ai/a2a_coding.py --mode single --dry-run
            python ai/a2a_coding.py --mode pair --problem rate-limiter --dry-run
            python ai/a2a_coding.py --mode complex --problem job-scheduler --dry-run
            python ai/a2a_coding.py --mode card --base-url http://localhost:8000/a2a/coding
        """
    ).strip()


def _extract_text_from_parts(parts: Iterable[Any]) -> list[str]:
    texts: list[str] = []
    for part in parts:
        if isinstance(part, dict):
            value = part.get("text")
            if isinstance(value, str):
                texts.append(value)
    return texts


def _run_local_tools(
    tools: Iterable[Callable[[str], dict[str, list[str]]]],
    text: str,
) -> dict[str, Any]:
    return {tool.__name__: tool(text) for tool in tools}


def _join_context(base_prompt: str, sections: dict[str, str]) -> str:
    rendered_sections = "\n\n".join(
        f"## {name}\n{content}" for name, content in sections.items()
    )
    return f"{base_prompt}\n\n{rendered_sections}" if rendered_sections else base_prompt


def _looks_approved(text: str) -> bool:
    normalized = text.lower()
    approval_markers = (
        "approved: no changes are needed",
        "no changes are needed",
        "already production-ready",
    )
    return any(marker in normalized for marker in approval_markers)


def _format_bullets(items: Iterable[str]) -> str:
    values = [item.strip() for item in items if item and item.strip()]
    return "\n".join(f"- {item}" for item in values) if values else "- None"


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _normalize_base_url(base_url: str) -> str:
    _require_text(base_url, "base_url")
    return base_url.rstrip("/")


def _ensure_trailing_slash(value: str) -> str:
    return value if value.endswith("/") else f"{value}/"


def _to_printable(result: Any, *, show_payloads: bool = False) -> str:
    if isinstance(result, A2AResult):
        if show_payloads:
            return json.dumps(_result_to_dict(result, show_payloads=True), indent=2)
        return result.output

    if isinstance(result, dict):
        printable = {
            key: _result_to_dict(value, show_payloads=show_payloads)
            for key, value in result.items()
            if isinstance(value, A2AResult)
        }
        return json.dumps(printable, indent=2)
    return str(result)


def _result_to_dict(result: A2AResult, *, show_payloads: bool) -> dict[str, Any]:
    data: dict[str, Any] = {
        "agent": result.agent_name,
        "output": result.output,
        "elapsed_ms": result.elapsed_ms,
        "local_observations": result.local_observations,
    }
    if show_payloads:
        data["request"] = result.request
        data["response"] = result.response
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="A2A coding-agent examples")
    parser.add_argument(
        "--mode",
        choices=("guide", "single", "pair", "complex", "card", "adk-snippet"),
        default="guide",
        help="Which A2A workflow or artifact to run.",
    )
    parser.add_argument(
        "--problem",
        choices=("two-sum", "rate-limiter", "job-scheduler"),
        default="two-sum",
        help="Problem sent to the selected workflow.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("A2A_CODING_BASE_URL", "http://localhost:8000/a2a/coding"),
        help="A2A base URL used for all agent roles unless role-specific URLs are supplied.",
    )
    parser.add_argument("--architect-url", default=os.getenv("A2A_ARCHITECT_URL"))
    parser.add_argument("--engineer-url", default=os.getenv("A2A_ENGINEER_URL"))
    parser.add_argument("--reviewer-url", default=os.getenv("A2A_REVIEWER_URL"))
    parser.add_argument("--token", default=os.getenv("A2A_BEARER_TOKEN"))
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--dry-run", action="store_true", help="Do not call remote A2A endpoints.")
    parser.add_argument("--show-payloads", action="store_true", help="Include A2A request/response JSON.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    if args.mode == "guide":
        print(describe_available_examples())
        return
    if args.mode == "card":
        print(json.dumps(create_coding_agent_card(args.base_url), indent=2))
        return
    if args.mode == "adk-snippet":
        print(create_google_adk_remote_a2a_snippet(base_url=args.base_url))
        return

    problem_factory: dict[str, Callable[[], CodingProblem]] = {
        "two-sum": example_basic_two_sum,
        "rate-limiter": example_intermediate_rate_limiter,
        "job-scheduler": example_advanced_job_scheduler,
    }
    problem = problem_factory[args.problem]()

    config = A2AConfig(
        timeout_seconds=args.timeout,
        bearer_token=args.token,
        dry_run=args.dry_run,
    )
    refs = build_default_agent_refs(args.base_url)
    if args.architect_url:
        refs["architect"] = A2AAgentRef(
            **{**refs["architect"].__dict__, "base_url": _normalize_base_url(args.architect_url)}
        )
    if args.engineer_url:
        refs["engineer"] = A2AAgentRef(
            **{**refs["engineer"].__dict__, "base_url": _normalize_base_url(args.engineer_url)}
        )
    if args.reviewer_url:
        refs["reviewer"] = A2AAgentRef(
            **{**refs["reviewer"].__dict__, "base_url": _normalize_base_url(args.reviewer_url)}
        )

    orchestrator = A2ACodingOrchestrator(config)

    if args.mode == "single":
        result = orchestrator.run_single_agent(problem, refs["single"])
    elif args.mode == "pair":
        result = orchestrator.run_pair_programming(
            problem,
            architect=refs["architect"],
            engineer=refs["engineer"],
            reviewer=refs["reviewer"],
        )
    else:
        result = orchestrator.run_complex_delivery(
            problem,
            requirements=refs["requirements"],
            architect=refs["architect"],
            engineer=refs["engineer"],
            correctness_reviewer=refs["correctness_reviewer"],
            test_reviewer=refs["test_reviewer"],
            security_reviewer=refs["security_reviewer"],
            refactorer=refs["refactorer"],
            final_writer=refs["final_writer"],
        )

    print(_to_printable(result, show_payloads=args.show_payloads))


if __name__ == "__main__":
    main()
