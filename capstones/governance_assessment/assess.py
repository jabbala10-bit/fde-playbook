"""Combined EU AI Act + GDPR governance assessment from one system profile.

The artifact an FDE actually hands a customer during discovery/scoping —
see governance-playbook.md and discovery-toolkit.md's governance checklist.
Reuses coding/eu-ai-act.py's EUAIActAssessor and coding/gdpr.py's
GDPRAssessor rather than reimplementing the rule engines.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Dict

from .loader import load_coding_module

_eu = load_coding_module("eu-ai-act.py")
_gdpr = load_coding_module("gdpr.py")


def _filtered(payload: Dict[str, Any], dataclass_type: type) -> Dict[str, Any]:
    """Keep only the keys `dataclass_type` actually declares — lets one JSON
    profile feed both assessors even though their field sets only partially
    overlap."""
    valid = {f.name for f in dataclasses.fields(dataclass_type)}
    return {k: v for k, v in payload.items() if k in valid}


def load_payload(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assess_system(payload: Dict[str, Any]) -> Dict[str, Any]:
    # eu-ai-act.py's ActorRole (provider/deployer/...) and gdpr.py's ActorRole
    # (controller/processor/...) are different enums that both happen to be
    # named "actor_role" on their dataclasses, so the shared input schema
    # disambiguates them as eu_actor_role / gdpr_actor_role and we remap here.
    eu_payload = dict(payload)
    if "eu_actor_role" in eu_payload:
        eu_payload["actor_role"] = eu_payload.pop("eu_actor_role")
    gdpr_payload = dict(payload)
    if "gdpr_actor_role" in gdpr_payload:
        gdpr_payload["actor_role"] = gdpr_payload.pop("gdpr_actor_role")

    eu_profile = _eu.AISystemProfile.from_mapping(_filtered(eu_payload, _eu.AISystemProfile))
    gdpr_profile = _gdpr.ProcessingActivityProfile.from_mapping(
        _filtered(gdpr_payload, _gdpr.ProcessingActivityProfile)
    )

    eu_report = _eu.EUAIActAssessor().assess(eu_profile)
    gdpr_report = _gdpr.GDPRAssessor().assess(gdpr_profile)

    return {
        "system_name": payload.get("name", "unnamed system"),
        "eu_ai_act": {
            "risk_category": eu_report.primary_category.value,
            "confidence": eu_report.confidence,
            "obligations": eu_report.obligations,
            "gaps": eu_report.gaps,
        },
        "gdpr": {
            "primary_risk": gdpr_report.primary_risk.value,
            "lawful_basis": gdpr_report.lawful_basis.value,
            "confidence": gdpr_report.confidence,
            "obligations": gdpr_report.obligations,
            "gaps": gdpr_report.gaps,
        },
        "combined_remediation_checklist": sorted(set(eu_report.gaps) | set(gdpr_report.gaps)),
        "_eu_report": eu_report,
        "_gdpr_report": gdpr_report,
    }


def to_markdown(result: Dict[str, Any]) -> str:
    checklist_lines = [f"- [ ] {gap}" for gap in result["combined_remediation_checklist"]] or [
        "- (none identified)"
    ]
    lines = [
        f"# Governance Assessment: {result['system_name']}",
        "",
        "## EU AI Act",
        f"- Risk category: `{result['eu_ai_act']['risk_category']}`",
        f"- Confidence: `{result['eu_ai_act']['confidence']:.2f}`",
        "- Obligations:",
        *[f"  - {o}" for o in result["eu_ai_act"]["obligations"]],
        "",
        "## GDPR",
        f"- Primary risk: `{result['gdpr']['primary_risk']}`",
        f"- Lawful basis: `{result['gdpr']['lawful_basis']}`",
        f"- Confidence: `{result['gdpr']['confidence']:.2f}`",
        "- Obligations:",
        *[f"  - {o}" for o in result["gdpr"]["obligations"]],
        "",
        "## Combined remediation checklist",
        *checklist_lines,
    ]
    return "\n".join(lines)
