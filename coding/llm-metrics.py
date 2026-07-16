"""
LLMOps observability metrics catalogue from a Forward Deployed Engineer lens.

This module is a practical reference and planning helper for production LLM
systems. It covers tracing, explainability, model activity monitoring, RAG,
agents, safety, cost, reliability, privacy, governance, and business outcomes.

Use it as:
    1. A checklist for launch readiness.
    2. A dashboard design starter.
    3. A field implementation guide for customer deployments.
    4. A lightweight CLI that prints JSON or Markdown plans.

Examples:
    python ai/llm-metrics.py --mode guide
    python ai/llm-metrics.py --mode catalog --format markdown
    python ai/llm-metrics.py --mode dashboard --format markdown
    python ai/llm-metrics.py --mode demo --format json
    python ai/llm-metrics.py --mode assess --input llmops_profile.json --format markdown
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from textwrap import dedent
from typing import Any, Iterable, Optional


TODAY = date.today().isoformat()


class MetricPillar(str, Enum):
    TRACING = "tracing"
    MODEL_ACTIVITY = "model_activity"
    PERFORMANCE = "performance"
    QUALITY = "quality"
    RAG = "rag"
    AGENTS_TOOLS = "agents_tools"
    SAFETY_SECURITY = "safety_security"
    COST_CAPACITY = "cost_capacity"
    DRIFT_DATA = "drift_data"
    EXPLAINABILITY = "explainability"
    GOVERNANCE = "governance"
    USER_BUSINESS = "user_business"
    OPERATIONS = "operations"


class SignalType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TRACE = "trace"
    LOG = "log"
    EVAL = "eval"
    AUDIT = "audit"
    BUSINESS = "business"


class RolloutTier(str, Enum):
    LAUNCH_BLOCKER = "launch_blocker"
    FIRST_WEEK = "first_week"
    SCALE_UP = "scale_up"
    OPTIMIZE = "optimize"


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: str
    name: str
    pillar: MetricPillar
    signal_type: SignalType
    tier: RolloutTier
    description: str
    why_fde_cares: str
    unit: str
    dimensions: tuple[str, ...]
    collection: str
    alert_guidance: str
    owner: str


@dataclass(frozen=True)
class LLMOpsProfile:
    """Structured input for selecting an observability plan."""

    name: str
    use_case: str
    architecture: tuple[str, ...] = field(default_factory=tuple)
    criticality: str = "medium"
    users: str = ""
    business_kpi: str = ""
    regulated: bool = False
    has_rag: bool = False
    has_agents: bool = False
    has_tools: bool = False
    has_streaming: bool = False
    multi_tenant: bool = False
    handles_pii: bool = False
    human_in_the_loop: bool = False
    external_model_provider: bool = True
    evidence: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "LLMOpsProfile":
        payload = dict(payload)
        value = payload.get("architecture", ())
        if isinstance(value, str):
            payload["architecture"] = tuple(item.strip() for item in value.split(",") if item.strip())
        else:
            payload["architecture"] = tuple(value or ())
        return cls(**payload)


@dataclass(frozen=True)
class DashboardSection:
    name: str
    purpose: str
    metrics: tuple[str, ...]


@dataclass(frozen=True)
class ObservabilityPlan:
    profile_name: str
    generated_on: str
    selected_metrics: list[MetricDefinition]
    launch_gates: list[str]
    dashboard_sections: list[DashboardSection]
    instrumentation_events: list[str]
    fde_rollout_notes: list[str]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    def to_markdown(self) -> str:
        lines = [
            f"# LLMOps Observability Plan: {self.profile_name}",
            "",
            f"- Generated on: `{self.generated_on}`",
            f"- Metrics selected: `{len(self.selected_metrics)}`",
            "",
            "## Launch Gates",
        ]
        lines.extend(f"- {item}" for item in self.launch_gates)

        lines.extend(["", "## Dashboard Sections"])
        for section in self.dashboard_sections:
            lines.append(f"### {section.name}")
            lines.append(section.purpose)
            for metric_id in section.metrics:
                lines.append(f"- `{metric_id}`")

        lines.extend(["", "## Selected Metrics"])
        for metric in self.selected_metrics:
            dims = ", ".join(metric.dimensions)
            lines.append(
                f"- `{metric.metric_id}` ({metric.pillar.value}, {metric.tier.value}): "
                f"{metric.description} Unit: {metric.unit}. Dimensions: {dims}."
            )

        lines.extend(["", "## Instrumentation Events"])
        lines.extend(f"- `{item}`" for item in self.instrumentation_events)

        lines.extend(["", "## FDE Rollout Notes"])
        lines.extend(f"- {item}" for item in self.fde_rollout_notes)
        return "\n".join(lines)


def m(
    metric_id: str,
    name: str,
    pillar: MetricPillar,
    signal_type: SignalType,
    tier: RolloutTier,
    description: str,
    why: str,
    unit: str,
    dimensions: tuple[str, ...],
    collection: str,
    alert: str,
    owner: str = "FDE + platform owner",
) -> MetricDefinition:
    return MetricDefinition(
        metric_id=metric_id,
        name=name,
        pillar=pillar,
        signal_type=signal_type,
        tier=tier,
        description=description,
        why_fde_cares=why,
        unit=unit,
        dimensions=dimensions,
        collection=collection,
        alert_guidance=alert,
        owner=owner,
    )


COMMON_DIMS = ("environment", "tenant_id", "use_case", "model", "model_version", "prompt_version")


METRICS: tuple[MetricDefinition, ...] = (
    # Tracing and request lineage.
    m("trace.request_trace_coverage", "Request trace coverage", MetricPillar.TRACING, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of LLM requests with an end-to-end trace id.", "Without trace coverage, field debugging becomes guesswork.", "%", COMMON_DIMS, "Emit trace_id at ingress and propagate through orchestration, retrieval, model, tools, and response.", "Alert below 99% in production."),
    m("trace.span_completeness", "Span completeness", MetricPillar.TRACING, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of traces containing required spans.", "Shows whether latency, cost, and quality can be attributed to the right component.", "%", COMMON_DIMS + ("span_name",), "Check required spans: ingress, policy, retrieval, prompt_build, model_call, tool_call, postprocess.", "Alert when required span coverage drops below 98%."),
    m("trace.context_propagation_failures", "Context propagation failures", MetricPillar.TRACING, SignalType.COUNTER, RolloutTier.FIRST_WEEK, "Count of requests where trace, user, tenant, or session context is lost.", "Lost context breaks auditability and root-cause analysis.", "count", COMMON_DIMS + ("component",), "Validate correlation fields at each service boundary.", "Page if failures affect regulated or high-impact workflows."),
    m("trace.orchestration_step_count", "Orchestration step count", MetricPillar.TRACING, SignalType.HISTOGRAM, RolloutTier.FIRST_WEEK, "Number of orchestration steps per request.", "Rising step count often predicts cost, latency, loops, and agent instability.", "steps", COMMON_DIMS + ("route",), "Count prompt, retrieval, tool, planner, verifier, and finalizer spans.", "Alert on sudden p95 increase or max-step exhaustion."),
    m("trace.replayability_completeness", "Replayability completeness", MetricPillar.TRACING, SignalType.GAUGE, RolloutTier.SCALE_UP, "Percent of traces with enough metadata to replay or evaluate offline.", "FDEs need reproducible failures when customer evidence is thin.", "%", COMMON_DIMS, "Record prompt version, model params, retrieval ids, tool inputs, policy decisions, and redaction state.", "Alert below agreed audit threshold."),
    m("trace.span_error_rate", "Span error rate", MetricPillar.TRACING, SignalType.GAUGE, RolloutTier.FIRST_WEEK, "Error rate by span and component.", "Separates model failures from retriever, tool, auth, network, and post-processing failures.", "%", COMMON_DIMS + ("span_name", "error_type"), "Mark span status and normalized error category.", "Alert when component error rate breaches SLO."),
    m("trace.customer_journey_linkage", "Customer journey linkage", MetricPillar.TRACING, SignalType.GAUGE, RolloutTier.SCALE_UP, "Percent of AI traces linked to the surrounding workflow or ticket.", "Lets field teams prove whether AI improved the actual operation.", "%", COMMON_DIMS + ("workflow",), "Attach workflow_id, ticket_id, case_id, or order_id where allowed.", "Alert when linkage drops after integration changes."),

    # Model activity and behavior.
    m("activity.request_volume", "Request volume", MetricPillar.MODEL_ACTIVITY, SignalType.COUNTER, RolloutTier.LAUNCH_BLOCKER, "Number of model requests.", "Baseline traffic helps spot adoption, abuse, outages, and release impact.", "requests", COMMON_DIMS + ("route", "user_segment"), "Count each model call and top-level user request separately.", "Alert on sharp deviations from seasonality."),
    m("activity.active_users", "Active AI users", MetricPillar.MODEL_ACTIVITY, SignalType.GAUGE, RolloutTier.FIRST_WEEK, "Distinct users or service accounts invoking AI.", "Separates real adoption from a few automated callers.", "users", ("environment", "tenant_id", "use_case", "user_segment"), "Count distinct authorized actors per window.", "Alert on unexpected spikes or privileged-account concentration."),
    m("activity.input_tokens", "Input tokens", MetricPillar.MODEL_ACTIVITY, SignalType.HISTOGRAM, RolloutTier.LAUNCH_BLOCKER, "Prompt, system, history, retrieval, and tool-result token volume.", "Input token growth drives cost, latency, and context-window failures.", "tokens", COMMON_DIMS + ("token_source",), "Capture token usage by source before the model call.", "Alert when p95 approaches context budget."),
    m("activity.output_tokens", "Output tokens", MetricPillar.MODEL_ACTIVITY, SignalType.HISTOGRAM, RolloutTier.LAUNCH_BLOCKER, "Generated token volume.", "Long outputs can hide verbosity regressions and cost creep.", "tokens", COMMON_DIMS, "Capture provider-reported completion tokens.", "Alert when p95 jumps after prompt/model release."),
    m("activity.context_window_utilization", "Context window utilization", MetricPillar.MODEL_ACTIVITY, SignalType.HISTOGRAM, RolloutTier.LAUNCH_BLOCKER, "Percent of model context window used.", "High utilization increases truncation, latency, and lost instructions.", "%", COMMON_DIMS, "Compute total input tokens divided by model context limit.", "Warn above 75%; alert above 90%."),
    m("activity.truncation_rate", "Prompt or context truncation rate", MetricPillar.MODEL_ACTIVITY, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of calls where context, history, or retrieved chunks were truncated.", "Truncation is a common invisible cause of bad answers.", "%", COMMON_DIMS + ("truncated_source",), "Log truncation decisions in prompt builder.", "Alert on any truncation for high-risk workflows."),
    m("activity.finish_reason_distribution", "Finish reason distribution", MetricPillar.MODEL_ACTIVITY, SignalType.COUNTER, RolloutTier.FIRST_WEEK, "Counts of stop, length, content filter, tool call, and error finish reasons.", "Length and filter finishes often explain UX complaints.", "count", COMMON_DIMS + ("finish_reason",), "Use provider finish reason and normalized internal categories.", "Alert on length/content-filter spikes."),
    m("activity.refusal_rate", "Refusal rate", MetricPillar.MODEL_ACTIVITY, SignalType.GAUGE, RolloutTier.FIRST_WEEK, "Percent of requests refused or safely declined.", "Useful refusals are good; unexpected refusals are workflow failures.", "%", COMMON_DIMS + ("policy_category",), "Classify model and policy refusals separately.", "Alert on business-critical refusal spike."),
    m("activity.retry_rate", "Retry rate", MetricPillar.MODEL_ACTIVITY, SignalType.GAUGE, RolloutTier.FIRST_WEEK, "Percent of model calls retried.", "Retries mask provider instability and inflate cost/latency.", "%", COMMON_DIMS + ("retry_reason",), "Record retry count and reason at the model gateway.", "Alert when retries exceed normal provider baseline."),
    m("activity.fallback_rate", "Fallback rate", MetricPillar.MODEL_ACTIVITY, SignalType.GAUGE, RolloutTier.FIRST_WEEK, "Percent of requests served by fallback model, cached answer, rules, or human queue.", "Shows whether the happy path is actually healthy.", "%", COMMON_DIMS + ("fallback_type",), "Emit fallback reason and target.", "Page if fallback is unavailable or rising for critical flows."),
    m("activity.cache_hit_rate", "Semantic/cache hit rate", MetricPillar.MODEL_ACTIVITY, SignalType.GAUGE, RolloutTier.SCALE_UP, "Percent of eligible requests served from cache.", "Cache can reduce cost, latency, and provider exposure if correctness is controlled.", "%", COMMON_DIMS + ("cache_type",), "Track exact, semantic, retrieval, and tool-result cache hits.", "Alert on drop after prompt, embedding, or key changes."),
    m("activity.streaming_abort_rate", "Streaming abort rate", MetricPillar.MODEL_ACTIVITY, SignalType.GAUGE, RolloutTier.FIRST_WEEK, "Percent of streamed responses cancelled before completion.", "Can indicate slow first token, poor answer starts, or UI issues.", "%", COMMON_DIMS + ("client",), "Capture client disconnect/cancel events.", "Alert on sudden p95 or segment-specific spikes."),

    # Performance and reliability.
    m("perf.end_to_end_latency", "End-to-end latency", MetricPillar.PERFORMANCE, SignalType.HISTOGRAM, RolloutTier.LAUNCH_BLOCKER, "Total user-perceived latency.", "The most visible production symptom for users and stakeholders.", "ms", COMMON_DIMS + ("route",), "Measure from request ingress to final response delivered.", "Define p50/p95/p99 SLOs per workflow."),
    m("perf.time_to_first_token", "Time to first token", MetricPillar.PERFORMANCE, SignalType.HISTOGRAM, RolloutTier.LAUNCH_BLOCKER, "Time until first streamed token or first response byte.", "Key UX metric for chat and copilot products.", "ms", COMMON_DIMS + ("client",), "Record first-token timestamp in streaming layer.", "Alert when p95 breaches UX SLO."),
    m("perf.model_latency", "Model provider latency", MetricPillar.PERFORMANCE, SignalType.HISTOGRAM, RolloutTier.LAUNCH_BLOCKER, "Latency of model API or serving backend.", "Distinguishes provider/model slowness from local orchestration.", "ms", COMMON_DIMS + ("provider",), "Wrap model gateway calls with spans.", "Alert on p95/p99 provider regressions."),
    m("perf.retrieval_latency", "Retrieval latency", MetricPillar.PERFORMANCE, SignalType.HISTOGRAM, RolloutTier.LAUNCH_BLOCKER, "Time spent in query rewriting, embedding, vector search, reranking, and fetch.", "RAG quality work can accidentally create unacceptable latency.", "ms", COMMON_DIMS + ("retriever",), "Instrument each retrieval subspan.", "Alert on p95 breach by tenant/index."),
    m("perf.tool_latency", "Tool latency", MetricPillar.PERFORMANCE, SignalType.HISTOGRAM, RolloutTier.FIRST_WEEK, "Latency of external tool calls.", "Field issues often live in slow downstream systems, not the model.", "ms", COMMON_DIMS + ("tool_name",), "Wrap every tool invocation.", "Alert on tool p95 and timeout rate."),
    m("perf.queue_time", "Queue time", MetricPillar.PERFORMANCE, SignalType.HISTOGRAM, RolloutTier.FIRST_WEEK, "Time waiting for workers, rate-limit slots, batches, or GPUs.", "Queue time exposes saturation before errors appear.", "ms", COMMON_DIMS + ("queue_name",), "Record enqueue/dequeue timestamps.", "Alert when p95 consumes too much of latency budget."),
    m("perf.timeout_rate", "Timeout rate", MetricPillar.PERFORMANCE, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of requests timing out.", "Timeouts usually become support tickets immediately.", "%", COMMON_DIMS + ("component",), "Normalize timeouts across providers and tools.", "Page for critical workflows above SLO."),
    m("perf.availability", "AI path availability", MetricPillar.PERFORMANCE, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of valid requests successfully served.", "Defines whether the AI feature is actually up.", "%", COMMON_DIMS + ("route",), "Use successful top-level requests divided by valid requests.", "Page on SLO breach."),
    m("perf.error_budget_burn", "Error budget burn", MetricPillar.PERFORMANCE, SignalType.GAUGE, RolloutTier.SCALE_UP, "Rate at which latency, availability, or quality SLO budget is consumed.", "Helps negotiate launch pauses and rollback decisions calmly.", "ratio", COMMON_DIMS + ("slo",), "Compute from SLO violations per rolling window.", "Page on fast burn; ticket on slow burn."),
    m("perf.rate_limit_events", "Rate limit events", MetricPillar.PERFORMANCE, SignalType.COUNTER, RolloutTier.FIRST_WEEK, "Provider or internal rate limit hits.", "Shows when capacity planning or backoff policy is wrong.", "count", COMMON_DIMS + ("provider", "limit_type"), "Capture HTTP/provider limit codes and internal limiter decisions.", "Alert on sustained throttling."),

    # Quality and evaluation.
    m("quality.task_success_rate", "Task success rate", MetricPillar.QUALITY, SignalType.EVAL, RolloutTier.LAUNCH_BLOCKER, "Percent of requests that accomplish the user or workflow task.", "This is the metric most likely to connect model behavior to customer value.", "%", COMMON_DIMS + ("task_type",), "Measure with online feedback, human review, deterministic checks, or offline evals.", "Launch gate should have a minimum threshold per task."),
    m("quality.human_acceptance_rate", "Human acceptance rate", MetricPillar.QUALITY, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of AI suggestions accepted by users or reviewers.", "In FDE work, acceptance is often the fastest field proxy for usefulness.", "%", ("tenant_id", "use_case", "user_segment", "task_type", "prompt_version"), "Capture accept/edit/reject actions in UI or workflow.", "Alert on release-to-release drop."),
    m("quality.edit_distance_after_suggestion", "Post-suggestion edit distance", MetricPillar.QUALITY, SignalType.HISTOGRAM, RolloutTier.FIRST_WEEK, "How much humans edit AI outputs before use.", "A stable way to detect subtle quality regressions.", "ratio", ("tenant_id", "use_case", "task_type", "prompt_version"), "Compare suggested text to submitted text.", "Investigate p95 increase."),
    m("quality.schema_validity_rate", "Schema validity rate", MetricPillar.QUALITY, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of outputs matching required JSON/schema/tool contract.", "Broken structure causes brittle automation failures.", "%", COMMON_DIMS + ("schema_name",), "Validate every structured output with a parser.", "Launch blocker below 99% for automation."),
    m("quality.instruction_following_score", "Instruction following score", MetricPillar.QUALITY, SignalType.EVAL, RolloutTier.LAUNCH_BLOCKER, "Rubric or classifier score for following system/developer/user instructions.", "Critical for enterprise policy and domain constraints.", "score", COMMON_DIMS + ("eval_set",), "Run offline golden tests and online sampled reviews.", "Gate releases on no material regression."),
    m("quality.answer_relevance", "Answer relevance", MetricPillar.QUALITY, SignalType.EVAL, RolloutTier.FIRST_WEEK, "How directly the answer addresses the request.", "Prevents fluent but unhelpful responses.", "score", COMMON_DIMS + ("task_type",), "Use human rubric, reference answers, or LLM judge with calibration.", "Investigate downward trend."),
    m("quality.correctness_rate", "Correctness rate", MetricPillar.QUALITY, SignalType.EVAL, RolloutTier.LAUNCH_BLOCKER, "Percent of answers judged factually or procedurally correct.", "The core quality bar for decision-support use cases.", "%", COMMON_DIMS + ("domain", "eval_set"), "Use expert labels, deterministic checks, or calibrated evaluation.", "Launch gate for high-impact flows."),
    m("quality.hallucination_rate", "Hallucination rate", MetricPillar.QUALITY, SignalType.EVAL, RolloutTier.LAUNCH_BLOCKER, "Percent of outputs containing unsupported factual claims.", "One of the most visible LLM failure modes for customers.", "%", COMMON_DIMS + ("domain",), "Sample production outputs and compare against sources or expert labels.", "Alert on statistically significant increase."),
    m("quality.groundedness_score", "Groundedness score", MetricPillar.QUALITY, SignalType.EVAL, RolloutTier.LAUNCH_BLOCKER, "Degree to which claims are supported by provided context.", "Especially important for RAG and regulated knowledge workflows.", "score", COMMON_DIMS + ("retriever",), "Evaluate answer spans against retrieved/source documents.", "Gate releases for RAG systems."),
    m("quality.refusal_correctness", "Refusal correctness", MetricPillar.QUALITY, SignalType.EVAL, RolloutTier.FIRST_WEEK, "Whether refusals happen when they should and not when they should not.", "Balances safety with usefulness.", "%", COMMON_DIMS + ("policy_category",), "Maintain allowed/blocked eval sets and sample online refusals.", "Alert on over-refusal or under-refusal drift."),
    m("quality.regression_eval_pass_rate", "Regression eval pass rate", MetricPillar.QUALITY, SignalType.EVAL, RolloutTier.LAUNCH_BLOCKER, "Percent of release candidate evals passing.", "Keeps prompt/model changes from silently breaking customer workflows.", "%", COMMON_DIMS + ("eval_suite",), "Run fixed, adversarial, and customer-specific eval suites in CI/CD.", "Block release below threshold."),
    m("quality.judge_agreement", "Evaluator agreement", MetricPillar.QUALITY, SignalType.EVAL, RolloutTier.SCALE_UP, "Agreement between LLM judge, human reviewer, and deterministic checks.", "Prevents false confidence in automated evaluation.", "score", ("eval_suite", "judge_model", "reviewer_group"), "Track Cohen kappa, correlation, or disagreement rate.", "Review judge prompts when agreement falls."),

    # RAG and knowledge systems.
    m("rag.retrieval_hit_rate", "Retrieval hit rate", MetricPillar.RAG, SignalType.EVAL, RolloutTier.LAUNCH_BLOCKER, "Percent of queries retrieving at least one relevant document.", "If retrieval misses, generation has little chance.", "%", COMMON_DIMS + ("index", "query_type"), "Evaluate against labeled query-document pairs.", "Gate launch for knowledge use cases."),
    m("rag.recall_at_k", "Recall at K", MetricPillar.RAG, SignalType.EVAL, RolloutTier.LAUNCH_BLOCKER, "Relevant documents retrieved within top K.", "Core retrieval quality metric.", "%", COMMON_DIMS + ("index", "k"), "Use golden query sets with known relevant docs.", "Alert on regression after index or embedding changes."),
    m("rag.precision_at_k", "Precision at K", MetricPillar.RAG, SignalType.EVAL, RolloutTier.FIRST_WEEK, "Fraction of top K retrieved chunks that are relevant.", "Controls context pollution and hallucination risk.", "%", COMMON_DIMS + ("index", "k"), "Label retrieved chunks or use calibrated review.", "Investigate drops by source system."),
    m("rag.mrr", "Mean reciprocal rank", MetricPillar.RAG, SignalType.EVAL, RolloutTier.FIRST_WEEK, "Average reciprocal rank of first relevant result.", "Higher rank usually improves answer quality and latency.", "score", COMMON_DIMS + ("index",), "Compute from labeled query-document pairs.", "Track release-to-release."),
    m("rag.ndcg", "nDCG", MetricPillar.RAG, SignalType.EVAL, RolloutTier.SCALE_UP, "Ranking quality with graded relevance.", "Useful when several chunks are partially relevant.", "score", COMMON_DIMS + ("index",), "Compute from graded labels.", "Investigate ranking regressions."),
    m("rag.citation_precision", "Citation precision", MetricPillar.RAG, SignalType.EVAL, RolloutTier.LAUNCH_BLOCKER, "Percent of cited sources that support the cited claim.", "Customers trust citations only if they are real evidence.", "%", COMMON_DIMS + ("source_system",), "Evaluate answer citations against source spans.", "Gate regulated knowledge assistants."),
    m("rag.citation_recall", "Citation recall", MetricPillar.RAG, SignalType.EVAL, RolloutTier.FIRST_WEEK, "Percent of important claims that have citations.", "Prevents uncited claims in source-grounded workflows.", "%", COMMON_DIMS + ("source_system",), "Detect answer claims and source support.", "Alert on decline for compliance domains."),
    m("rag.source_freshness_lag", "Source freshness lag", MetricPillar.RAG, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Age of indexed content relative to source of truth.", "Stale indexes create wrong answers even with good retrieval.", "minutes", ("environment", "tenant_id", "source_system", "index"), "Compare source update time to index ingestion time.", "Alert when lag exceeds business tolerance."),
    m("rag.indexing_failure_rate", "Indexing failure rate", MetricPillar.RAG, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of documents or chunks failing ingestion.", "Silent ingestion gaps become answer gaps.", "%", ("environment", "tenant_id", "source_system", "index", "error_type"), "Track ingestion pipeline successes/failures.", "Alert on failures for critical sources."),
    m("rag.chunk_coverage", "Chunk coverage", MetricPillar.RAG, SignalType.GAUGE, RolloutTier.FIRST_WEEK, "Percent of eligible source documents represented in the vector/keyword index.", "Confirms that the deployed assistant can see the promised corpus.", "%", ("tenant_id", "source_system", "index"), "Compare source inventory to indexed chunk inventory.", "Alert below agreed corpus coverage."),
    m("rag.retrieval_score_margin", "Retrieval score margin", MetricPillar.RAG, SignalType.HISTOGRAM, RolloutTier.SCALE_UP, "Score gap between top result and alternatives.", "Low margin queries may need clarification or broader search.", "score", COMMON_DIMS + ("index",), "Record top scores and margin from retriever/reranker.", "Use to route uncertain queries to fallback."),
    m("rag.context_utilization", "Context utilization", MetricPillar.RAG, SignalType.EVAL, RolloutTier.SCALE_UP, "How much retrieved context is actually used in the answer.", "Shows wasted tokens and irrelevant retrieval.", "%", COMMON_DIMS + ("index",), "Map answer claims to provided chunks.", "Optimize chunking/reranking when low."),

    # Agents and tool use.
    m("agent.tool_call_success_rate", "Tool call success rate", MetricPillar.AGENTS_TOOLS, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of tool calls that complete successfully.", "Tool reliability is often the real production bottleneck.", "%", COMMON_DIMS + ("tool_name",), "Wrap tool calls and normalize success/error status.", "Alert by tool and tenant."),
    m("agent.tool_selection_accuracy", "Tool selection accuracy", MetricPillar.AGENTS_TOOLS, SignalType.EVAL, RolloutTier.FIRST_WEEK, "Whether the agent chose the right tool for the task.", "Wrong tools cause wrong actions, not just wrong text.", "%", COMMON_DIMS + ("tool_name", "task_type"), "Evaluate traces against labeled expected tool use.", "Gate agent changes with tool evals."),
    m("agent.tool_argument_validity", "Tool argument validity", MetricPillar.AGENTS_TOOLS, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of tool calls with valid schema and business-rule arguments.", "Prevents malformed or dangerous downstream actions.", "%", COMMON_DIMS + ("tool_name",), "Validate schema and domain constraints before execution.", "Block or alert on invalid action attempts."),
    m("agent.loop_rate", "Agent loop rate", MetricPillar.AGENTS_TOOLS, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of agent runs with repeated or unproductive steps.", "Loops can burn cost and stall users.", "%", COMMON_DIMS + ("agent_name",), "Detect repeated tool/prompt states or max-step termination.", "Page if loops affect live traffic."),
    m("agent.max_step_exhaustion_rate", "Max step exhaustion rate", MetricPillar.AGENTS_TOOLS, SignalType.GAUGE, RolloutTier.FIRST_WEEK, "Runs ending because the step limit was reached.", "Shows planning or tool failures.", "%", COMMON_DIMS + ("agent_name",), "Emit terminal reason for every agent run.", "Alert on spike after prompt/tool changes."),
    m("agent.human_approval_rate", "Human approval rate", MetricPillar.AGENTS_TOOLS, SignalType.GAUGE, RolloutTier.FIRST_WEEK, "Percent of proposed actions approved by humans.", "Strong proxy for whether agent actions are useful and trusted.", "%", ("tenant_id", "use_case", "tool_name", "action_type"), "Capture approve/reject/edit decisions.", "Investigate low approval by action type."),
    m("agent.unsafe_action_block_rate", "Unsafe action block rate", MetricPillar.AGENTS_TOOLS, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of tool actions blocked by policy guardrails.", "Validates control boundaries for write/action agents.", "%", COMMON_DIMS + ("policy_category", "tool_name"), "Log policy decisions before side effects.", "Alert on under-blocking and sudden over-blocking."),
    m("agent.idempotency_conflict_rate", "Idempotency conflict rate", MetricPillar.AGENTS_TOOLS, SignalType.GAUGE, RolloutTier.SCALE_UP, "Duplicate or conflicting action attempts caught by idempotency controls.", "Prevents repeated orders, tickets, emails, or data changes.", "%", ("tenant_id", "use_case", "tool_name", "action_type"), "Record idempotency keys and conflict outcomes.", "Alert on elevated conflicts."),

    # Safety, security, and privacy.
    m("security.prompt_injection_detection_rate", "Prompt injection detection rate", MetricPillar.SAFETY_SECURITY, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of inputs or retrieved content flagged for injection.", "RAG and agents need defense against hostile instructions.", "%", COMMON_DIMS + ("source", "detector"), "Scan user input, retrieved text, and tool output.", "Alert on attack spikes or detector outage."),
    m("security.jailbreak_success_rate", "Jailbreak success rate", MetricPillar.SAFETY_SECURITY, SignalType.EVAL, RolloutTier.LAUNCH_BLOCKER, "Percent of adversarial prompts that bypass policy.", "A direct release gate for safety controls.", "%", COMMON_DIMS + ("eval_suite",), "Run red-team and adversarial evals in CI and pre-release.", "Block release above tolerated rate."),
    m("security.pii_input_rate", "PII input rate", MetricPillar.SAFETY_SECURITY, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of requests containing personal data.", "Determines privacy controls, retention, and customer commitments.", "%", COMMON_DIMS + ("pii_type",), "Run DLP/redaction detector before persistence/provider call.", "Alert on new PII categories or tenant policy breach."),
    m("security.pii_output_leakage_rate", "PII output leakage rate", MetricPillar.SAFETY_SECURITY, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of responses containing disallowed PII.", "High-severity trust and compliance metric.", "%", COMMON_DIMS + ("pii_type",), "Scan responses before delivery and in sampled audit.", "Page on any confirmed leakage in strict workflows."),
    m("security.secret_detection_rate", "Secret detection rate", MetricPillar.SAFETY_SECURITY, SignalType.COUNTER, RolloutTier.LAUNCH_BLOCKER, "Detected API keys, tokens, credentials, or secrets in prompts/logs/outputs.", "Secrets can leak through support tickets, code RAG, or tool logs.", "count", COMMON_DIMS + ("secret_type", "location"), "Scan ingress, logs, traces, retrieved chunks, and generated text.", "Page on confirmed secret exposure."),
    m("security.policy_violation_rate", "Policy violation rate", MetricPillar.SAFETY_SECURITY, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of requests or outputs violating content, privacy, or business policy.", "Summarizes whether controls are holding in production.", "%", COMMON_DIMS + ("policy_category",), "Combine deterministic policy checks, classifiers, and review labels.", "Alert on breach of policy SLO."),
    m("security.tenant_isolation_violation_rate", "Tenant isolation violation rate", MetricPillar.SAFETY_SECURITY, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Cross-tenant retrieval, memory, trace, or output leakage events.", "Multi-tenant field deployments live or die on isolation.", "events", ("environment", "tenant_id", "source_tenant", "target_tenant", "component"), "Validate tenant filters at retrieval, memory, cache, and logging boundaries.", "Page on any confirmed violation."),
    m("security.authz_denial_rate", "Authorization denial rate", MetricPillar.SAFETY_SECURITY, SignalType.GAUGE, RolloutTier.FIRST_WEEK, "Percent of AI or tool actions denied by authorization.", "High denials reveal integration, role, or policy mismatch.", "%", ("tenant_id", "use_case", "user_role", "tool_name", "resource_type"), "Record authz decision and reason.", "Alert on spikes after permission changes."),
    m("security.retention_policy_compliance", "Retention policy compliance", MetricPillar.SAFETY_SECURITY, SignalType.GAUGE, RolloutTier.SCALE_UP, "Percent of logs/traces/prompts/responses retained according to policy.", "Observability data itself can become sensitive data risk.", "%", ("environment", "tenant_id", "data_class", "storage"), "Audit storage TTLs, deletion jobs, and legal holds.", "Alert on expired data still present."),

    # Cost and capacity.
    m("cost.cost_per_request", "Cost per request", MetricPillar.COST_CAPACITY, SignalType.HISTOGRAM, RolloutTier.LAUNCH_BLOCKER, "Estimated model, embedding, reranking, tool, and infra cost per top-level request.", "FDEs need unit economics before scale surprises everyone.", "currency", COMMON_DIMS + ("route",), "Join token usage, provider price table, cache, and infra estimates.", "Alert on p95 or average budget breach."),
    m("cost.cost_per_successful_task", "Cost per successful task", MetricPillar.COST_CAPACITY, SignalType.GAUGE, RolloutTier.SCALE_UP, "Total cost divided by successful business tasks.", "Better than raw cost because it accounts for quality.", "currency/task", ("tenant_id", "use_case", "task_type"), "Join cost telemetry with task success labels.", "Optimize if cost rises while success is flat."),
    m("cost.budget_burn_rate", "Budget burn rate", MetricPillar.COST_CAPACITY, SignalType.GAUGE, RolloutTier.FIRST_WEEK, "Actual spend pace relative to budget.", "Prevents invoice shock during pilots.", "ratio", ("environment", "tenant_id", "use_case", "cost_center"), "Aggregate estimated cost over time against budget.", "Alert at 50/80/100% budget thresholds."),
    m("cost.token_waste_ratio", "Token waste ratio", MetricPillar.COST_CAPACITY, SignalType.GAUGE, RolloutTier.OPTIMIZE, "Tokens not contributing to final answer or accepted output.", "Finds bloated prompts, unused context, and verbose responses.", "%", COMMON_DIMS + ("token_source",), "Estimate from context utilization, accepted output length, and prompt sections.", "Optimize when consistently high."),
    m("cost.cache_savings", "Cache savings", MetricPillar.COST_CAPACITY, SignalType.GAUGE, RolloutTier.OPTIMIZE, "Estimated cost avoided by cache hits.", "Helps justify caching complexity.", "currency", ("tenant_id", "use_case", "cache_type", "model"), "Compare cached path cost to uncached estimated cost.", "Track as optimization KPI."),
    m("capacity.concurrency", "Concurrent AI requests", MetricPillar.COST_CAPACITY, SignalType.GAUGE, RolloutTier.FIRST_WEEK, "In-flight requests by service, provider, and tenant.", "Capacity issues show first as concurrency saturation.", "requests", ("environment", "tenant_id", "service", "provider"), "Track active requests and worker occupancy.", "Alert near configured capacity."),
    m("capacity.provider_quota_utilization", "Provider quota utilization", MetricPillar.COST_CAPACITY, SignalType.GAUGE, RolloutTier.FIRST_WEEK, "Usage of provider RPM, TPM, batch, or GPU quotas.", "Lets field teams negotiate quota before launch events.", "%", ("environment", "tenant_id", "provider", "quota_type"), "Read provider headers and internal counters.", "Warn above 70%; alert above 90%."),
    m("capacity.gpu_utilization", "GPU utilization", MetricPillar.COST_CAPACITY, SignalType.GAUGE, RolloutTier.SCALE_UP, "GPU memory, compute, and batch utilization for self-hosted models.", "Needed for self-hosted serving economics.", "%", ("environment", "cluster", "model", "gpu_type"), "Collect from serving stack and hardware exporters.", "Alert on saturation or under-utilization."),

    # Drift, data, and release change.
    m("drift.input_topic_drift", "Input topic drift", MetricPillar.DRIFT_DATA, SignalType.GAUGE, RolloutTier.SCALE_UP, "Change in topic distribution of user requests.", "New topics can invalidate eval coverage and retrieval assumptions.", "score", ("tenant_id", "use_case", "language", "topic"), "Compare embeddings/topics against reference windows.", "Review when drift exceeds threshold."),
    m("drift.embedding_distribution_shift", "Embedding distribution shift", MetricPillar.DRIFT_DATA, SignalType.GAUGE, RolloutTier.SCALE_UP, "Distribution change in query or document embeddings.", "Detects corpus, user, or model changes that break retrieval.", "score", ("tenant_id", "use_case", "index", "embedding_model"), "Compare centroid, covariance, or distance histograms.", "Alert after index/model changes."),
    m("drift.output_style_drift", "Output style drift", MetricPillar.DRIFT_DATA, SignalType.GAUGE, RolloutTier.OPTIMIZE, "Change in tone, length, format, or reading level.", "Subtle style drift can reduce adoption even when facts are right.", "score", COMMON_DIMS + ("style_feature",), "Track output length, readability, schema fields, tone labels.", "Investigate after prompt/model release."),
    m("drift.language_distribution", "Language distribution", MetricPillar.DRIFT_DATA, SignalType.GAUGE, RolloutTier.SCALE_UP, "Request and response language mix.", "Important for multinational deployments and eval coverage.", "%", ("tenant_id", "use_case", "language"), "Run lightweight language detection on inputs/outputs.", "Alert on unsupported-language growth."),
    m("data.training_serving_skew", "Training-serving skew", MetricPillar.DRIFT_DATA, SignalType.GAUGE, RolloutTier.SCALE_UP, "Difference between offline eval data and production traffic.", "Explains why lab evals do not match field behavior.", "score", ("tenant_id", "use_case", "eval_suite", "feature"), "Compare distributions of production samples and eval datasets.", "Refresh evals when skew grows."),
    m("data.feedback_label_coverage", "Feedback label coverage", MetricPillar.DRIFT_DATA, SignalType.GAUGE, RolloutTier.FIRST_WEEK, "Percent of traffic with human/user feedback labels.", "Without labels, quality monitoring degrades into vibes.", "%", ("tenant_id", "use_case", "task_type", "user_segment"), "Track ratings, approvals, edits, escalations, and review samples.", "Alert if sample target is missed."),
    m("data.eval_dataset_freshness", "Eval dataset freshness", MetricPillar.DRIFT_DATA, SignalType.GAUGE, RolloutTier.SCALE_UP, "Age of eval cases relative to current production patterns.", "Stale evals produce false release confidence.", "days", ("use_case", "eval_suite", "domain"), "Record eval case creation/update times and coverage.", "Refresh when older than release policy."),

    # Explainability and auditability.
    m("explain.explanation_availability", "Explanation availability", MetricPillar.EXPLAINABILITY, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of decisions with a user-appropriate reason or rationale.", "High-impact deployments need understandable reasons, not just answers.", "%", COMMON_DIMS + ("decision_type",), "Require rationale field or decision trace for eligible outputs.", "Gate high-impact workflows."),
    m("explain.evidence_attribution_rate", "Evidence attribution rate", MetricPillar.EXPLAINABILITY, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of claims/actions linked to evidence, rule, source, or tool result.", "Turns opaque AI output into inspectable field evidence.", "%", COMMON_DIMS + ("source_type",), "Attach source ids, rule ids, tool ids, or retrieved chunks to output claims.", "Alert when attribution drops."),
    m("explain.rationale_consistency", "Rationale consistency", MetricPillar.EXPLAINABILITY, SignalType.EVAL, RolloutTier.SCALE_UP, "Whether explanations are consistent with the actual decision path.", "Post-hoc explanations can be misleading.", "score", COMMON_DIMS + ("eval_suite",), "Compare rationale to trace/tool/source evidence.", "Review when consistency falls."),
    m("explain.feature_or_factor_coverage", "Feature or factor coverage", MetricPillar.EXPLAINABILITY, SignalType.GAUGE, RolloutTier.SCALE_UP, "Percent of decisions listing material factors, constraints, or source fields.", "Useful in risk, operations, and customer-facing decisions.", "%", COMMON_DIMS + ("decision_type",), "Validate explanation payload includes required factors.", "Alert for regulated workflows."),
    m("explain.user_challenge_rate", "User challenge rate", MetricPillar.EXPLAINABILITY, SignalType.GAUGE, RolloutTier.SCALE_UP, "How often users contest, request clarification, or ask for human review.", "High challenge rate often signals low trust or poor explanation.", "%", ("tenant_id", "use_case", "decision_type", "user_segment"), "Capture challenge/appeal/clarification actions.", "Investigate spikes."),

    # Governance and release management.
    m("gov.model_version_coverage", "Model version coverage", MetricPillar.GOVERNANCE, SignalType.AUDIT, RolloutTier.LAUNCH_BLOCKER, "Percent of traces with model name, version, provider, and parameters.", "Version gaps make audits and rollback analysis impossible.", "%", COMMON_DIMS, "Attach model metadata at gateway.", "Alert below 100% for production."),
    m("gov.prompt_version_coverage", "Prompt version coverage", MetricPillar.GOVERNANCE, SignalType.AUDIT, RolloutTier.LAUNCH_BLOCKER, "Percent of traces with prompt/template version.", "Prompt changes are releases and need traceability.", "%", COMMON_DIMS, "Use immutable prompt ids or hashes.", "Alert below 100% for production."),
    m("gov.approval_artifact_coverage", "Approval artifact coverage", MetricPillar.GOVERNANCE, SignalType.AUDIT, RolloutTier.LAUNCH_BLOCKER, "Percent of production model/prompt/tool releases with approval evidence.", "FDEs need defensible customer change control.", "%", ("environment", "use_case", "release_id", "artifact_type"), "Link release metadata to approvals, evals, and risk signoff.", "Block release if missing."),
    m("gov.audit_log_integrity", "Audit log integrity", MetricPillar.GOVERNANCE, SignalType.AUDIT, RolloutTier.LAUNCH_BLOCKER, "Completeness and tamper evidence of audit logs.", "Critical for incident response and regulated deployments.", "%", ("environment", "tenant_id", "storage", "event_type"), "Hash-chain or immutable-store key events.", "Page on write failure or integrity gap."),
    m("gov.model_card_completeness", "Model card completeness", MetricPillar.GOVERNANCE, SignalType.AUDIT, RolloutTier.SCALE_UP, "Required documentation fields completed for model/system cards.", "Keeps customer, legal, and support teams aligned.", "%", ("use_case", "model", "model_version"), "Validate required metadata fields.", "Release gate for governed use cases."),
    m("gov.rollback_readiness", "Rollback readiness", MetricPillar.GOVERNANCE, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Whether previous stable model/prompt/tool versions can be restored.", "Rollback is the field engineer's parachute.", "score", ("environment", "use_case", "component"), "Test rollback path and record last successful rollback drill.", "Block high-risk release if not ready."),
    m("gov.change_failure_rate", "AI change failure rate", MetricPillar.GOVERNANCE, SignalType.GAUGE, RolloutTier.SCALE_UP, "Percent of AI releases causing rollback, incident, or SLO breach.", "Measures release discipline.", "%", ("environment", "use_case", "component", "release_type"), "Join deployment records to incidents and SLO breaches.", "Review when trend worsens."),

    # User and business outcomes.
    m("biz.feature_adoption_rate", "Feature adoption rate", MetricPillar.USER_BUSINESS, SignalType.BUSINESS, RolloutTier.FIRST_WEEK, "Eligible users or workflows using the AI feature.", "Adoption validates that field deployment actually landed.", "%", ("tenant_id", "use_case", "user_segment", "workflow"), "Compare eligible population to active AI usage.", "Investigate low adoption despite availability."),
    m("biz.deflection_rate", "Deflection rate", MetricPillar.USER_BUSINESS, SignalType.BUSINESS, RolloutTier.SCALE_UP, "Percent of cases resolved without escalation due to AI.", "Common support/copilot value metric.", "%", ("tenant_id", "use_case", "case_type"), "Join AI usage with ticket/case outcomes.", "Watch with quality and CSAT to avoid false wins."),
    m("biz.handle_time_delta", "Handle time delta", MetricPillar.USER_BUSINESS, SignalType.BUSINESS, RolloutTier.SCALE_UP, "Change in task or case handling time with AI.", "Often the clearest operational ROI signal.", "seconds", ("tenant_id", "use_case", "task_type", "user_segment"), "Compare cohorts, pre/post, or A/B treatment.", "Alert if AI increases time after release."),
    m("biz.rework_rate", "Rework rate", MetricPillar.USER_BUSINESS, SignalType.BUSINESS, RolloutTier.FIRST_WEEK, "Percent of AI-assisted outcomes requiring correction.", "Catches damage hidden behind fast completion.", "%", ("tenant_id", "use_case", "task_type"), "Track reopen, correction, reversal, edit, or supervisor override events.", "Alert on increase after release."),
    m("biz.escalation_rate", "Escalation rate", MetricPillar.USER_BUSINESS, SignalType.BUSINESS, RolloutTier.FIRST_WEEK, "Percent of AI interactions escalated to human or expert queue.", "Good for spotting poor confidence, safety blocks, or user distrust.", "%", ("tenant_id", "use_case", "task_type", "escalation_reason"), "Capture explicit and automatic escalation.", "Investigate spikes by reason."),
    m("biz.csat_after_ai", "CSAT after AI", MetricPillar.USER_BUSINESS, SignalType.BUSINESS, RolloutTier.SCALE_UP, "Customer or user satisfaction after AI-assisted workflow.", "Balances automation metrics with experience quality.", "score", ("tenant_id", "use_case", "user_segment"), "Join survey/feedback to AI traces.", "Investigate divergence from operational KPIs."),
    m("biz.conversion_or_completion_lift", "Conversion or completion lift", MetricPillar.USER_BUSINESS, SignalType.BUSINESS, RolloutTier.SCALE_UP, "Business conversion, completion, or throughput change attributable to AI.", "Connects observability to executive outcomes.", "%", ("tenant_id", "use_case", "experiment", "segment"), "Use A/B, phased rollout, or causal analysis where possible.", "Review with quality and cost before scaling."),

    # Operations and incident readiness.
    m("ops.alert_precision", "Alert precision", MetricPillar.OPERATIONS, SignalType.GAUGE, RolloutTier.SCALE_UP, "Percent of alerts that represent real action-worthy incidents.", "Noisy alerts cause field teams to ignore the dashboard.", "%", ("service", "alert_name", "severity"), "Classify alert outcomes after triage.", "Tune alerts with low precision."),
    m("ops.mtta", "Mean time to acknowledge", MetricPillar.OPERATIONS, SignalType.GAUGE, RolloutTier.FIRST_WEEK, "Average time to acknowledge AI incidents.", "Critical for customer-facing managed deployments.", "minutes", ("tenant_id", "use_case", "severity"), "Join alert and incident-management timestamps.", "Alert on SLA breach."),
    m("ops.mttr", "Mean time to resolve", MetricPillar.OPERATIONS, SignalType.GAUGE, RolloutTier.FIRST_WEEK, "Average time to resolve AI incidents.", "Shows whether runbooks and ownership work.", "minutes", ("tenant_id", "use_case", "severity"), "Join incident open/close timestamps.", "Review severe or repeated incidents."),
    m("ops.runbook_coverage", "Runbook coverage", MetricPillar.OPERATIONS, SignalType.AUDIT, RolloutTier.LAUNCH_BLOCKER, "Percent of critical alerts with an owner and runbook.", "Launches fail when nobody knows what to do at 2 AM.", "%", ("service", "alert_name", "severity"), "Validate alert metadata includes runbook and escalation owner.", "Block production launch for critical gaps."),
    m("ops.incident_recurrence_rate", "Incident recurrence rate", MetricPillar.OPERATIONS, SignalType.GAUGE, RolloutTier.SCALE_UP, "Repeated incidents with same root cause.", "Shows whether fixes are durable.", "%", ("tenant_id", "use_case", "root_cause", "component"), "Tag incident postmortems and compare within rolling windows.", "Escalate recurring high-severity issues."),
    m("ops.canary_regression_rate", "Canary regression rate", MetricPillar.OPERATIONS, SignalType.GAUGE, RolloutTier.LAUNCH_BLOCKER, "Percent of canary metrics regressing during rollout.", "Protects customers during prompt/model/tool releases.", "%", ("environment", "use_case", "release_id", "metric_name"), "Compare canary cohort to baseline/control.", "Auto-pause or rollback on threshold breach."),
)


METRIC_BY_ID = {metric.metric_id: metric for metric in METRICS}


DASHBOARD_SECTIONS = (
    DashboardSection(
        "Executive Outcome",
        "Show whether the AI system is creating operational value without hiding quality or cost.",
        (
            "biz.feature_adoption_rate",
            "quality.task_success_rate",
            "quality.human_acceptance_rate",
            "biz.handle_time_delta",
            "cost.cost_per_successful_task",
            "biz.rework_rate",
        ),
    ),
    DashboardSection(
        "Live Health",
        "Answer the on-call question: is the AI path up, fast, and within budget right now?",
        (
            "perf.availability",
            "perf.end_to_end_latency",
            "perf.time_to_first_token",
            "perf.timeout_rate",
            "activity.retry_rate",
            "cost.budget_burn_rate",
        ),
    ),
    DashboardSection(
        "Trace Explorer",
        "Let an FDE debug one bad answer from user report to exact model, prompt, context, and tool action.",
        (
            "trace.request_trace_coverage",
            "trace.span_completeness",
            "gov.model_version_coverage",
            "gov.prompt_version_coverage",
            "trace.replayability_completeness",
            "trace.span_error_rate",
        ),
    ),
    DashboardSection(
        "Quality and Safety",
        "Track behavior quality, policy compliance, and release regression risk.",
        (
            "quality.correctness_rate",
            "quality.hallucination_rate",
            "quality.groundedness_score",
            "quality.schema_validity_rate",
            "security.policy_violation_rate",
            "security.pii_output_leakage_rate",
        ),
    ),
    DashboardSection(
        "RAG Knowledge",
        "Validate that the system retrieves fresh, relevant, attributable knowledge.",
        (
            "rag.retrieval_hit_rate",
            "rag.recall_at_k",
            "rag.precision_at_k",
            "rag.citation_precision",
            "rag.source_freshness_lag",
            "rag.indexing_failure_rate",
        ),
    ),
    DashboardSection(
        "Agents and Tools",
        "Monitor whether agent decisions and side effects are correct, bounded, and reversible.",
        (
            "agent.tool_call_success_rate",
            "agent.tool_selection_accuracy",
            "agent.tool_argument_validity",
            "agent.loop_rate",
            "agent.unsafe_action_block_rate",
            "agent.human_approval_rate",
        ),
    ),
    DashboardSection(
        "Governance and Release",
        "Make prompts, models, tools, approvals, rollbacks, and incidents auditable.",
        (
            "gov.approval_artifact_coverage",
            "gov.audit_log_integrity",
            "gov.rollback_readiness",
            "ops.canary_regression_rate",
            "gov.change_failure_rate",
            "ops.runbook_coverage",
        ),
    ),
)


INSTRUMENTATION_EVENTS = (
    "ai.request.received",
    "ai.policy.input_checked",
    "ai.retrieval.query_built",
    "ai.retrieval.completed",
    "ai.prompt.built",
    "ai.model.requested",
    "ai.model.completed",
    "ai.tool.requested",
    "ai.tool.completed",
    "ai.policy.output_checked",
    "ai.response.delivered",
    "ai.feedback.captured",
    "ai.eval.completed",
    "ai.release.started",
    "ai.release.completed",
    "ai.incident.created",
)


BASE_METRIC_IDS = {
    metric.metric_id
    for metric in METRICS
    if metric.tier == RolloutTier.LAUNCH_BLOCKER
    or metric.pillar
    in {
        MetricPillar.TRACING,
        MetricPillar.MODEL_ACTIVITY,
        MetricPillar.PERFORMANCE,
        MetricPillar.QUALITY,
        MetricPillar.SAFETY_SECURITY,
        MetricPillar.COST_CAPACITY,
        MetricPillar.GOVERNANCE,
        MetricPillar.OPERATIONS,
    }
}


def select_metrics(profile: LLMOpsProfile) -> list[MetricDefinition]:
    selected = set(BASE_METRIC_IDS)
    architecture = {item.lower() for item in profile.architecture}

    if profile.has_rag or "rag" in architecture or "retrieval" in architecture:
        selected.update(metric.metric_id for metric in METRICS if metric.pillar == MetricPillar.RAG)
    if profile.has_agents or profile.has_tools or "agent" in architecture or "tools" in architecture:
        selected.update(metric.metric_id for metric in METRICS if metric.pillar == MetricPillar.AGENTS_TOOLS)
    if profile.has_streaming or "streaming" in architecture:
        selected.add("activity.streaming_abort_rate")
        selected.add("perf.time_to_first_token")
    if profile.handles_pii or profile.regulated:
        selected.update(metric.metric_id for metric in METRICS if metric.pillar in {MetricPillar.SAFETY_SECURITY, MetricPillar.GOVERNANCE, MetricPillar.EXPLAINABILITY})
    if profile.multi_tenant:
        selected.add("security.tenant_isolation_violation_rate")
        selected.add("trace.customer_journey_linkage")
    if profile.human_in_the_loop:
        selected.add("quality.human_acceptance_rate")
        selected.add("quality.edit_distance_after_suggestion")
        selected.add("agent.human_approval_rate")

    selected.update(metric.metric_id for metric in METRICS if metric.pillar in {MetricPillar.USER_BUSINESS, MetricPillar.DRIFT_DATA})
    return sorted((METRIC_BY_ID[metric_id] for metric_id in selected), key=lambda item: (item.pillar.value, item.metric_id))


def launch_gates(profile: LLMOpsProfile) -> list[str]:
    gates = [
        "End-to-end trace coverage is at least 99% for production traffic.",
        "Every response trace includes model version, prompt version, release id, and policy decision.",
        "Latency, availability, timeout, retry, and cost SLOs are defined per workflow.",
        "Regression eval suite passes for task success, instruction following, schema validity, and safety.",
        "Runbooks, alert owners, rollback path, and canary metrics are tested before launch.",
    ]
    if profile.has_rag:
        gates.append("RAG evals meet retrieval hit, recall@k, citation precision, and source freshness thresholds.")
    if profile.has_agents or profile.has_tools:
        gates.append("Tool schemas, authz, idempotency, unsafe-action blocks, and human approval paths are tested.")
    if profile.handles_pii or profile.regulated:
        gates.append("PII detection/redaction, retention controls, audit logs, and explanation/evidence attribution are verified.")
    if profile.multi_tenant:
        gates.append("Tenant isolation tests cover retrieval, memory, cache, trace storage, and tool authorization.")
    return gates


def rollout_notes(profile: LLMOpsProfile) -> list[str]:
    return [
        "Start with a narrow golden-path dashboard: health, trace explorer, quality, safety, and cost.",
        "Create tenant/use-case dimensions on day one; retrofitting them later is painful.",
        "Keep raw prompt/response retention minimal and policy-bound; store redacted hashes when full text is not needed.",
        "Treat prompts, retrieval configs, tools, and safety policies as release artifacts, not loose runtime settings.",
        "For pilots, pair quantitative metrics with weekly trace review sessions; the best field insights often start from five bad traces.",
        f"Primary business KPI to connect with AI telemetry: {profile.business_kpi or 'define one before scale-up'}.",
    ]


def build_plan(profile: LLMOpsProfile) -> ObservabilityPlan:
    return ObservabilityPlan(
        profile_name=profile.name,
        generated_on=TODAY,
        selected_metrics=select_metrics(profile),
        launch_gates=launch_gates(profile),
        dashboard_sections=list(DASHBOARD_SECTIONS),
        instrumentation_events=list(INSTRUMENTATION_EVENTS),
        fde_rollout_notes=rollout_notes(profile),
    )


def demo_profile() -> LLMOpsProfile:
    return LLMOpsProfile(
        name="Enterprise Support RAG Agent",
        use_case="Customer support copilot that retrieves policy docs, drafts answers, and opens follow-up tickets.",
        architecture=("rag", "agent", "tools", "streaming"),
        criticality="high",
        users="Support agents, team leads, and operations managers.",
        business_kpi="first contact resolution and average handle time",
        regulated=True,
        has_rag=True,
        has_agents=True,
        has_tools=True,
        has_streaming=True,
        multi_tenant=True,
        handles_pii=True,
        human_in_the_loop=True,
        external_model_provider=True,
    )


def sample_profile_json() -> str:
    return json.dumps(asdict(demo_profile()), indent=2)


def metrics_to_json(metrics: Iterable[MetricDefinition]) -> str:
    return json.dumps([asdict(metric) for metric in metrics], indent=2)


def metrics_to_markdown(metrics: Iterable[MetricDefinition]) -> str:
    grouped: dict[MetricPillar, list[MetricDefinition]] = {}
    for metric in metrics:
        grouped.setdefault(metric.pillar, []).append(metric)

    lines = ["# LLMOps Observability Metric Catalogue", ""]
    for pillar in MetricPillar:
        items = grouped.get(pillar, [])
        if not items:
            continue
        lines.extend([f"## {pillar.value.replace('_', ' ').title()}", ""])
        for metric in sorted(items, key=lambda item: item.metric_id):
            dims = ", ".join(metric.dimensions)
            lines.extend(
                [
                    f"### `{metric.metric_id}`",
                    f"- Name: {metric.name}",
                    f"- Tier: `{metric.tier.value}`",
                    f"- Signal: `{metric.signal_type.value}`",
                    f"- Description: {metric.description}",
                    f"- FDE lens: {metric.why_fde_cares}",
                    f"- Unit: {metric.unit}",
                    f"- Dimensions: {dims}",
                    f"- Collection: {metric.collection}",
                    f"- Alert guidance: {metric.alert_guidance}",
                    f"- Owner: {metric.owner}",
                    "",
                ]
            )
    return "\n".join(lines).strip()


def dashboard_to_markdown() -> str:
    lines = ["# LLMOps Dashboard Blueprint", ""]
    for section in DASHBOARD_SECTIONS:
        lines.extend([f"## {section.name}", section.purpose, ""])
        lines.extend(f"- `{metric_id}`" for metric_id in section.metrics)
        lines.append("")
    return "\n".join(lines).strip()


def guide() -> str:
    return dedent(
        """
        LLMOps observability from a Forward Deployed Engineer standpoint:

        1. Trace first
           Every user-facing answer must connect user/session/workflow -> policy
           check -> retrieval -> prompt -> model -> tool calls -> output check ->
           feedback. If you cannot replay the trace, you cannot debug the field.

        2. Separate health from quality
           Uptime and latency only prove the system responded. You still need task
           success, groundedness, hallucination rate, schema validity, refusal
           correctness, and human acceptance/edit metrics.

        3. Treat RAG and agents as first-class systems
           RAG needs corpus coverage, freshness, retrieval quality, and citation
           quality. Agents need tool choice, argument validity, loop detection,
           approval, idempotency, authorization, and unsafe-action blocks.

        4. Make cost observable per successful task
           Token spend alone is not enough. Track cost per request, per workflow,
           per tenant, and per successful business outcome.

        5. Build for incident response
           Add canaries, rollback readiness, runbook coverage, alert precision,
           MTTA/MTTR, and change failure rate before a customer escalation proves
           you needed them.

        6. Connect to business value
           The field view should show adoption, handle time, deflection, rework,
           CSAT, completion lift, and workflow throughput beside quality and cost.

        Commands:
           python ai/llm-metrics.py --mode guide
           python ai/llm-metrics.py --mode sample-profile
           python ai/llm-metrics.py --mode catalog --format markdown
           python ai/llm-metrics.py --mode dashboard --format markdown
           python ai/llm-metrics.py --mode demo --format markdown
           python ai/llm-metrics.py --mode assess --input llmops_profile.json --format json
        """
    ).strip()


def load_profile(path: Path) -> LLMOpsProfile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return LLMOpsProfile.from_mapping(payload)


def parse_pillar(raw: Optional[str]) -> Optional[MetricPillar]:
    if not raw:
        return None
    return MetricPillar(raw.strip().lower())


def main() -> None:
    parser = argparse.ArgumentParser(description="LLMOps observability metrics catalogue")
    parser.add_argument(
        "--mode",
        choices=("guide", "sample-profile", "catalog", "dashboard", "demo", "assess"),
        default="guide",
    )
    parser.add_argument("--input", help="Path to LLMOps profile JSON.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--pillar", choices=[pillar.value for pillar in MetricPillar], help="Filter catalog by pillar.")
    args = parser.parse_args()

    if args.mode == "guide":
        print(guide())
        return

    if args.mode == "sample-profile":
        print(sample_profile_json())
        return

    if args.mode == "catalog":
        pillar = parse_pillar(args.pillar)
        metrics = [metric for metric in METRICS if pillar is None or metric.pillar == pillar]
        print(metrics_to_markdown(metrics) if args.format == "markdown" else metrics_to_json(metrics))
        return

    if args.mode == "dashboard":
        if args.format == "markdown":
            print(dashboard_to_markdown())
        else:
            print(json.dumps([asdict(section) for section in DASHBOARD_SECTIONS], indent=2))
        return

    profile = demo_profile() if args.mode == "demo" else load_profile(Path(args.input or ""))
    plan = build_plan(profile)
    print(plan.to_markdown() if args.format == "markdown" else plan.to_json())


if __name__ == "__main__":
    main()
