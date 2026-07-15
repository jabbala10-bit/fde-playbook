"""
CrewAI problem-solving patterns from basic to advanced.

This module shows three practical coding-agent workflows:
1. Single-agent coding assistant for focused problems.
2. Multi-agent pair-programming crew for design, implementation, and review.
3. Complex multi-agent coding crew for production-style feature delivery.

CrewAI must be installed to execute the crews:
    pip install "crewai[tools]"

Set your model credentials before running, for example:
    $env:OPENAI_API_KEY = "..."
    $env:OPENAI_MODEL_NAME = "gpt-4o-mini"

The code uses lazy imports so the file can still be imported, compiled, and studied
when CrewAI is not installed.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from enum import Enum
from textwrap import dedent
from typing import Any, Callable, Iterable, Literal, Optional


CrewProcess = Literal["sequential", "hierarchical"]


class Difficulty(str, Enum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass(frozen=True)
class CodingProblem:
    """Structured input shared by all example crews."""

    title: str
    prompt: str
    language: str = "Python"
    difficulty: Difficulty = Difficulty.BASIC
    constraints: tuple[str, ...] = field(default_factory=tuple)
    expected_deliverables: tuple[str, ...] = (
        "working solution",
        "explanation",
        "complexity analysis",
        "test cases",
    )

    def as_inputs(self) -> dict[str, str]:
        return {
            "title": self.title,
            "prompt": self.prompt,
            "language": self.language,
            "difficulty": self.difficulty.value,
            "constraints": _format_bullets(self.constraints),
            "expected_deliverables": _format_bullets(self.expected_deliverables),
        }


def load_crewai() -> tuple[Any, Any, Any, Any]:
    """Import CrewAI only when a real crew needs to be constructed."""

    try:
        from crewai import Agent, Crew, Process, Task
    except ImportError as exc:
        raise RuntimeError(
            'CrewAI is not installed. Install it with: pip install "crewai[tools]"'
        ) from exc

    return Agent, Crew, Process, Task


def create_static_code_tools() -> list[Any]:
    """
    Create lightweight custom CrewAI tools for coding crews.

    These tools do not execute arbitrary code. They provide safer static checks and
    deterministic guidance that agents can call while drafting a solution.
    """

    try:
        from crewai.tools import tool
    except ImportError as exc:
        raise RuntimeError(
            'CrewAI tools are not installed. Install them with: pip install "crewai[tools]"'
        ) from exc

    @tool("static_code_risk_scan")
    def static_code_risk_scan(code: str) -> str:
        """Scan code text for common safety, maintainability, and production risks."""
        risks: list[str] = []
        lowered = code.lower()
        risky_terms = {
            "eval(": "Avoid eval; parse input explicitly or use a constrained interpreter.",
            "exec(": "Avoid exec; prefer explicit functions and whitelisted behavior.",
            "shell=true": "Avoid shell=True unless command input is fully controlled.",
            "password": "Check for hard-coded secrets or sensitive identifiers.",
            "api_key": "Check for hard-coded API keys; load secrets from environment or a vault.",
            "todo": "Resolve TODOs or convert them into tracked follow-up work.",
        }

        for term, message in risky_terms.items():
            if term in lowered:
                risks.append(f"- {message}")

        if "def test_" not in lowered and "pytest" not in lowered:
            risks.append("- Add focused tests for success, edge, and failure cases.")
        if "logging" not in lowered:
            risks.append("- Add structured logging where operational failures matter.")
        if "typing" not in lowered and "from __future__ import annotations" not in lowered:
            risks.append("- Add type hints for public functions and data structures.")

        return "\n".join(risks) if risks else "No obvious static risks found."

    @tool("complexity_probe")
    def complexity_probe(solution_plan: str) -> str:
        """Estimate likely complexity concerns from a proposed algorithm or design."""
        plan = solution_plan.lower()
        observations: list[str] = []

        if "nested loop" in plan or "for each" in plan:
            observations.append("- Watch for O(n^2) behavior; justify it or improve it.")
        if "sort" in plan:
            observations.append("- Sorting suggests at least O(n log n) time.")
        if "hash" in plan or "dict" in plan or "map" in plan:
            observations.append("- Hash maps can reduce lookup cost to average O(1).")
        if "recursion" in plan:
            observations.append("- Define recursion depth and base cases clearly.")
        if "cache" in plan or "memo" in plan:
            observations.append("- Document cache key design and memory growth.")

        return "\n".join(observations) if observations else "No major complexity flags detected."

    return [static_code_risk_scan, complexity_probe]


def build_single_agent_coding_crew(
    problem: CodingProblem,
    *,
    llm: Optional[str] = None,
    verbose: bool = True,
) -> Any:
    """Build a simple one-agent crew for focused problem solving."""

    validate_problem(problem)
    Agent, Crew, Process, Task = load_crewai()
    tools = create_static_code_tools()

    solver = Agent(
        role="Senior Coding Problem Solver",
        goal=(
            "Solve coding problems clearly, correctly, and with production-minded "
            "edge-case handling."
        ),
        backstory=(
            "You are a careful software engineer who explains tradeoffs, writes "
            "small testable code, and avoids cleverness unless it materially helps."
        ),
        tools=tools,
        llm=llm,
        verbose=verbose,
        reasoning=True,
        max_reasoning_attempts=2,
        max_iter=12,
        max_retry_limit=2,
    )

    solve_task = Task(
        description=dedent(
            """
            Solve the coding problem.

            Title: {title}
            Difficulty: {difficulty}
            Language: {language}

            Problem:
            {prompt}

            Constraints:
            {constraints}

            Expected deliverables:
            {expected_deliverables}

            Use the static_code_risk_scan and complexity_probe tools before finalizing.
            """
        ).strip(),
        expected_output=(
            "A complete answer with approach, production-quality code, complexity "
            "analysis, tests, and notable edge cases."
        ),
        agent=solver,
    )

    return Crew(
        agents=[solver],
        tasks=[solve_task],
        process=Process.sequential,
        verbose=verbose,
    )


def build_pair_programming_crew(
    problem: CodingProblem,
    *,
    llm: Optional[str] = None,
    verbose: bool = True,
) -> Any:
    """
    Build an intermediate multi-agent crew.

    The agents work sequentially: design first, implementation second, review last.
    Later tasks receive earlier task outputs through CrewAI task context.
    """

    validate_problem(problem)
    Agent, Crew, Process, Task = load_crewai()
    tools = create_static_code_tools()

    architect = Agent(
        role="Algorithm Architect",
        goal="Design a correct, efficient, and explainable solution strategy.",
        backstory=(
            "You specialize in turning ambiguous coding prompts into precise "
            "requirements, invariants, and algorithm choices."
        ),
        tools=[tools[1]],
        llm=llm,
        verbose=verbose,
        reasoning=True,
        max_reasoning_attempts=2,
    )
    developer = Agent(
        role="Implementation Engineer",
        goal="Write clean, idiomatic, testable code from the approved design.",
        backstory=(
            "You write production-grade code with clear functions, type hints, "
            "input validation, and meaningful tests."
        ),
        tools=tools,
        llm=llm,
        verbose=verbose,
        max_iter=16,
    )
    reviewer = Agent(
        role="Code Reviewer",
        goal="Find correctness, edge-case, security, and maintainability issues.",
        backstory=(
            "You review code like a senior engineer: specific, practical, and "
            "focused on failures that would matter in real use."
        ),
        tools=[tools[0]],
        llm=llm,
        verbose=verbose,
        max_iter=10,
    )

    design_task = Task(
        description=dedent(
            """
            Create a solution design for:
            {title}

            Problem:
            {prompt}

            Language: {language}
            Difficulty: {difficulty}
            Constraints:
            {constraints}

            Include assumptions, algorithm choice, data structures, edge cases,
            and time/space complexity.
            """
        ).strip(),
        expected_output="A concise implementation-ready design document.",
        agent=architect,
    )
    implementation_task = Task(
        description=dedent(
            """
            Implement the approved design in {language}.

            Include:
            - final code
            - focused tests
            - short explanation
            - complexity analysis
            """
        ).strip(),
        expected_output="Production-quality code with tests and explanation.",
        agent=developer,
        context=[design_task],
    )
    review_task = Task(
        description=dedent(
            """
            Review the implementation for correctness, security, edge cases,
            readability, and test coverage. If issues exist, provide a corrected
            final version.
            """
        ).strip(),
        expected_output=(
            "Review findings followed by the final corrected code and tests."
        ),
        agent=reviewer,
        context=[design_task, implementation_task],
    )

    return Crew(
        agents=[architect, developer, reviewer],
        tasks=[design_task, implementation_task, review_task],
        process=Process.sequential,
        verbose=verbose,
    )


def build_complex_multi_agent_coding_crew(
    problem: CodingProblem,
    *,
    llm: Optional[str] = None,
    process: CrewProcess = "sequential",
    manager_llm: Optional[str] = None,
    verbose: bool = True,
) -> Any:
    """
    Build an advanced crew for production-style coding delivery.

    Use sequential mode for deterministic learning. Use hierarchical mode when you
    want a manager model to coordinate task assignment and validation.
    """

    validate_problem(problem)
    Agent, Crew, Process, Task = load_crewai()
    tools = create_static_code_tools()

    product_analyst = Agent(
        role="Product and Requirements Analyst",
        goal="Convert a problem statement into crisp acceptance criteria.",
        backstory="You remove ambiguity before implementation starts.",
        llm=llm,
        verbose=verbose,
        reasoning=True,
    )
    system_architect = Agent(
        role="Principal Software Architect",
        goal="Design a robust module boundary and algorithmic approach.",
        backstory="You design systems that are simple first and scalable when needed.",
        tools=[tools[1]],
        llm=llm,
        verbose=verbose,
        reasoning=True,
    )
    implementation_engineer = Agent(
        role="Senior Implementation Engineer",
        goal="Build the solution with clean code, types, and tests.",
        backstory="You turn architecture into maintainable, working code.",
        tools=tools,
        llm=llm,
        verbose=verbose,
        max_iter=20,
        max_retry_limit=3,
    )
    test_engineer = Agent(
        role="Test Engineer",
        goal="Design high-signal tests for correctness, boundaries, and regressions.",
        backstory="You think in examples, failure modes, and reproducibility.",
        llm=llm,
        verbose=verbose,
    )
    security_reviewer = Agent(
        role="Security and Reliability Reviewer",
        goal="Identify unsafe behavior, operational risks, and resilience gaps.",
        backstory="You catch issues before they become production incidents.",
        tools=[tools[0]],
        llm=llm,
        verbose=verbose,
    )
    docs_engineer = Agent(
        role="Technical Documentation Engineer",
        goal="Create concise usage notes and maintenance guidance.",
        backstory="You make code easy for the next engineer to run and evolve.",
        llm=llm,
        verbose=verbose,
    )

    requirements_task = Task(
        description=dedent(
            """
            Analyze the coding problem and produce acceptance criteria.

            Title: {title}
            Difficulty: {difficulty}
            Language: {language}

            Problem:
            {prompt}

            Constraints:
            {constraints}
            """
        ).strip(),
        expected_output=(
            "Acceptance criteria, input/output rules, edge cases, and non-goals."
        ),
        agent=product_analyst,
    )
    architecture_task = Task(
        description=(
            "Create a technical design that satisfies the acceptance criteria. "
            "Include algorithm choice, data structures, failure modes, and complexity."
        ),
        expected_output="Implementation-ready architecture and algorithm design.",
        agent=system_architect,
        context=[requirements_task],
    )
    implementation_task = Task(
        description=(
            "Implement the solution in {language}. Keep the code production-grade, "
            "readable, typed, and easy to test."
        ),
        expected_output="Complete implementation with clear function boundaries.",
        agent=implementation_engineer,
        context=[requirements_task, architecture_task],
    )
    testing_task = Task(
        description=(
            "Create a strong test suite covering normal behavior, edge cases, "
            "invalid inputs, and regression risks."
        ),
        expected_output="Runnable tests with a short explanation of coverage.",
        agent=test_engineer,
        context=[requirements_task, architecture_task, implementation_task],
    )
    security_task = Task(
        description=(
            "Review the implementation and tests for security, reliability, "
            "resource use, and maintainability concerns."
        ),
        expected_output="Risk review with fixes or explicit approval.",
        agent=security_reviewer,
        context=[implementation_task, testing_task],
    )
    final_package_task = Task(
        description=dedent(
            """
            Produce the final package:
            - final code
            - final tests
            - explanation
            - complexity analysis
            - run instructions
            - limitations and future improvements
            """
        ).strip(),
        expected_output="A polished final coding answer ready for handoff.",
        agent=docs_engineer,
        context=[
            requirements_task,
            architecture_task,
            implementation_task,
            testing_task,
            security_task,
        ],
    )

    selected_process = _resolve_process(Process, process, manager_llm)
    crew_kwargs: dict[str, Any] = {
        "agents": [
            product_analyst,
            system_architect,
            implementation_engineer,
            test_engineer,
            security_reviewer,
            docs_engineer,
        ],
        "tasks": [
            requirements_task,
            architecture_task,
            implementation_task,
            testing_task,
            security_task,
            final_package_task,
        ],
        "process": selected_process,
        "verbose": verbose,
        "planning": True,
        "memory": False,
    }

    if process == "hierarchical":
        crew_kwargs["manager_llm"] = manager_llm

    return Crew(**crew_kwargs)


def kickoff_single_agent(problem: CodingProblem, **kwargs: Any) -> Any:
    crew = build_single_agent_coding_crew(problem, **kwargs)
    return crew.kickoff(inputs=problem.as_inputs())


def kickoff_pair_programming(problem: CodingProblem, **kwargs: Any) -> Any:
    crew = build_pair_programming_crew(problem, **kwargs)
    return crew.kickoff(inputs=problem.as_inputs())


def kickoff_complex_delivery(problem: CodingProblem, **kwargs: Any) -> Any:
    crew = build_complex_multi_agent_coding_crew(problem, **kwargs)
    return crew.kickoff(inputs=problem.as_inputs())


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
            "a rolling time window. Provide code that can be unit tested without "
            "sleeping in tests."
        ),
        difficulty=Difficulty.INTERMEDIATE,
        constraints=(
            "Use dependency injection for time.",
            "Avoid global mutable state.",
            "Evict old timestamps to prevent unbounded memory growth.",
        ),
    )


def example_advanced_job_scheduler() -> CodingProblem:
    return CodingProblem(
        title="Priority Job Scheduler",
        prompt=(
            "Build an in-memory job scheduler that supports adding jobs with "
            "priority and scheduled time, claiming the next runnable job, marking "
            "jobs complete or failed, and retrying failed jobs up to a maximum."
        ),
        difficulty=Difficulty.ADVANCED,
        constraints=(
            "Make state transitions explicit.",
            "Prevent claiming jobs before scheduled time.",
            "Include tests for retry exhaustion and tie-breaking.",
            "Keep the design adaptable for persistent storage later.",
        ),
    )


def validate_problem(problem: CodingProblem) -> None:
    if not isinstance(problem, CodingProblem):
        raise TypeError("problem must be a CodingProblem")
    _require_text(problem.title, "title")
    _require_text(problem.prompt, "prompt")
    _require_text(problem.language, "language")


def _resolve_process(Process: Any, process: CrewProcess, manager_llm: Optional[str]) -> Any:
    if process == "sequential":
        return Process.sequential

    if process == "hierarchical":
        if not manager_llm:
            raise ValueError("manager_llm is required for hierarchical CrewAI process")
        return Process.hierarchical

    raise ValueError("process must be either 'sequential' or 'hierarchical'")


def _format_bullets(items: Iterable[str]) -> str:
    values = [item.strip() for item in items if item and item.strip()]
    if not values:
        return "- None"
    return "\n".join(f"- {item}" for item in values)


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def describe_available_examples() -> str:
    """Return a quick guide when CrewAI is not installed or no API key is set."""

    return dedent(
        """
        Available CrewAI coding examples:

        1. basic
           Single-agent coding assistant for focused algorithm problems.

        2. pair
           Three-agent workflow: architect -> developer -> reviewer.

        3. complex
           Six-agent production workflow: requirements, architecture,
           implementation, testing, security review, and final handoff.

        Example commands:
            python ai/crewai.py --mode basic
            python ai/crewai.py --mode pair
            python ai/crewai.py --mode complex
            python ai/crewai.py --mode complex --process hierarchical --manager-llm gpt-4o-mini
        """
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="CrewAI coding-agent examples")
    parser.add_argument(
        "--mode",
        choices=("guide", "basic", "pair", "complex"),
        default="guide",
        help="Which example crew to run.",
    )
    parser.add_argument(
        "--problem",
        choices=("two-sum", "rate-limiter", "job-scheduler"),
        default="two-sum",
        help="Problem to pass to the selected crew.",
    )
    parser.add_argument("--llm", default=os.getenv("OPENAI_MODEL_NAME"))
    parser.add_argument("--manager-llm", default=None)
    parser.add_argument("--process", choices=("sequential", "hierarchical"), default="sequential")
    parser.add_argument("--quiet", action="store_true", help="Disable CrewAI verbose output.")
    args = parser.parse_args()

    problem_factory: dict[str, Callable[[], CodingProblem]] = {
        "two-sum": example_basic_two_sum,
        "rate-limiter": example_intermediate_rate_limiter,
        "job-scheduler": example_advanced_job_scheduler,
    }
    problem = problem_factory[args.problem]()
    verbose = not args.quiet

    if args.mode == "guide":
        print(describe_available_examples())
        return

    if args.mode == "basic":
        result = kickoff_single_agent(problem, llm=args.llm, verbose=verbose)
    elif args.mode == "pair":
        result = kickoff_pair_programming(problem, llm=args.llm, verbose=verbose)
    else:
        result = kickoff_complex_delivery(
            problem,
            llm=args.llm,
            process=args.process,
            manager_llm=args.manager_llm,
            verbose=verbose,
        )

    print(result)


if __name__ == "__main__":
    main()
