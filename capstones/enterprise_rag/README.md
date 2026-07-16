# Capstone 1 — Enterprise RAG for a Legal Firm

### The runnable companion to notes/18's worked system-design answer

*Part of [The FDE Playbook](../../README.md)'s [capstones](../). Implements the exact scenario from [notes/18_interview_blackbook_case_studies.md](../../notes/18_interview_blackbook_case_studies.md) §2 — a legal firm, 500K-page corpus (represented here by a small synthetic set), per-matter access control, and a citation + faithfulness requirement.*

## Objective

Build and evaluate a RAG pipeline that a lawyer could actually be handed:
retrieval that never leaks one matter's documents into another's answer,
every answer carrying a source citation, and a faithfulness score that
flags ungrounded answers. Everything runs offline by default.

## Setup

```bash
pip install -e .          # from repo root; stdlib-only, no network needed
python -m capstones.enterprise_rag ingest
python -m capstones.enterprise_rag ask "What is the transaction value in the Acme Robotics merger?" --matter matter-101
python -m capstones.enterprise_rag eval
```

## The exercise

[`retrieve.py`](./retrieve.py)'s `rerank()` is a deliberate no-op passthrough
— the seam notes/18 calls a cross-encoder reranker. Implement a real
reranking signal (a cheap lexical-overlap boost is enough to start; a
proper cross-encoder is the stretch version), keeping the contract intact:
same list length in and out, sorted by score, and it must never surface a
chunk from a matter other than the one it was retrieved for (that's already
enforced upstream in `store.py` — don't undo it).

Re-run `eval` before and after; note the change in
`retrieval_recall_at_k` and `faithfulness_rate`.

## Grading rubric

| Dimension | 1 (needs work) | 3 (solid) | 5 (strong) |
|---|---|---|---|
| Access control | A test can make matter A's query return matter B's chunks | Filter enforced in the store, verified by the provided test | Filter enforced *and* a second independent check exists (e.g. in guardrails) |
| Retrieval quality | `retrieval_recall_at_k` unchanged or worse after reranking | Recall improves measurably on the golden set | Recall improves and you can explain *why* in the tradeoffs a system-design interviewer would ask about |
| Citations | Answers ship with no source attribution | Every answer lists its source doc_ids | Citations are inline per-claim, not just a trailing block |
| Faithfulness | No groundedness check | Heuristic check present and reported | You can articulate what would break if you swapped the heuristic for an LLM-as-judge, and why (see [eval-driven-development.md](../../eval-driven-development.md)) |

Run `pytest tests/capstones/test_enterprise_rag.py -v` — it must pass
before and after your changes (it tests the contract, not your specific
reranking implementation).

## Go live (stretch goal)

- Swap `LocalHashEmbedding` for a real embedding API. Not wired here on
  purpose — pick one and wire it, matching the "why this vs. that" tradeoff
  discussion in notes/18.
- `--provider live` already wires `AnthropicGenerator` (needs
  `pip install -e '.[live]'` and `ANTHROPIC_API_KEY`) — try it and compare
  faithfulness against the mock generator.
- `store.py`'s `BigQueryVectorStore` is a stub with `NotImplementedError` —
  implement it against [notes/09_bigquery_data_architecture.md](../../notes/09_bigquery_data_architecture.md)'s
  `VECTOR_SEARCH` pattern for the row-level-security-at-scale version of
  this capstone.
