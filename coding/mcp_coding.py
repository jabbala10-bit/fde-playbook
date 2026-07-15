"""
MCP coding examples from basic to advanced.

MCP (Model Context Protocol) is not an agent framework by itself. It is a
standard way for AI hosts and agents to discover and call tools, read resources,
and reuse prompts. This module demonstrates both sides:

1. An MCP server exposing coding tools, resources, and prompts.
2. A client/orchestrator that calls those tools as single, multi, and complex
   coding workflows.

Install MCP before running live server/client modes:
    pip install "mcp[cli]"

Guide and dry-run modes work without MCP installed:
    python ai/mcp_coding.py --mode guide
    python ai/mcp_coding.py --mode pair --dry-run

Run as an MCP stdio server:
    python ai/mcp_coding.py --mode server
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import json
import logging
import os
import sys
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from enum import Enum
from textwrap import dedent
from typing import Any, Callable, Iterable, Optional


DEFAULT_TIMEOUT_SECONDS = 120.0
SERVER_NAME = "coding-mcp-server"
logger = logging.getLogger(__name__)


class Difficulty(str, Enum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass(frozen=True)
class CodingProblem:
    """Structured coding problem used by all MCP workflows."""

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
class MCPConfig:
    """Runtime config for the local MCP client/orchestrator."""

    server_script: str
    python_command: str = sys.executable
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    dry_run: bool = False

    def __post_init__(self) -> None:
        _require_text(self.server_script, "server_script")
        _require_text(self.python_command, "python_command")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True)
class MCPToolResult:
    tool_name: str
    output: str
    elapsed_ms: float
    arguments: dict[str, Any]


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


def solve_coding_problem(problem: str, language: str = "Python") -> str:
    """Basic single-agent style coding answer scaffold."""

    risk_scan = static_code_risk_scan(problem)
    complexity = complexity_probe(problem)
    return _render_sections(
        {
            "role": "single_coding_solver",
            "problem": problem,
            "language": language,
            "approach": (
                "Clarify inputs and outputs, choose the simplest correct algorithm, "
                "then implement with tests around edge cases."
            ),
            "local_complexity_observations": json.dumps(complexity, indent=2),
            "local_risk_observations": json.dumps(risk_scan, indent=2),
            "deliverable_instruction": (
                "Return final code, tests, explanation, and time/space complexity."
            ),
        }
    )


def design_coding_solution(problem: str, language: str = "Python") -> str:
    """Create implementation-ready design notes."""

    complexity = complexity_probe(problem)
    return _render_sections(
        {
            "role": "algorithm_architect",
            "problem": problem,
            "language": language,
            "assumptions": "Keep assumptions explicit. Prefer deterministic behavior.",
            "algorithm_design": (
                "Select data structures based on lookup, ordering, and mutation needs. "
                "Document invariants before implementation."
            ),
            "edge_cases": (
                "Cover empty inputs, duplicate values, invalid inputs, boundary times, "
                "and retry/state-transition failures where relevant."
            ),
            "complexity_probe": json.dumps(complexity, indent=2),
        }
    )


def implement_coding_solution(
    problem: str,
    design_notes: str,
    language: str = "Python",
) -> str:
    """Create implementation instructions from a design."""

    risk_scan = static_code_risk_scan(f"{problem}\n\n{design_notes}")
    return _render_sections(
        {
            "role": "implementation_engineer",
            "problem": problem,
            "design_notes": design_notes,
            "language": language,
            "implementation_guidance": (
                "Write small typed functions/classes, validate public inputs, avoid "
                "global mutable state, and separate core logic from I/O."
            ),
            "test_guidance": (
                "Include normal, edge, and failure tests. Keep tests deterministic."
            ),
            "risk_scan": json.dumps(risk_scan, indent=2),
        }
    )


def review_coding_solution(problem: str, implementation: str) -> str:
    """Review code for correctness, risk, and coverage."""

    risk_scan = static_code_risk_scan(implementation)
    return _render_sections(
        {
            "role": "code_reviewer",
            "problem": problem,
            "implementation": implementation,
            "review_checklist": (
                "Check correctness, edge cases, input validation, security, resource "
                "growth, maintainability, and test coverage."
            ),
            "risk_scan": json.dumps(risk_scan, indent=2),
            "final_instruction": (
                "If issues exist, provide corrected code. If none exist, approve explicitly."
            ),
        }
    )


def extract_requirements(problem: str) -> str:
    """Extract acceptance criteria for a coding task."""

    return _render_sections(
        {
            "role": "requirements_analyst",
            "problem": problem,
            "acceptance_criteria": (
                "Define observable behavior, input/output contracts, failure behavior, "
                "and performance expectations."
            ),
            "non_goals": "Avoid unrelated frameworks, persistence, or UI unless requested.",
            "test_strategy": "Map each criterion to at least one deterministic test.",
        }
    )


def review_correctness(problem: str, candidate_code: str) -> str:
    """Review functional correctness and edge cases."""

    return _render_sections(
        {
            "role": "correctness_reviewer",
            "problem": problem,
            "candidate_code": candidate_code,
            "findings": (
                "Verify algorithm invariants, boundary cases, duplicate handling, "
                "state transitions, and expected exceptions."
            ),
        }
    )


def review_tests(problem: str, candidate_code: str) -> str:
    """Review test quality and missing coverage."""

    has_tests = "def test_" in candidate_code or "pytest" in candidate_code or "unittest" in candidate_code
    return _render_sections(
        {
            "role": "test_reviewer",
            "problem": problem,
            "candidate_code": candidate_code,
            "coverage_status": "Tests detected." if has_tests else "No obvious tests detected.",
            "required_tests": (
                "Add success-path, boundary, invalid-input, regression, and deterministic "
                "time/state tests where applicable."
            ),
        }
    )


def review_security_reliability(candidate_code: str) -> str:
    """Review security, reliability, and operational risks."""

    risk_scan = static_code_risk_scan(candidate_code)
    return _render_sections(
        {
            "role": "security_reliability_reviewer",
            "candidate_code": candidate_code,
            "risk_scan": json.dumps(risk_scan, indent=2),
            "reliability_checks": (
                "Check timeouts, bounded memory, deterministic state transitions, "
                "secret handling, logging, and safe defaults."
            ),
        }
    )


def refactor_from_review(
    candidate_code: str,
    correctness_review: str,
    test_review: str,
    security_review: str,
) -> str:
    """Apply review feedback and produce a corrected package."""

    return _render_sections(
        {
            "role": "refactor_engineer",
            "candidate_code": candidate_code,
            "correctness_review": correctness_review,
            "test_review": test_review,
            "security_review": security_review,
            "refactor_instruction": (
                "Apply concrete fixes. If no changes are needed, say "
                "'approved: no changes are needed'."
            ),
        }
    )


def write_final_handoff(problem: str, final_candidate: str) -> str:
    """Create the final coding handoff."""

    return _render_sections(
        {
            "role": "final_handoff_writer",
            "problem": problem,
            "final_candidate": final_candidate,
            "handoff_requirements": (
                "Include final code, tests, explanation, complexity analysis, run "
                "instructions, limitations, and production notes."
            ),
        }
    )


def create_mcp_server() -> Any:
    """Create the FastMCP server with tools, resources, and prompts."""

    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError('MCP SDK is not installed. Install it with: pip install "mcp[cli]"') from exc

    mcp = FastMCP(SERVER_NAME)

    mcp.tool()(solve_coding_problem)
    mcp.tool()(design_coding_solution)
    mcp.tool()(implement_coding_solution)
    mcp.tool()(review_coding_solution)
    mcp.tool()(extract_requirements)
    mcp.tool()(review_correctness)
    mcp.tool()(review_tests)
    mcp.tool()(review_security_reliability)
    mcp.tool()(refactor_from_review)
    mcp.tool()(write_final_handoff)

    @mcp.resource("coding://checklists/production")
    def production_checklist() -> str:
        """Production coding checklist exposed as an MCP resource."""

        return dedent(
            """
            # Production Coding Checklist

            - Define input/output contracts.
            - Keep core logic separate from I/O.
            - Validate public inputs.
            - Bound memory growth.
            - Add deterministic tests.
            - Avoid hard-coded secrets.
            - Prefer explicit state transitions.
            - Document time and space complexity.
            """
        ).strip()

    @mcp.prompt()
    def coding_problem_prompt(problem: str, language: str = "Python") -> str:
        """Prompt template for coding problem solving."""

        return dedent(
            f"""
            Solve this coding problem in {language}.

            Problem:
            {problem}

            Return approach, code, tests, edge cases, and complexity analysis.
            """
        ).strip()

    return mcp


class MCPStdioClient:
    """Small MCP stdio client for calling coding tools from this script."""

    def __init__(self, config: MCPConfig) -> None:
        self.config = config
        self._exit_stack = AsyncExitStack()
        self._session: Optional[Any] = None

    async def __aenter__(self) -> "MCPStdioClient":
        if self.config.dry_run:
            return self

        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as exc:
            raise RuntimeError('MCP SDK is not installed. Install it with: pip install "mcp[cli]"') from exc

        server_params = StdioServerParameters(
            command=self.config.python_command,
            args=[self.config.server_script, "--mode", "server"],
            env=None,
        )
        read_stream, write_stream = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await self._exit_stack.aclose()

    async def list_tools(self) -> list[str]:
        if self.config.dry_run:
            return [
                "solve_coding_problem",
                "design_coding_solution",
                "implement_coding_solution",
                "review_coding_solution",
                "extract_requirements",
                "review_correctness",
                "review_tests",
                "review_security_reliability",
                "refactor_from_review",
                "write_final_handoff",
            ]
        if self._session is None:
            raise RuntimeError("MCP session is not initialized")
        response = await self._session.list_tools()
        return [tool.name for tool in response.tools]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> MCPToolResult:
        started = time.perf_counter()
        if self.config.dry_run:
            output = _call_local_tool(tool_name, arguments)
        else:
            if self._session is None:
                raise RuntimeError("MCP session is not initialized")
            response = await self._session.call_tool(tool_name, arguments)
            output = _extract_mcp_text(response)

        elapsed_ms = (time.perf_counter() - started) * 1_000
        return MCPToolResult(
            tool_name=tool_name,
            output=output,
            elapsed_ms=round(elapsed_ms, 3),
            arguments=arguments,
        )


class MCPCodingOrchestrator:
    """Client-side workflow orchestrator that composes MCP coding tools."""

    def __init__(self, client: MCPStdioClient) -> None:
        self.client = client

    async def run_single_agent(self, problem: CodingProblem) -> MCPToolResult:
        return await self.client.call_tool(
            "solve_coding_problem",
            {"problem": problem.to_prompt(), "language": problem.language},
        )

    async def run_pair_programming(self, problem: CodingProblem) -> dict[str, MCPToolResult]:
        design = await self.client.call_tool(
            "design_coding_solution",
            {"problem": problem.to_prompt(), "language": problem.language},
        )
        implementation = await self.client.call_tool(
            "implement_coding_solution",
            {
                "problem": problem.to_prompt(),
                "design_notes": design.output,
                "language": problem.language,
            },
        )
        review = await self.client.call_tool(
            "review_coding_solution",
            {"problem": problem.to_prompt(), "implementation": implementation.output},
        )
        return {
            "design": design,
            "implementation": implementation,
            "review": review,
        }

    async def run_complex_delivery(
        self,
        problem: CodingProblem,
        *,
        max_refinement_rounds: int = 2,
    ) -> dict[str, Any]:
        requirements = await self.client.call_tool(
            "extract_requirements",
            {"problem": problem.to_prompt()},
        )
        architecture = await self.client.call_tool(
            "design_coding_solution",
            {
                "problem": _join_context(problem.to_prompt(), {"requirements": requirements.output}),
                "language": problem.language,
            },
        )
        candidate = await self.client.call_tool(
            "implement_coding_solution",
            {
                "problem": problem.to_prompt(),
                "design_notes": architecture.output,
                "language": problem.language,
            },
        )

        refinement_history: list[dict[str, MCPToolResult]] = []
        for _ in range(max_refinement_rounds):
            reviews = await self._run_reviews(candidate.output, problem)
            candidate = await self.client.call_tool(
                "refactor_from_review",
                {
                    "candidate_code": candidate.output,
                    "correctness_review": reviews["correctness_review"].output,
                    "test_review": reviews["test_review"].output,
                    "security_review": reviews["security_review"].output,
                },
            )
            refinement_history.append(reviews | {"refactor": candidate})
            if _looks_approved(candidate.output):
                break

        final = await self.client.call_tool(
            "write_final_handoff",
            {"problem": problem.to_prompt(), "final_candidate": candidate.output},
        )
        return {
            "requirements": requirements,
            "architecture": architecture,
            "final_candidate": candidate,
            "refinement_history": refinement_history,
            "final": final,
        }

    async def _run_reviews(
        self,
        candidate_code: str,
        problem: CodingProblem,
    ) -> dict[str, MCPToolResult]:
        if self.client.config.dry_run:
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    "correctness_review": executor.submit(
                        _call_local_tool,
                        "review_correctness",
                        {"problem": problem.to_prompt(), "candidate_code": candidate_code},
                    ),
                    "test_review": executor.submit(
                        _call_local_tool,
                        "review_tests",
                        {"problem": problem.to_prompt(), "candidate_code": candidate_code},
                    ),
                    "security_review": executor.submit(
                        _call_local_tool,
                        "review_security_reliability",
                        {"candidate_code": candidate_code},
                    ),
                }
                now = time.perf_counter()
                return {
                    name: MCPToolResult(
                        tool_name=name,
                        output=future.result(),
                        elapsed_ms=round((time.perf_counter() - now) * 1_000, 3),
                        arguments={},
                    )
                    for name, future in futures.items()
                }

        correctness, tests, security = await asyncio.gather(
            self.client.call_tool(
                "review_correctness",
                {"problem": problem.to_prompt(), "candidate_code": candidate_code},
            ),
            self.client.call_tool(
                "review_tests",
                {"problem": problem.to_prompt(), "candidate_code": candidate_code},
            ),
            self.client.call_tool(
                "review_security_reliability",
                {"candidate_code": candidate_code},
            ),
        )
        return {
            "correctness_review": correctness,
            "test_review": tests,
            "security_review": security,
        }


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
        Available MCP coding examples:

        1. server
           Runs this file as an MCP stdio server exposing coding tools,
           a production checklist resource, and a coding prompt.

        2. single
           Calls solve_coding_problem through MCP.

        3. pair
           MCP workflow: design -> implementation -> review.

        4. complex
           MCP workflow:
           requirements -> architecture -> implementation -> parallel reviews
           -> refinement -> final handoff.

        5. list-tools
           Starts the local MCP server and lists available tools.

        Example commands:
            python ai/mcp_coding.py --mode guide
            python ai/mcp_coding.py --mode server
            python ai/mcp_coding.py --mode list-tools --dry-run
            python ai/mcp_coding.py --mode single --problem two-sum --dry-run
            python ai/mcp_coding.py --mode pair --problem rate-limiter --dry-run
            python ai/mcp_coding.py --mode complex --problem job-scheduler --dry-run
        """
    ).strip()


async def run_cli_async(args: argparse.Namespace) -> Any:
    problem_factory: dict[str, Callable[[], CodingProblem]] = {
        "two-sum": example_basic_two_sum,
        "rate-limiter": example_intermediate_rate_limiter,
        "job-scheduler": example_advanced_job_scheduler,
    }
    problem = problem_factory[args.problem]()
    config = MCPConfig(
        server_script=args.server_script,
        python_command=args.python_command,
        timeout_seconds=args.timeout,
        dry_run=args.dry_run,
    )

    async with MCPStdioClient(config) as client:
        orchestrator = MCPCodingOrchestrator(client)
        if args.mode == "list-tools":
            return await client.list_tools()
        if args.mode == "single":
            return await orchestrator.run_single_agent(problem)
        if args.mode == "pair":
            return await orchestrator.run_pair_programming(problem)
        if args.mode == "complex":
            return await orchestrator.run_complex_delivery(problem)
        raise ValueError(f"Unsupported async mode: {args.mode}")


def _call_local_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    tools: dict[str, Callable[..., str]] = {
        "solve_coding_problem": solve_coding_problem,
        "design_coding_solution": design_coding_solution,
        "implement_coding_solution": implement_coding_solution,
        "review_coding_solution": review_coding_solution,
        "extract_requirements": extract_requirements,
        "review_correctness": review_correctness,
        "review_tests": review_tests,
        "review_security_reliability": review_security_reliability,
        "refactor_from_review": refactor_from_review,
        "write_final_handoff": write_final_handoff,
    }
    if tool_name not in tools:
        raise ValueError(f"Unknown tool: {tool_name}")
    return tools[tool_name](**arguments)


def _extract_mcp_text(response: Any) -> str:
    content = getattr(response, "content", None)
    if not content:
        return str(response)

    texts: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            texts.append(text)
        elif isinstance(item, dict) and isinstance(item.get("text"), str):
            texts.append(item["text"])
    return "\n".join(texts) if texts else str(response)


def _render_sections(sections: dict[str, str]) -> str:
    return "\n\n".join(f"## {title}\n{body}" for title, body in sections.items())


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


def _to_printable(result: Any) -> str:
    if isinstance(result, MCPToolResult):
        return result.output
    if isinstance(result, list):
        return json.dumps(result, indent=2)
    if isinstance(result, dict):
        printable = {
            key: value.output if isinstance(value, MCPToolResult) else value
            for key, value in result.items()
            if key != "refinement_history"
        }
        return json.dumps(printable, indent=2)
    return str(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP coding tools and workflows")
    parser.add_argument(
        "--mode",
        choices=("guide", "server", "list-tools", "single", "pair", "complex"),
        default="guide",
        help="Which MCP mode to run.",
    )
    parser.add_argument(
        "--problem",
        choices=("two-sum", "rate-limiter", "job-scheduler"),
        default="two-sum",
        help="Problem sent to the selected workflow.",
    )
    parser.add_argument("--server-script", default=os.path.abspath(__file__))
    parser.add_argument("--python-command", default=sys.executable)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--dry-run", action="store_true", help="Use local functions without MCP transport.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    if args.mode == "guide":
        print(describe_available_examples())
        return

    if args.mode == "server":
        # Stdio MCP servers must not write logs or prints to stdout.
        logging.basicConfig(stream=sys.stderr)
        create_mcp_server().run(transport="stdio")
        return

    result = asyncio.run(run_cli_async(args))
    print(_to_printable(result))


if __name__ == "__main__":
    main()
