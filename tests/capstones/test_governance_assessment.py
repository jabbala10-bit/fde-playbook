"""Contract tests for Capstone 2 (Governance Assessment Tool). Fully local —
rule-based assessors, no network calls."""

from __future__ import annotations

from pathlib import Path

from capstones.governance_assessment.assess import assess_system, load_payload, to_markdown

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "capstones" / "governance_assessment" / "sample_systems"


def test_legal_rag_system_classifies_and_has_obligations():
    payload = load_payload(SAMPLES_DIR / "legal-rag-system.json")
    result = assess_system(payload)
    assert result["eu_ai_act"]["risk_category"]
    assert result["gdpr"]["primary_risk"]
    assert result["eu_ai_act"]["obligations"]
    assert result["gdpr"]["obligations"]


def test_clinical_doc_ai_classifies_as_high_risk():
    """The clinical-doc-ai profile sets is_safety_component + integrated_into_regulated_product
    and special_category_data (health data) — it should land at the top of both
    risk ladders, matching case-studies/clinical-doc-ai.md's "patient safety event" framing."""
    payload = load_payload(SAMPLES_DIR / "clinical-doc-ai.json")
    result = assess_system(payload)
    assert result["eu_ai_act"]["risk_category"] == "high_risk"
    assert result["gdpr"]["primary_risk"] == "special_category_data"


def test_combined_remediation_checklist_is_deduplicated_union():
    payload = load_payload(SAMPLES_DIR / "clinical-doc-ai.json")
    result = assess_system(payload)
    checklist = result["combined_remediation_checklist"]
    assert len(checklist) == len(set(checklist))


def test_to_markdown_renders_both_frameworks():
    payload = load_payload(SAMPLES_DIR / "legal-rag-system.json")
    result = assess_system(payload)
    md = to_markdown(result)
    assert "EU AI Act" in md
    assert "GDPR" in md
    assert result["system_name"] in md
