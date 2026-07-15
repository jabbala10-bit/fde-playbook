"""
Google ADK coding-agent examples from basic to advanced.

This file mirrors the CrewAI examples in this folder, but uses Google Agent
Development Kit (ADK) concepts:

1. Single LlmAgent for focused coding problem solving.
2. Sequential multi-agent workflow for design -> code -> review.
3. Complex multi-agent workflow with sequential, parallel, and loop agents.

Install and configure ADK before running real agent calls:
    pip install google-adk
    $env:GOOGLE_API_KEY = "..."

Guide mode works without ADK installed:
    python ai/google-adk.py --mode guide
"""

from __future__ import annotations

import argparse
import asyncio
import os
from dataclasses import dataclass, field
from enum import Enum
from textwrap import dedent
from typing import Any, Callable, Iterable, Literal, Optional


DEFAULT_MODEL = "gemini-2.5-flash"
RunMode = Literal["single", "pair", "complex"]


class Difficulty(str, Enum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass(frozen=True)
class CodingProblem:
    """Problem shape passed into ADK agents through the user message."""

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


def load_adk() -> dict[str, Any]:
    """Lazy-load ADK classes so guide/compile mode works without dependencies."""

    try:
        from google.adk.agents import Agent, LlmAgent, LoopAgent, ParallelAgent, SequentialAgent
        from google.adk.tools.tool_context import ToolContext
    except ImportError as exc:
        raise RuntimeError("Google ADK is not installed. Install it with: pip install google-adk") from exc

    return {
        "Agent": Agent,
        "LlmAgent": LlmAgent,
        "LoopAgent": LoopAgent,
        "ParallelAgent": ParallelAgent,
        "SequentialAgent": SequentialAgent,
        "ToolContext": ToolContext,
    }


def static_code_risk_scan(code: str) -> dict[str, list[str]]:
    """Scan code text for common correctness, safety, and maintainability risks."""

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
    """Estimate likely complexity concerns from a proposed algorithm/design."""

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


def exit_loop(tool_context: Any) -> dict[str, str]:
    """Signal an ADK LoopAgent to stop when the refinement is good enough."""

    tool_context.actions.escalate = True
    tool_context.actions.skip_summarization = True
    return {"status": "loop_exit_requested"}


def build_single_agent(
    *,
    model: str = DEFAULT_MODEL,
) -> Any:
    """Build a basic single-agent coding assistant."""

    LlmAgent = load_adk()["LlmAgent"]
    return LlmAgent(
        name="single_coding_solver",
        model=model,
        description="Solves focused coding problems with code, tests, and explanation.",
        instruction=dedent(
            """
            You are a senior coding problem solver.

            Given the user's problem:
            1. Clarify assumptions only when the prompt is materially ambiguous.
            2. Explain the approach briefly.
            3. Write clean, idiomatic, production-minded code.
            4. Include tests for normal, edge, and failure cases.
            5. Include time and space complexity.

            Use tools:
            - complexity_probe before selecting the final approach.
            - static_code_risk_scan before finalizing code.
            """
        ).strip(),
        tools=[complexity_probe, static_code_risk_scan],
        output_key="single_agent_solution",
    )


def build_pair_programming_agent(
    *,
    model: str = DEFAULT_MODEL,
) -> Any:
    """Build an intermediate sequential ADK workflow."""

    adk = load_adk()
    LlmAgent = adk["LlmAgent"]
    SequentialAgent = adk["SequentialAgent"]

    design_agent = LlmAgent(
        name="algorithm_architect",
        model=model,
        description="Creates implementation-ready algorithm and design notes.",
        instruction=dedent(
            """
            You are the Algorithm Architect.
            Read the user's coding problem and produce:
            - assumptions
            - algorithm choice
            - data structures
            - edge cases
            - time and space complexity

            Use complexity_probe to check the selected design.
            Output only the design document.
            """
        ).strip(),
        tools=[complexity_probe],
        output_key="design_notes",
    )

    implementation_agent = LlmAgent(
        name="implementation_engineer",
        model=model,
        description="Implements clean code from design notes.",
        instruction=dedent(
            """
            You are the Implementation Engineer.

            Problem:
            {user_problem}

            Design notes:
            {design_notes}

            Write the final code in the requested language.
            Include public type hints, focused helper functions, and tests.
            Output only the implementation package.
            """
        ).strip(),
        tools=[static_code_risk_scan],
        output_key="implementation_package",
    )

    review_agent = LlmAgent(
        name="code_reviewer",
        model=model,
        description="Reviews implementation and returns final corrected answer.",
        instruction=dedent(
            """
            You are the Code Reviewer.

            Design notes:
            {design_notes}

            Implementation:
            {implementation_package}

            Review correctness, security, edge cases, maintainability, and tests.
            Use static_code_risk_scan. If issues exist, provide a corrected final
            version. If no material issues exist, approve and restate the final answer.
            """
        ).strip(),
        tools=[static_code_risk_scan],
        output_key="reviewed_solution",
    )

    return SequentialAgent(
        name="pair_programming_pipeline",
        description="Runs design, implementation, and review in a strict order.",
        sub_agents=[design_agent, implementation_agent, review_agent],
    )


def build_complex_multi_agent(
    *,
    model: str = DEFAULT_MODEL,
    refinement_iterations: int = 2,
) -> Any:
    """
    Build an advanced ADK coding workflow.

    Flow:
    requirements -> architecture -> implementation -> parallel quality review
    -> iterative refactor loop -> final handoff.
    """

    adk = load_adk()
    Agent = adk["Agent"]
    LlmAgent = adk["LlmAgent"]
    LoopAgent = adk["LoopAgent"]
    ParallelAgent = adk["ParallelAgent"]
    SequentialAgent = adk["SequentialAgent"]

    requirements_agent = LlmAgent(
        name="requirements_analyst",
        model=model,
        description="Extracts acceptance criteria and non-goals.",
        instruction=dedent(
            """
            You are the Requirements Analyst.
            
            User problem:
            {user_problem}
            
            Convert the user's coding problem into:
            - acceptance criteria
            - input/output rules
            - edge cases
            - non-goals
            - test strategy hints

            Output only the requirements document.
            """
        ).strip(),
        output_key="requirements",
    )

    architecture_agent = LlmAgent(
        name="principal_architect",
        model=model,
        description="Creates production-minded architecture and algorithm design.",
        instruction=dedent(
            """
            You are the Principal Architect.

            Requirements:
            {requirements}

            Produce an implementation-ready technical design with module boundaries,
            algorithm choice, data structures, failure modes, and complexity.
            Use complexity_probe before finalizing.
            """
        ).strip(),
        tools=[complexity_probe],
        output_key="architecture",
    )

    implementation_agent = LlmAgent(
        name="senior_implementation_engineer",
        model=model,
        description="Builds the implementation.",
        instruction=dedent(
            """
            You are the Senior Implementation Engineer.

            Requirements:
            {requirements}

            Architecture:
            {architecture}

            Write the implementation with clear functions, type hints, validation,
            and focused tests. Keep it easy to move into a real codebase.
            """
        ).strip(),
        tools=[static_code_risk_scan],
        output_key="candidate_code",
    )

    correctness_reviewer = LlmAgent(
        name="correctness_reviewer",
        model=model,
        description="Reviews functional correctness and edge cases.",
        instruction=dedent(
            """
            Review this implementation for correctness and edge cases.

            Requirements:
            {requirements}

            Candidate code:
            {candidate_code}

            Return concrete findings and required fixes.
            """
        ).strip(),
        output_key="correctness_review",
    )

    test_reviewer = LlmAgent(
        name="test_reviewer",
        model=model,
        description="Reviews test quality and missing coverage.",
        instruction=dedent(
            """
            Review this implementation's test coverage.

            Requirements:
            {requirements}

            Candidate code:
            {candidate_code}

            Return missing tests, weak assertions, and suggested test cases.
            """
        ).strip(),
        output_key="test_review",
    )

    security_reviewer = LlmAgent(
        name="security_reliability_reviewer",
        model=model,
        description="Reviews security, reliability, and operational risk.",
        instruction=dedent(
            """
            Review this implementation for security, reliability, performance,
            and maintainability risks.

            Candidate code:
            {candidate_code}

            Use static_code_risk_scan and return concrete fixes.
            """
        ).strip(),
        tools=[static_code_risk_scan],
        output_key="security_review",
    )

    parallel_review_agent = ParallelAgent(
        name="parallel_quality_review",
        description="Runs correctness, testing, and security reviews concurrently.",
        sub_agents=[correctness_reviewer, test_reviewer, security_reviewer],
    )

    refactor_agent = LlmAgent(
        name="refactor_engineer",
        model=model,
        description="Applies review feedback and improves candidate code.",
        instruction=dedent(
            """
            You are the Refactor Engineer.

            Candidate code:
            {candidate_code}

            Correctness review:
            {correctness_review}

            Test review:
            {test_review}

            Security review:
            {security_review}

            If the code is already production-ready, call exit_loop.
            Otherwise, produce a corrected implementation package and include tests.
            """
        ).strip(),
        tools=[static_code_risk_scan, exit_loop],
        output_key="candidate_code",
    )

    final_reviewer = LlmAgent(
        name="final_handoff_writer",
        model=model,
        description="Creates the final polished coding answer.",
        instruction=dedent(
            """
            You are the Final Handoff Writer.

            Requirements:
            {requirements}

            Architecture:
            {architecture}

            Final candidate:
            {candidate_code}

            Produce the final answer with:
            - code
            - tests
            - explanation
            - complexity analysis
            - run instructions
            - limitations and production notes
            """
        ).strip(),
        output_key="final_solution",
    )

    refinement_loop = LoopAgent(
        name="review_refactor_loop",
        description="Iteratively applies review feedback until acceptable or max iterations is reached.",
        sub_agents=[parallel_review_agent, refactor_agent],
        max_iterations=refinement_iterations,
    )

    delivery_pipeline = SequentialAgent(
        name="complex_coding_delivery_pipeline",
        description="Production-style coding workflow for larger problems.",
        sub_agents=[
            requirements_agent,
            architecture_agent,
            implementation_agent,
            refinement_loop,
            final_reviewer,
        ],
    )

    return Agent(
        name="root_coding_agent",
        model=model,
        description="Routes coding work through a complex multi-agent ADK delivery pipeline.",
        instruction=dedent(
            """
            You are the root coding orchestrator. Delegate coding implementation,
            review, and final handoff work to the complex delivery pipeline.
            """
        ).strip(),
        sub_agents=[delivery_pipeline],
    )


def build_agent(mode: RunMode, *, model: str = DEFAULT_MODEL) -> Any:
    if mode == "single":
        return build_single_agent(model=model)
    if mode == "pair":
        return build_pair_programming_agent(model=model)
    if mode == "complex":
        return build_complex_multi_agent(model=model)
    raise ValueError("mode must be one of: single, pair, complex")


async def run_agent_async(
    agent: Any,
    problem: CodingProblem,
    *,
    app_name: str = "adk_coding_examples",
    user_id: str = "local-user",
    session_id: str = "local-session",
) -> str:
    """
    Run an ADK agent directly from Python.

    For larger ADK projects, you can also expose a module-level `root_agent` and
    use the ADK CLI/web runtime.
    """

    try:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("ADK runtime dependencies are unavailable.") from exc

    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
        state={"user_problem": problem.to_prompt()},
    )

    runner = Runner(agent=agent, app_name=app_name, session_service=session_service)
    message = types.Content(role="user", parts=[types.Part(text=problem.to_prompt())])
    final_response = "No final response received."

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_response = event.content.parts[0].text or final_response

    return final_response


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
        Available Google ADK coding examples:

        1. single
           One LlmAgent solves a focused problem using static analysis tools.

        2. pair
           Sequential workflow: architect -> implementation engineer -> reviewer.

        3. complex
           Root agent delegates to a production-style pipeline:
           requirements -> architecture -> implementation -> parallel quality review
           -> looped refactor -> final handoff.

        Example commands:
            python ai/google-adk.py --mode guide
            python ai/google-adk.py --mode single --problem two-sum
            python ai/google-adk.py --mode pair --problem rate-limiter
            python ai/google-adk.py --mode complex --problem job-scheduler
        """
    ).strip()


def _format_bullets(items: Iterable[str]) -> str:
    values = [item.strip() for item in items if item and item.strip()]
    return "\n".join(f"- {item}" for item in values) if values else "- None"


def main() -> None:
    parser = argparse.ArgumentParser(description="Google ADK coding-agent examples")
    parser.add_argument(
        "--mode",
        choices=("guide", "single", "pair", "complex"),
        default="guide",
        help="Which ADK example to run.",
    )
    parser.add_argument(
        "--problem",
        choices=("two-sum", "rate-limiter", "job-scheduler"),
        default="two-sum",
        help="Problem sent to the selected ADK agent.",
    )
    parser.add_argument("--model", default=os.getenv("GOOGLE_ADK_MODEL", DEFAULT_MODEL))
    args = parser.parse_args()

    problem_factory: dict[str, Callable[[], CodingProblem]] = {
        "two-sum": example_basic_two_sum,
        "rate-limiter": example_intermediate_rate_limiter,
        "job-scheduler": example_advanced_job_scheduler,
    }
    problem = problem_factory[args.problem]()

    if args.mode == "guide":
        print(describe_available_examples())
        return

    agent = build_agent(args.mode, model=args.model)
    print(asyncio.run(run_agent_async(agent, problem)))


if __name__ == "__main__":
    main()
