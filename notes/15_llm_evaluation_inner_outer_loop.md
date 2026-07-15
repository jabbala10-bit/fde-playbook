# 15 — LLM Evaluation: Inner & Outer Loop

> **Why this matters for FDEs:** "The model works great in my testing"
> has ended more AI projects than any technical failure. Real evaluation
> is the discipline that separates a demo from a production system.
> This file covers the complete evaluation framework from dev-time
> iteration to production monitoring.

---

## 1. The Two Evaluation Loops

```
┌─────────────────────────────────────────────────────────────────────┐
│                    THE EVALUATION FRAMEWORK                        │
│                                                                     │
│  INNER LOOP (Development)          OUTER LOOP (Production)        │
│  ────────────────────────          ────────────────────────        │
│  Fast, cheap, iterative            Slower, rigorous, ongoing       │
│                                                                     │
│  Goal: Improve the model/          Goal: Monitor model quality     │
│  prompt/pipeline quickly           after deployment; detect drift  │
│                                                                     │
│  Methods:                          Methods:                        │
│  - Unit tests on golden set        - A/B tests (AutoSxS)          │
│  - LLM-as-judge spot checks        - Human evaluation sample      │
│  - Ragas metrics on RAG            - Business outcome tracking     │
│  - Component-level testing         - Drift detection alerts        │
│                                                                     │
│  Tools: LangSmith, Ragas,          Tools: Vertex AI AutoSxS,      │
│         custom pytest fixtures     Cloud Monitoring, LangSmith     │
│                                                                     │
│  Cadence: Every commit             Cadence: Daily/weekly           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Building a Golden Dataset — The Foundation of All Evaluation

A **golden dataset** is a curated set of question-answer pairs that
represent the quality bar for your specific deployment. Without it,
evaluation is just vibes.

### Golden Dataset Structure
```python
# Each entry in the golden dataset represents one test case
golden_dataset = [
    {
        "id": "GD-001",
        "category": "factual_retrieval",  # type of question
        "query": "What is the company's return policy for electronics?",
        "reference_answer": (
            "Electronics can be returned within 30 days of purchase with "
            "original receipt. Items must be in original packaging. After "
            "30 days, warranty service only. Extended return policy applies "
            "to Pro members (90 days). Source: Returns Policy v2.3, Section 4."
        ),
        "required_facts": [
            "30 days return window",
            "original receipt required",
            "original packaging required",
            "90 days for Pro members"
        ],
        "source_documents": ["Returns Policy v2.3"],
        "difficulty": "medium",
        "notes": "Common support question; must be accurate to avoid customer disputes"
    },
    {
        "id": "GD-002",
        "category": "multi_step_reasoning",
        "query": "If a Pro member bought a TV on June 1st, what is the last day they can return it?",
        "reference_answer": "August 29th (90 days from June 1st).",
        "required_facts": ["August 29th", "90 days calculation"],
        "source_documents": ["Returns Policy v2.3"],
        "difficulty": "hard",
        "notes": "Requires date arithmetic + policy lookup"
    },
    {
        "id": "GD-003",
        "category": "out_of_scope",
        "query": "What is the CEO's home address?",
        "reference_answer": None,  # should refuse to answer
        "expected_behavior": "refusal",
        "notes": "Test that agent doesn't hallucinate or retrieve PII"
    }
]
```

### Golden Dataset Construction Rules
```
MINIMUM VIABLE: 50 examples across key categories
PRODUCTION QUALITY: 200+ examples, reviewed by domain experts
DISTRIBUTION: should mirror ACTUAL production query distribution

Coverage requirements:
□ All major use cases (80% of expected real queries)
□ Edge cases (ambiguous questions, multi-step reasoning)
□ Failure modes to prevent (hallucination, out-of-scope, PII)
□ Hard negatives (questions that look answerable but aren't)
□ Category breakdown matches real usage patterns

Quality requirements:
□ Every reference answer verified by a domain expert, not the FDE
□ "Required facts" list created per entry (for automated fact checking)
□ Source documents linked (for RAG faithfulness testing)
□ Difficulty labeled (easy/medium/hard) for stratified analysis
```

---

## 3. Inner Loop: Automated Metrics

### Ragas — RAG-Specific Metrics
```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,          # does the answer match the retrieved context?
    answer_relevancy,      # does the answer address the question?
    context_precision,     # are the retrieved chunks relevant?
    context_recall,        # did we retrieve all relevant information?
)
from datasets import Dataset

# Prepare evaluation dataset in Ragas format
def prepare_ragas_dataset(golden_set: list, rag_outputs: list) -> Dataset:
    """
    golden_set: your golden dataset entries
    rag_outputs: what your RAG system actually returned for each query
    """
    data = {
        "question": [],
        "answer": [],           # what the RAG system returned
        "contexts": [],         # what documents were retrieved
        "ground_truth": []      # the reference answer from golden dataset
    }
    
    for gold, output in zip(golden_set, rag_outputs):
        data["question"].append(gold["query"])
        data["answer"].append(output["answer"])
        data["contexts"].append(output["retrieved_chunks"])
        data["ground_truth"].append(gold["reference_answer"])
    
    return Dataset.from_dict(data)

def run_ragas_evaluation(golden_set: list, rag_outputs: list) -> dict:
    """Run Ragas evaluation and return metrics."""
    dataset = prepare_ragas_dataset(golden_set, rag_outputs)
    
    result = evaluate(
        dataset,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        ],
        llm=your_evaluation_llm,      # use a strong model as judge
        embeddings=your_embeddings,
    )
    
    metrics = result.to_pandas().mean().to_dict()
    
    print(f"Faithfulness:        {metrics['faithfulness']:.3f}  (target: > 0.85)")
    print(f"Answer Relevancy:    {metrics['answer_relevancy']:.3f}  (target: > 0.80)")
    print(f"Context Precision:   {metrics['context_precision']:.3f}  (target: > 0.75)")
    print(f"Context Recall:      {metrics['context_recall']:.3f}  (target: > 0.70)")
    
    return metrics
```

### LLM-as-Judge — Custom Evaluation for Your Specific Criteria
```python
import json
from google.cloud import aiplatform

def evaluate_with_llm_judge(
    query: str,
    reference_answer: str,
    system_answer: str,
    required_facts: list[str]
) -> dict:
    """
    Use a strong LLM to evaluate the quality of a response.
    The judge model is different from the production model.
    """
    
    judge_prompt = f"""You are an expert evaluator for an enterprise AI assistant.
    
ORIGINAL QUESTION:
{query}

REFERENCE ANSWER (ground truth):
{reference_answer}

REQUIRED FACTS (must be present in a correct answer):
{chr(10).join(f"- {fact}" for fact in required_facts)}

SYSTEM ANSWER (what the AI produced):
{system_answer}

Evaluate the system answer on these 4 dimensions (score each 1-5):

1. FACTUAL_ACCURACY: Does the answer contain correct facts from the reference?
   1=Mostly wrong, 3=Partially correct, 5=Fully accurate
   
2. COMPLETENESS: Does the answer cover all required facts?
   1=Missing most facts, 3=Missing some, 5=All required facts present
   
3. FAITHFULNESS: Is the answer grounded in retrieved content (no hallucination)?
   1=Clear hallucination, 3=Some unsupported claims, 5=Fully grounded
   
4. CONCISENESS: Is the answer appropriately concise without unnecessary padding?
   1=Way too verbose/rambling, 3=Acceptable, 5=Perfectly concise

Respond ONLY with valid JSON:
{{
    "factual_accuracy": <1-5>,
    "completeness": <1-5>,
    "faithfulness": <1-5>,
    "conciseness": <1-5>,
    "overall": <1-5>,
    "reasoning": "<1-2 sentence explanation of the main issues if any>",
    "pass": <true if overall >= 4, false otherwise>
}}"""

    # Use your strongest available model as the judge
    # (Gemini 1.5 Pro, GPT-4o, or Claude 3.5 Sonnet work well)
    response = call_judge_llm(judge_prompt)
    
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {"error": "Judge returned invalid JSON", "raw": response}

def run_full_evaluation(golden_dataset: list, system_responses: list) -> dict:
    """Run evaluation across the full golden dataset."""
    results = []
    
    for gold, response in zip(golden_dataset, system_responses):
        if gold.get("expected_behavior") == "refusal":
            # Special handling for out-of-scope queries
            passed = "I cannot" in response["answer"] or "don't have" in response["answer"]
            results.append({"id": gold["id"], "pass": passed, "category": "refusal"})
        else:
            score = evaluate_with_llm_judge(
                query=gold["query"],
                reference_answer=gold["reference_answer"],
                system_answer=response["answer"],
                required_facts=gold.get("required_facts", [])
            )
            score["id"] = gold["id"]
            score["category"] = gold["category"]
            score["difficulty"] = gold["difficulty"]
            results.append(score)
    
    # Aggregate by category and difficulty
    import pandas as pd
    df = pd.DataFrame(results)
    
    summary = {
        "overall_pass_rate": df["pass"].mean(),
        "by_category": df.groupby("category")["pass"].mean().to_dict(),
        "by_difficulty": df.groupby("difficulty")["pass"].mean().to_dict(),
        "total_evaluated": len(results),
        "passed": df["pass"].sum(),
    }
    
    print(f"\n{'='*60}")
    print(f"EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"Overall Pass Rate: {summary['overall_pass_rate']:.1%}")
    print(f"\nBy Category:")
    for cat, rate in summary['by_category'].items():
        print(f"  {cat}: {rate:.1%}")
    print(f"\nBy Difficulty:")
    for diff, rate in summary['by_difficulty'].items():
        print(f"  {diff}: {rate:.1%}")
    
    return summary
```

---

## 4. Outer Loop: Vertex AI AutoSxS (Side-by-Side Evaluation)

**AutoSxS** is Google's managed evaluation service. It compares two
model responses head-to-head using a strong judge model at scale.

```python
from google.cloud import aiplatform
import pandas as pd

def run_autosxs_evaluation(
    project_id: str,
    location: str,
    model_a_responses_gcs: str,  # gs://bucket/model_a_responses.jsonl
    model_b_responses_gcs: str,  # gs://bucket/model_b_responses.jsonl
    golden_set_gcs: str,         # gs://bucket/golden_set.jsonl
    inference_output_gcs: str    # gs://bucket/autosxs_results/
) -> dict:
    """
    Compare two model responses using AutoSxS.
    model_a = current production model
    model_b = candidate new model
    """
    
    aiplatform.init(project=project_id, location=location)
    
    # AutoSxS pipeline configuration
    pipeline_spec = {
        "inputs": {
            "task": "question_answering",  # or "summarization", "text_generation"
            "autorater_prompt_parameters": {
                "inference_instruction": "Answer the following question based on the provided context.",
                "inference_context": "{{context}}",  # reference fields in your JSONL
            },
            "response_column_a": "response_a",
            "response_column_b": "response_b",
            "human_preference_column": "human_preference",  # optional if you have labels
        },
        "input_dataset_paths": [golden_set_gcs],
        "response_paths_a": [model_a_responses_gcs],
        "response_paths_b": [model_b_responses_gcs],
        "output_path": inference_output_gcs,
    }
    
    # Run the evaluation pipeline
    job = aiplatform.PipelineJob(
        display_name="autosxs-evaluation",
        template_path="https://us-kfp.pkg.dev/ml-pipeline/google-cloud-registry/autosxs-template/latest",
        parameter_values=pipeline_spec,
    )
    job.run(sync=True)
    
    # Read results
    results_df = pd.read_json(
        f"{inference_output_gcs}/judgments.jsonl",
        lines=True
    )
    
    win_rate_b = (results_df["preference"] == "B").mean()
    win_rate_a = (results_df["preference"] == "A").mean()
    tie_rate = (results_df["preference"] == "DRAW").mean()
    
    print(f"Model A (current) win rate: {win_rate_a:.1%}")
    print(f"Model B (candidate) win rate: {win_rate_b:.1%}")
    print(f"Tie rate: {tie_rate:.1%}")
    
    # Model B needs > 55% win rate to justify deployment (arbitrary threshold
    # — agree with client on this number before the evaluation runs!)
    should_deploy_b = win_rate_b > 0.55
    
    return {
        "win_rate_a": win_rate_a,
        "win_rate_b": win_rate_b,
        "tie_rate": tie_rate,
        "recommendation": "DEPLOY B" if should_deploy_b else "KEEP A",
        "confidence": "HIGH" if abs(win_rate_b - win_rate_a) > 0.10 else "LOW"
    }
```

---

## 5. Regression Testing — Don't Break What Works

```python
import pytest

# tests/test_agent_quality.py
# Run as part of CI/CD pipeline before every deployment

class TestAgentQuality:
    
    @pytest.fixture(scope="class")
    def agent_responses(self, golden_dataset):
        """Run the agent against the full golden dataset once."""
        responses = []
        for item in golden_dataset:
            response = call_agent(item["query"])
            responses.append(response)
        return responses
    
    def test_overall_pass_rate_minimum(self, golden_dataset, agent_responses):
        """Overall pass rate must be >= 85%."""
        results = run_full_evaluation(golden_dataset, agent_responses)
        assert results["overall_pass_rate"] >= 0.85, \
            f"Pass rate {results['overall_pass_rate']:.1%} < 85% threshold"
    
    def test_factual_retrieval_category(self, golden_dataset, agent_responses):
        """Factual retrieval questions must pass at >= 90%."""
        factual_items = [g for g in golden_dataset if g["category"] == "factual_retrieval"]
        factual_responses = [r for g, r in zip(golden_dataset, agent_responses)
                            if g["category"] == "factual_retrieval"]
        results = run_full_evaluation(factual_items, factual_responses)
        assert results["overall_pass_rate"] >= 0.90, \
            f"Factual retrieval pass rate {results['overall_pass_rate']:.1%} < 90%"
    
    def test_refusal_behavior(self, golden_dataset, agent_responses):
        """Out-of-scope queries must be refused 100% of the time."""
        refusal_items = [(g, r) for g, r in zip(golden_dataset, agent_responses)
                        if g.get("expected_behavior") == "refusal"]
        
        for gold, response in refusal_items:
            assert any(phrase in response["answer"].lower() for phrase in
                      ["cannot", "don't have", "unable to", "not able to"]), \
                f"Query '{gold['query']}' was not refused. Got: {response['answer'][:100]}"
    
    def test_no_hallucination_on_hard_examples(self, golden_dataset, agent_responses):
        """Hard examples must have faithfulness score >= 4."""
        hard_items = [(g, r) for g, r in zip(golden_dataset, agent_responses)
                     if g.get("difficulty") == "hard"]
        
        for gold, response in hard_items:
            score = evaluate_with_llm_judge(
                gold["query"],
                gold["reference_answer"],
                response["answer"],
                gold.get("required_facts", [])
            )
            assert score["faithfulness"] >= 4, \
                f"ID {gold['id']}: Faithfulness {score['faithfulness']}/5 < 4. " \
                f"Reasoning: {score['reasoning']}"
```

---

## 6. Production Monitoring — Detecting Silent Degradation

```python
# Cloud Function or Cloud Run job running daily

from google.cloud import bigquery
import datetime

def check_production_quality_metrics():
    """
    Run daily quality checks on a sample of production queries.
    Alerts if quality metrics drop below thresholds.
    """
    client = bigquery.Client()
    
    # Get yesterday's production queries (sampled)
    yesterday = (datetime.date.today() - datetime.timedelta(1)).isoformat()
    
    query = f"""
    SELECT
        session_id,
        user_query,
        agent_response,
        retrieved_documents,
        response_latency_ms,
        user_feedback  -- thumbs up/down if collected
    FROM `prod.agent_logs.query_log`
    WHERE DATE(timestamp) = '{yesterday}'
    -- Sample 1% for daily evaluation (cost control)
    AND RAND() < 0.01
    LIMIT 100
    """
    
    production_sample = [dict(row) for row in client.query(query).result()]
    
    # Run LLM-as-judge on the sample
    quality_scores = []
    for row in production_sample:
        score = evaluate_with_llm_judge(
            query=row["user_query"],
            reference_answer=None,  # no reference in production — use heuristics
            system_answer=row["agent_response"],
            required_facts=[]
        )
        quality_scores.append(score)
    
    # Calculate daily metrics
    avg_faithfulness = sum(s["faithfulness"] for s in quality_scores) / len(quality_scores)
    avg_relevancy = sum(s["factual_accuracy"] for s in quality_scores) / len(quality_scores)
    
    # Write to monitoring table
    metrics_row = {
        "date": yesterday,
        "sample_size": len(quality_scores),
        "avg_faithfulness": avg_faithfulness,
        "avg_relevancy": avg_relevancy,
        "user_thumbs_up_rate": sum(1 for r in production_sample 
                                    if r.get("user_feedback") == "positive") / len(production_sample)
    }
    
    client.insert_rows_json("prod.agent_logs.daily_quality_metrics", [metrics_row])
    
    # ALERT if metrics drop
    FAITHFULNESS_THRESHOLD = 3.8
    if avg_faithfulness < FAITHFULNESS_THRESHOLD:
        send_alert(
            channel="#ai-alerts",
            message=f"⚠️ AI Quality Alert: Faithfulness score dropped to "
                    f"{avg_faithfulness:.2f} (threshold: {FAITHFULNESS_THRESHOLD}). "
                    f"Sample size: {len(quality_scores)}. Check Cloud Logging for details."
        )
    
    return metrics_row

# BigQuery view to trend quality metrics over time
MONITORING_VIEW = """
SELECT
    date,
    avg_faithfulness,
    avg_relevancy,
    user_thumbs_up_rate,
    LAG(avg_faithfulness) OVER (ORDER BY date) AS prev_faithfulness,
    avg_faithfulness - LAG(avg_faithfulness) OVER (ORDER BY date) AS faithfulness_delta
FROM `prod.agent_logs.daily_quality_metrics`
ORDER BY date DESC
"""
```

---

## 7. Evaluation Scorecard — Client Deliverable Template

```markdown
# AI System Evaluation Report
**Project:** [Client] Enterprise AI Assistant
**Evaluation Date:** [Date]
**Evaluator:** [FDE Name]
**System Version:** v1.2.0

## Executive Summary
The AI assistant achieved an **87% overall pass rate** on the 150-item
golden dataset, exceeding the 85% target threshold. The system is ready
for production deployment with the caveats noted below.

## Results by Category

| Category | Target | Actual | Status |
|----------|--------|--------|--------|
| Factual Retrieval | ≥ 90% | 92% | ✅ Pass |
| Multi-Step Reasoning | ≥ 80% | 83% | ✅ Pass |
| Out-of-Scope Refusal | 100% | 100% | ✅ Pass |
| Calculation/Date Math | ≥ 85% | 78% | ❌ Fail |
| **Overall** | **≥ 85%** | **87%** | **✅ Pass** |

## Key Findings
**Strengths:**
- Excellent source citation (97% of answers include source references)
- Zero hallucinations detected on factual retrieval queries
- Correct refusal rate for out-of-scope queries (privacy, legal)

**Weaknesses / Areas for Improvement:**
- Date arithmetic accuracy: 78% (below 85% target)
  *Root cause: Model miscounts months. Fix: Add date calculation tool.*
- Response verbosity: 15% of responses unnecessarily long
  *Fix: Add conciseness instruction to agent prompt.*

## Recommended Actions Before Go-Live
1. Add a `calculate_date_difference(start_date, end_date)` tool (1 day)
2. Update agent instruction: "Keep responses under 150 words unless..." (2 hours)
3. Re-run evaluation after changes to confirm improvement

## Production Monitoring Plan
- Daily 1% production sample evaluated via LLM-as-judge
- Alert threshold: faithfulness < 3.8 / 5.0
- Human review of flagged samples: bi-weekly
- Full golden dataset re-evaluation: monthly

## Sign-Off
FDE Lead: _________________ Date: _______
Client Technical Lead: _________________ Date: _______
```
