"""
OpenClaw coding-agent examples from basic to advanced.

OpenClaw is primarily a local-first CLI/Gateway assistant, not a Python package.
This module therefore uses Python as an orchestration layer around the documented
OpenClaw CLI:

    openclaw agent --message "..." --thinking high

Install and onboard OpenClaw before running live calls:
    npm install -g openclaw@latest
    openclaw onboard --install-daemon
    openclaw gateway status

Guide and dry-run modes work without OpenClaw installed:
    python ai/openclaw.py --mode guide
    python ai/openclaw.py --mode complex --dry-run
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from textwrap import dedent
from typing import Any, Callable, Iterable, Optional


DEFAULT_THINKING = "high"
DEFAULT_TIMEOUT_SECONDS = 180.0
logger = logging.getLogger(__name__)


class Difficulty(str, Enum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass(frozen=True)
class CodingProblem:
    """Structured coding-problem input for OpenClaw prompt orchestration."""

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
class OpenClawConfig:
    """Runtime settings for OpenClaw CLI calls."""

    binary: str = "openclaw"
    thinking: str = DEFAULT_THINKING
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    dry_run: bool = False

    def __post_init__(self) -> None:
        _require_text(self.binary, "binary")
        _require_text(self.thinking, "thinking")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True)
class ClawAgentSpec:
    """Local role wrapper for one OpenClaw assistant call."""

    name: str
    instructions: str
    local_tools: tuple[Callable[[str], dict[str, list[str]]], ...] = ()


@dataclass(frozen=True)
class ClawResult:
    agent_name: str
    output: str
    elapsed_ms: float
    command: tuple[str, ...]
    local_observations: dict[str, Any] = field(default_factory=dict)


def static_code_risk_scan(code: str) -> dict[str, list[str]]:
    """Deterministic local check for common coding and operational risks."""

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
    """Deterministic local check for algorithmic complexity risks."""

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


class OpenClawCodingOrchestrator:
    """Production-minded Python wrapper around OpenClaw CLI agent calls."""

    def __init__(self, config: Optional[OpenClawConfig] = None) -> None:
        self.config = config or OpenClawConfig()

    def run_single_agent(self, problem: CodingProblem) -> ClawResult:
        agent = ClawAgentSpec(
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

                Treat local observations as advisory checks before finalizing.
                """
            ).strip(),
            local_tools=(complexity_probe, static_code_risk_scan),
        )
        return self._run_claw_agent(agent, problem.to_prompt())

    def run_pair_programming(self, problem: CodingProblem) -> dict[str, ClawResult]:
        architect = ClawAgentSpec(
            name="algorithm_architect",
            instructions=(
                "Create implementation-ready design notes: assumptions, algorithm, "
                "data structures, edge cases, and complexity."
            ),
            local_tools=(complexity_probe,),
        )
        engineer = ClawAgentSpec(
            name="implementation_engineer",
            instructions=(
                "Convert the approved design into clean, typed, testable code. "
                "Include focused tests and usage notes."
            ),
            local_tools=(static_code_risk_scan,),
        )
        reviewer = ClawAgentSpec(
            name="code_reviewer",
            instructions=(
                "Review correctness, security, maintainability, and test coverage. "
                "If needed, provide a corrected final implementation."
            ),
            local_tools=(static_code_risk_scan,),
        )

        design = self._run_claw_agent(architect, problem.to_prompt())
        implementation = self._run_claw_agent(
            engineer,
            _join_context(problem.to_prompt(), {"design_notes": design.output}),
        )
        review = self._run_claw_agent(
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
        max_refinement_rounds: int = 2,
    ) -> dict[str, Any]:
        requirements_agent = ClawAgentSpec(
            name="requirements_analyst",
            instructions=(
                "Extract acceptance criteria, input/output rules, edge cases, "
                "non-goals, and testing strategy hints."
            ),
        )
        architecture_agent = ClawAgentSpec(
            name="principal_architect",
            instructions=(
                "Create production-minded architecture and algorithm design with "
                "module boundaries, failure modes, and complexity."
            ),
            local_tools=(complexity_probe,),
        )
        implementation_agent = ClawAgentSpec(
            name="senior_implementation_engineer",
            instructions=(
                "Build the implementation with clear functions, type hints, "
                "validation, and focused tests."
            ),
            local_tools=(static_code_risk_scan,),
        )
        correctness_reviewer = ClawAgentSpec(
            name="correctness_reviewer",
            instructions="Review functional correctness and edge cases. Return concrete fixes.",
        )
        test_reviewer = ClawAgentSpec(
            name="test_reviewer",
            instructions="Review test quality and missing coverage. Return concrete fixes.",
        )
        security_reviewer = ClawAgentSpec(
            name="security_reliability_reviewer",
            instructions=(
                "Review security, reliability, performance, and maintainability risks. "
                "Return concrete fixes."
            ),
            local_tools=(static_code_risk_scan,),
        )
        refactor_agent = ClawAgentSpec(
            name="refactor_engineer",
            instructions=(
                "Apply review feedback. Return corrected code, tests, and notes. "
                "If no changes are needed, say 'approved: no changes are needed'."
            ),
            local_tools=(static_code_risk_scan,),
        )
        final_agent = ClawAgentSpec(
            name="final_handoff_writer",
            instructions=(
                "Create a polished final coding answer with code, tests, explanation, "
                "complexity analysis, run instructions, limitations, and production notes."
            ),
        )

        requirements = self._run_claw_agent(requirements_agent, problem.to_prompt())
        architecture = self._run_claw_agent(
            architecture_agent,
            _join_context(problem.to_prompt(), {"requirements": requirements.output}),
        )
        candidate = self._run_claw_agent(
            implementation_agent,
            _join_context(
                problem.to_prompt(),
                {
                    "requirements": requirements.output,
                    "architecture": architecture.output,
                },
            ),
        )

        refinement_history: list[dict[str, ClawResult]] = []
        for round_number in range(1, max_refinement_rounds + 1):
            review_context = _join_context(
                problem.to_prompt(),
                {
                    "requirements": requirements.output,
                    "architecture": architecture.output,
                    "candidate_code": candidate.output,
                    "round": str(round_number),
                },
            )
            reviews = self._run_reviews_parallel(
                [correctness_reviewer, test_reviewer, security_reviewer],
                review_context,
            )
            candidate = self._run_claw_agent(
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

        final = self._run_claw_agent(
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
        agents: list[ClawAgentSpec],
        prompt: str,
    ) -> dict[str, ClawResult]:
        if self.config.dry_run:
            return {agent.name: self._run_claw_agent(agent, prompt) for agent in agents}

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(agents)) as executor:
            futures = {
                executor.submit(self._run_claw_agent, agent, prompt): agent.name
                for agent in agents
            }
            return {
                agent_name: future.result()
                for future, agent_name in futures.items()
            }

    def _run_claw_agent(self, agent: ClawAgentSpec, prompt: str) -> ClawResult:
        local_observations = _run_local_tools(agent.local_tools, prompt)
        full_prompt = _build_agent_prompt(agent, prompt, local_observations)
        command = (
            self.config.binary,
            "agent",
            "--message",
            full_prompt,
            "--thinking",
            self.config.thinking,
        )

        started = time.perf_counter()
        if self.config.dry_run:
            output = f"[dry-run] Would run {agent.name} with OpenClaw CLI."
        else:
            output = self._invoke_openclaw(command)
        elapsed_ms = (time.perf_counter() - started) * 1_000

        logger.info(
            "openclaw.agent.completed",
            extra={"agent": agent.name, "elapsed_ms": round(elapsed_ms, 3)},
        )
        return ClawResult(
            agent_name=agent.name,
            output=output,
            elapsed_ms=round(elapsed_ms, 3),
            command=command,
            local_observations=local_observations,
        )

    def _invoke_openclaw(self, command: tuple[str, ...]) -> str:
        if shutil.which(self.config.binary) is None:
            raise RuntimeError(
                f"OpenClaw CLI '{self.config.binary}' was not found. "
                "Install OpenClaw and run onboarding first, or use --dry-run."
            )

        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=self.config.timeout_seconds,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            raise RuntimeError(f"OpenClaw command failed: {stderr or completed.returncode}")
        return completed.stdout.strip()


def create_coding_skill_markdown() -> str:
    """Return an OpenClaw skill file for coding-review workflows."""

    return dedent(
        """
        ---
        name: production-coding-review
        description: Use for coding tasks that need design, implementation, tests, and security review.
        ---

        # Production Coding Review

        When solving a coding task:

        1. Restate the problem and constraints.
        2. Choose a simple correct design before writing code.
        3. Include typed, maintainable code.
        4. Include focused tests for success, edge, and failure cases.
        5. Review security, reliability, and operational risks.
        6. End with complexity analysis and run instructions.

        Prefer explicit assumptions over silent guesses. Do not execute unsafe shell
        commands unless the operator has approved the action and scope.
        """
    ).strip()


def create_safe_multi_agent_config_example() -> str:
    """Return a JSON5 config snippet for isolated OpenClaw coding agents."""

    return dedent(
        """
        {
          agents: {
            defaults: {
              sandbox: {
                mode: "all",
                scope: "agent"
              },
              skills: ["production-coding-review"]
            },
            list: [
              {
                id: "coding-architect",
                workspace: "~/.openclaw/workspaces/coding-architect",
                skills: ["production-coding-review"]
              },
              {
                id: "coding-reviewer",
                workspace: "~/.openclaw/workspaces/coding-reviewer",
                skills: ["production-coding-review"]
              },
              {
                id: "locked-down",
                workspace: "~/.openclaw/workspaces/locked-down",
                skills: []
              }
            ]
          }
        }
        """
    ).strip()


def run_single_agent(problem: CodingProblem, config: Optional[OpenClawConfig] = None) -> ClawResult:
    return OpenClawCodingOrchestrator(config).run_single_agent(problem)


def run_pair_programming(
    problem: CodingProblem,
    config: Optional[OpenClawConfig] = None,
) -> dict[str, ClawResult]:
    return OpenClawCodingOrchestrator(config).run_pair_programming(problem)


def run_complex_delivery(
    problem: CodingProblem,
    config: Optional[OpenClawConfig] = None,
) -> dict[str, Any]:
    return OpenClawCodingOrchestrator(config).run_complex_delivery(problem)


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
        Available OpenClaw coding examples:

        1. single
           One OpenClaw assistant call solves a focused coding problem.

        2. pair
           Local multi-agent workflow: architect -> implementation engineer -> reviewer.

        3. complex
           Production-style workflow:
           requirements -> architecture -> implementation -> parallel reviews
           -> refinement -> final handoff.

        4. skill
           Print a reusable OpenClaw SKILL.md for production coding review.

        5. config
           Print a safe JSON5 multi-agent config example with sandboxing and skill allowlists.

        Example commands:
            python ai/openclaw.py --mode guide
            python ai/openclaw.py --mode single --problem two-sum --dry-run
            python ai/openclaw.py --mode pair --problem rate-limiter --dry-run
            python ai/openclaw.py --mode complex --problem job-scheduler --dry-run
            python ai/openclaw.py --mode skill
            python ai/openclaw.py --mode config
        """
    ).strip()


def _build_agent_prompt(
    agent: ClawAgentSpec,
    prompt: str,
    local_observations: dict[str, Any],
) -> str:
    return _join_context(
        prompt,
        {
            "role": agent.name,
            "instructions": agent.instructions,
            "local_observations": json.dumps(local_observations, indent=2),
        },
    )


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


def _to_printable(result: Any, *, show_commands: bool = False) -> str:
    if isinstance(result, ClawResult):
        printable = _result_to_dict(result, show_commands=show_commands)
        if show_commands:
            return json.dumps(printable, indent=2)
        return result.output

    if isinstance(result, dict):
        printable = {
            key: _result_to_dict(value, show_commands=show_commands)
            for key, value in result.items()
            if isinstance(value, ClawResult)
        }
        return json.dumps(printable, indent=2)
    return str(result)


def _result_to_dict(result: ClawResult, *, show_commands: bool) -> dict[str, Any]:
    data: dict[str, Any] = {
        "agent": result.agent_name,
        "output": result.output,
        "local_observations": result.local_observations,
    }
    if show_commands:
        data["command"] = [
            part if index != 3 else "<prompt omitted>"
            for index, part in enumerate(result.command)
        ]
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenClaw coding-agent examples")
    parser.add_argument(
        "--mode",
        choices=("guide", "single", "pair", "complex", "skill", "config"),
        default="guide",
        help="Which OpenClaw workflow or artifact to run.",
    )
    parser.add_argument(
        "--problem",
        choices=("two-sum", "rate-limiter", "job-scheduler"),
        default="two-sum",
        help="Problem sent to the selected workflow.",
    )
    parser.add_argument("--binary", default="openclaw")
    parser.add_argument("--thinking", default=DEFAULT_THINKING)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--dry-run", action="store_true", help="Do not invoke the OpenClaw CLI.")
    parser.add_argument("--show-commands", action="store_true", help="Include CLI command metadata.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    if args.mode == "guide":
        print(describe_available_examples())
        return
    if args.mode == "skill":
        print(create_coding_skill_markdown())
        return
    if args.mode == "config":
        print(create_safe_multi_agent_config_example())
        return

    problem_factory: dict[str, Callable[[], CodingProblem]] = {
        "two-sum": example_basic_two_sum,
        "rate-limiter": example_intermediate_rate_limiter,
        "job-scheduler": example_advanced_job_scheduler,
    }
    problem = problem_factory[args.problem]()
    config = OpenClawConfig(
        binary=args.binary,
        thinking=args.thinking,
        timeout_seconds=args.timeout,
        dry_run=args.dry_run,
    )
    orchestrator = OpenClawCodingOrchestrator(config)

    if args.mode == "single":
        result = orchestrator.run_single_agent(problem)
    elif args.mode == "pair":
        result = orchestrator.run_pair_programming(problem)
    else:
        result = orchestrator.run_complex_delivery(problem)

    print(_to_printable(result, show_commands=args.show_commands))


if __name__ == "__main__":
    main()
