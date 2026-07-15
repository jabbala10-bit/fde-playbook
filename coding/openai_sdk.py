"""
OpenAI SDK coding-agent examples from basic to advanced.

This module uses the official OpenAI Python SDK and the Responses API to build
three coding workflows:

1. Single-agent coding solver.
2. Multi-agent design -> implementation -> review pipeline.
3. Complex multi-agent production pipeline with parallel reviews and refinement.

Install and configure before running real API calls:
    pip install openai
    $env:OPENAI_API_KEY = "..."

Guide mode works without the OpenAI package installed:
    python ai/openai_sdk.py --mode guide
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from textwrap import dedent
from typing import Any, Callable, Iterable, Optional


DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6")
DEFAULT_TIMEOUT_SECONDS = 60.0
logger = logging.getLogger(__name__)


class Difficulty(str, Enum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass(frozen=True)
class CodingProblem:
    """Structured problem input shared by all workflows."""

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
class OpenAIConfig:
    """Configuration for OpenAI SDK calls."""

    model: str = DEFAULT_MODEL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_retries: int = 2

    def __post_init__(self) -> None:
        _require_text(self.model, "model")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")


@dataclass(frozen=True)
class AgentSpec:
    """A lightweight local agent definition around one OpenAI model call."""

    name: str
    instructions: str
    tools: tuple[Callable[[str], dict[str, list[str]]], ...] = ()


@dataclass(frozen=True)
class AgentResult:
    agent_name: str
    output: str
    elapsed_ms: float
    tool_observations: dict[str, Any] = field(default_factory=dict)


def load_openai_client(timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> Any:
    """Lazy-load the SDK so this file can be imported without OpenAI installed."""

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("OpenAI SDK is not installed. Install it with: pip install openai") from exc

    return OpenAI(timeout=timeout_seconds)


def static_code_risk_scan(code: str) -> dict[str, list[str]]:
    """Deterministic local tool for common coding risk checks."""

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
    """Deterministic local tool for algorithmic complexity review."""

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


class OpenAICodingOrchestrator:
    """Small production-style orchestrator built on OpenAI Responses API calls."""

    def __init__(self, config: Optional[OpenAIConfig] = None, client: Optional[Any] = None) -> None:
        self.config = config or OpenAIConfig()
        self.client = client or load_openai_client(self.config.timeout_seconds)

    def run_single_agent(self, problem: CodingProblem) -> AgentResult:
        agent = AgentSpec(
            name="single_coding_solver",
            instructions=dedent(
                """
                You are a senior coding problem solver.

                Solve the user's problem with:
                - brief approach
                - production-quality code
                - tests
                - edge cases
                - time and space complexity

                Use the provided local observations as advisory review notes.
                """
            ).strip(),
            tools=(complexity_probe, static_code_risk_scan),
        )
        return self._run_agent(agent, problem.to_prompt())

    def run_pair_programming(self, problem: CodingProblem) -> dict[str, AgentResult]:
        design_agent = AgentSpec(
            name="algorithm_architect",
            instructions=dedent(
                """
                You are the Algorithm Architect.
                Produce implementation-ready design notes: assumptions, algorithm,
                data structures, edge cases, and complexity.
                """
            ).strip(),
            tools=(complexity_probe,),
        )
        implementation_agent = AgentSpec(
            name="implementation_engineer",
            instructions=dedent(
                """
                You are the Implementation Engineer.
                Convert the approved design into clean, typed, testable code.
                Include focused tests and a short usage note.
                """
            ).strip(),
            tools=(static_code_risk_scan,),
        )
        review_agent = AgentSpec(
            name="code_reviewer",
            instructions=dedent(
                """
                You are the Code Reviewer.
                Review correctness, security, maintainability, and test coverage.
                If needed, provide the corrected final implementation.
                """
            ).strip(),
            tools=(static_code_risk_scan,),
        )

        design = self._run_agent(design_agent, problem.to_prompt())
        implementation = self._run_agent(
            implementation_agent,
            _join_context(problem.to_prompt(), {"design_notes": design.output}),
        )
        review = self._run_agent(
            review_agent,
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
        max_refinement_rounds: int = 2,
    ) -> dict[str, Any]:
        requirements_agent = AgentSpec(
            name="requirements_analyst",
            instructions=(
                "Extract acceptance criteria, input/output rules, edge cases, "
                "non-goals, and testing strategy hints."
            ),
        )
        architecture_agent = AgentSpec(
            name="principal_architect",
            instructions=(
                "Create production-minded architecture and algorithm design with "
                "module boundaries, failure modes, and complexity."
            ),
            tools=(complexity_probe,),
        )
        implementation_agent = AgentSpec(
            name="senior_implementation_engineer",
            instructions=(
                "Build the implementation with clear functions, type hints, "
                "validation, and focused tests."
            ),
            tools=(static_code_risk_scan,),
        )
        correctness_reviewer = AgentSpec(
            name="correctness_reviewer",
            instructions="Review functional correctness and edge cases. Return concrete fixes.",
        )
        test_reviewer = AgentSpec(
            name="test_reviewer",
            instructions="Review test quality and missing coverage. Return concrete fixes.",
        )
        security_reviewer = AgentSpec(
            name="security_reliability_reviewer",
            instructions=(
                "Review security, reliability, performance, and maintainability risks. "
                "Return concrete fixes."
            ),
            tools=(static_code_risk_scan,),
        )
        refactor_agent = AgentSpec(
            name="refactor_engineer",
            instructions=(
                "Apply review feedback. Return a corrected implementation package "
                "with code, tests, and notes. If no changes are needed, say so clearly."
            ),
            tools=(static_code_risk_scan,),
        )
        final_agent = AgentSpec(
            name="final_handoff_writer",
            instructions=(
                "Create a polished final coding answer with code, tests, explanation, "
                "complexity analysis, run instructions, limitations, and production notes."
            ),
        )

        requirements = self._run_agent(requirements_agent, problem.to_prompt())
        architecture = self._run_agent(
            architecture_agent,
            _join_context(problem.to_prompt(), {"requirements": requirements.output}),
        )
        candidate = self._run_agent(
            implementation_agent,
            _join_context(
                problem.to_prompt(),
                {
                    "requirements": requirements.output,
                    "architecture": architecture.output,
                },
            ),
        )

        refinement_history: list[dict[str, AgentResult]] = []
        for round_index in range(max_refinement_rounds):
            review_context = _join_context(
                problem.to_prompt(),
                {
                    "requirements": requirements.output,
                    "architecture": architecture.output,
                    "candidate_code": candidate.output,
                    "round": str(round_index + 1),
                },
            )
            reviews = self._run_reviews_parallel(
                [correctness_reviewer, test_reviewer, security_reviewer],
                review_context,
            )
            candidate = self._run_agent(
                refactor_agent,
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
            final_agent,
            _join_context(
                problem.to_prompt(),
                {
                    "requirements": requirements.output,
                    "architecture": architecture.output,
                    "final_candidate": candidate.output,
                },
            ),
        )

        return {
            "requirements": requirements,
            "architecture": architecture,
            "final_candidate": candidate,
            "refinement_history": refinement_history,
            "final": final,
        }

    def _run_reviews_parallel(
        self,
        agents: list[AgentSpec],
        prompt: str,
    ) -> dict[str, AgentResult]:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(agents)) as executor:
            futures = {
                executor.submit(self._run_agent, agent, prompt): agent.name
                for agent in agents
            }
            return {
                agent_name: future.result()
                for future, agent_name in futures.items()
            }

    def _run_agent(self, agent: AgentSpec, prompt: str) -> AgentResult:
        tool_observations = _run_local_tools(agent.tools, prompt)
        enriched_prompt = _join_context(prompt, {"local_tool_observations": json.dumps(tool_observations)})
        started = time.perf_counter()
        output = self._create_response(agent.instructions, enriched_prompt)
        elapsed_ms = (time.perf_counter() - started) * 1_000
        logger.info(
            "openai_sdk.agent.completed",
            extra={"agent": agent.name, "elapsed_ms": round(elapsed_ms, 3)},
        )
        return AgentResult(
            agent_name=agent.name,
            output=output,
            elapsed_ms=round(elapsed_ms, 3),
            tool_observations=tool_observations,
        )

    def _create_response(self, instructions: str, user_input: str) -> str:
        last_error: Optional[Exception] = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.client.responses.create(
                    model=self.config.model,
                    instructions=instructions,
                    input=user_input,
                )
                return response.output_text
            except Exception as exc:  # Narrow to OpenAI SDK/API errors in a production package.
                last_error = exc
                if attempt >= self.config.max_retries:
                    break
                time.sleep(min(0.25 * (2**attempt), 2.0))

        raise RuntimeError("OpenAI response failed after retries") from last_error


def run_single_agent(problem: CodingProblem, config: Optional[OpenAIConfig] = None) -> AgentResult:
    return OpenAICodingOrchestrator(config).run_single_agent(problem)


def run_pair_programming(
    problem: CodingProblem,
    config: Optional[OpenAIConfig] = None,
) -> dict[str, AgentResult]:
    return OpenAICodingOrchestrator(config).run_pair_programming(problem)


def run_complex_delivery(
    problem: CodingProblem,
    config: Optional[OpenAIConfig] = None,
) -> dict[str, Any]:
    return OpenAICodingOrchestrator(config).run_complex_delivery(problem)


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
        Available OpenAI SDK coding examples:

        1. single
           One OpenAI Responses API call acts as a coding solver with local
           static-analysis observations.

        2. pair
           Local multi-agent workflow: architect -> implementation engineer -> reviewer.

        3. complex
           Production-style workflow:
           requirements -> architecture -> implementation -> parallel reviews
           -> refinement -> final handoff.

        Example commands:
            python ai/openai_sdk.py --mode guide
            python ai/openai_sdk.py --mode single --problem two-sum
            python ai/openai_sdk.py --mode pair --problem rate-limiter
            python ai/openai_sdk.py --mode complex --problem job-scheduler
        """
    ).strip()


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
        "no changes are needed",
        "already production-ready",
        "approved",
    )
    return any(marker in normalized for marker in approval_markers)


def _format_bullets(items: Iterable[str]) -> str:
    values = [item.strip() for item in items if item and item.strip()]
    return "\n".join(f"- {item}" for item in values) if values else "- None"


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _to_printable(result: Any) -> str:
    if isinstance(result, AgentResult):
        return result.output
    if isinstance(result, dict):
        printable = {
            key: value.output if isinstance(value, AgentResult) else value
            for key, value in result.items()
            if key != "refinement_history"
        }
        return json.dumps(printable, indent=2)
    return str(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenAI SDK coding-agent examples")
    parser.add_argument(
        "--mode",
        choices=("guide", "single", "pair", "complex"),
        default="guide",
        help="Which OpenAI SDK workflow to run.",
    )
    parser.add_argument(
        "--problem",
        choices=("two-sum", "rate-limiter", "job-scheduler"),
        default="two-sum",
        help="Problem sent to the selected workflow.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-retries", type=int, default=2)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    problem_factory: dict[str, Callable[[], CodingProblem]] = {
        "two-sum": example_basic_two_sum,
        "rate-limiter": example_intermediate_rate_limiter,
        "job-scheduler": example_advanced_job_scheduler,
    }
    problem = problem_factory[args.problem]()

    if args.mode == "guide":
        print(describe_available_examples())
        return

    config = OpenAIConfig(
        model=args.model,
        timeout_seconds=args.timeout,
        max_retries=args.max_retries,
    )
    orchestrator = OpenAICodingOrchestrator(config)

    if args.mode == "single":
        result = orchestrator.run_single_agent(problem)
    elif args.mode == "pair":
        result = orchestrator.run_pair_programming(problem)
    else:
        result = orchestrator.run_complex_delivery(problem)

    print(_to_printable(result))


if __name__ == "__main__":
    main()
