"""
EU AI Act detection, verification, and assessment helper.

This module is a practical preparation/demo tool for AI governance workflows. It
does not provide legal advice and does not replace a formal conformity
assessment, legal review, or notified-body process where required.

What it does:
    1. Detect likely EU AI Act risk triggers from an AI system description.
    2. Verify whether expected evidence artifacts are present.
    3. Assess risk category, obligations, readiness, and remediation gaps.
    4. Produce an audit-friendly JSON/Markdown report.

Official sources used for the rule model:
    - European Commission AI Act overview:
      https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai
    - Regulation (EU) 2024/1689:
      https://eur-lex.europa.eu/eli/reg/2024/1689/oj

Examples:
    python ai/eu-ai-act.py --mode guide
    python ai/eu-ai-act.py --mode demo
    python ai/eu-ai-act.py --mode assess --input system_inventory.json --format markdown
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from textwrap import dedent
from typing import Any, Iterable, Optional


TODAY = date.today().isoformat()


class RiskCategory(str, Enum):
    PROHIBITED = "prohibited"
    HIGH_RISK = "high_risk"
    TRANSPARENCY = "transparency"
    GPAI = "general_purpose_ai"
    MINIMAL = "minimal_or_no_risk"
    NEEDS_REVIEW = "needs_review"


class ActorRole(str, Enum):
    PROVIDER = "provider"
    DEPLOYER = "deployer"
    IMPORTER = "importer"
    DISTRIBUTOR = "distributor"
    PRODUCT_MANUFACTURER = "product_manufacturer"
    UNKNOWN = "unknown"


class EvidenceStatus(str, Enum):
    PRESENT = "present"
    MISSING = "missing"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class AISystemProfile:
    """Structured input for EU AI Act screening."""

    name: str
    description: str
    intended_purpose: str
    actor_role: ActorRole = ActorRole.UNKNOWN
    users: str = ""
    affected_persons: str = ""
    geography: str = "EU"
    domain: str = ""
    model_type: str = ""
    autonomy_level: str = ""
    data_categories: tuple[str, ...] = field(default_factory=tuple)
    outputs: tuple[str, ...] = field(default_factory=tuple)
    decisions_supported: tuple[str, ...] = field(default_factory=tuple)
    deployment_context: str = ""
    is_gpai_model_provider: bool = False
    is_generative_ai: bool = False
    is_biometric_system: bool = False
    is_safety_component: bool = False
    integrated_into_regulated_product: bool = False
    evidence: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "AISystemProfile":
        payload = dict(payload)
        payload["actor_role"] = ActorRole(payload.get("actor_role", ActorRole.UNKNOWN))
        for key in ("data_categories", "outputs", "decisions_supported"):
            value = payload.get(key, ())
            if isinstance(value, str):
                payload[key] = tuple(item.strip() for item in value.split(",") if item.strip())
            else:
                payload[key] = tuple(value or ())
        return cls(**payload)

    def corpus(self) -> str:
        return " ".join(
            [
                self.name,
                self.description,
                self.intended_purpose,
                self.users,
                self.affected_persons,
                self.geography,
                self.domain,
                self.model_type,
                self.autonomy_level,
                self.deployment_context,
                " ".join(self.data_categories),
                " ".join(self.outputs),
                " ".join(self.decisions_supported),
            ]
        ).lower()


@dataclass(frozen=True)
class DetectionRule:
    rule_id: str
    category: RiskCategory
    label: str
    keywords: tuple[str, ...]
    rationale: str
    severity: int

    def match(self, profile: AISystemProfile) -> Optional["DetectionHit"]:
        corpus = profile.corpus()
        matched = [keyword for keyword in self.keywords if keyword_matches(corpus, keyword)]
        if not matched:
            return None

        confidence = min(0.95, 0.45 + 0.12 * len(matched))
        return DetectionHit(
            rule_id=self.rule_id,
            category=self.category,
            label=self.label,
            matched_terms=tuple(matched),
            confidence=round(confidence, 2),
            rationale=self.rationale,
            severity=self.severity,
        )


@dataclass(frozen=True)
class DetectionHit:
    rule_id: str
    category: RiskCategory
    label: str
    matched_terms: tuple[str, ...]
    confidence: float
    rationale: str
    severity: int


@dataclass(frozen=True)
class EvidenceCheck:
    artifact: str
    status: EvidenceStatus
    detail: str
    required_for: tuple[RiskCategory, ...]


@dataclass(frozen=True)
class AssessmentReport:
    profile_name: str
    assessed_on: str
    primary_category: RiskCategory
    actor_role: ActorRole
    confidence: float
    detections: list[DetectionHit]
    evidence_checks: list[EvidenceCheck]
    obligations: list[str]
    gaps: list[str]
    next_actions: list[str]
    timeline_notes: list[str]
    disclaimer: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    def to_markdown(self) -> str:
        lines = [
            f"# EU AI Act Assessment: {self.profile_name}",
            "",
            f"- Assessed on: {self.assessed_on}",
            f"- Primary category: `{self.primary_category.value}`",
            f"- Actor role: `{self.actor_role.value}`",
            f"- Confidence: `{self.confidence:.2f}`",
            "",
            "## Detection Hits",
        ]
        if self.detections:
            for hit in self.detections:
                terms = ", ".join(hit.matched_terms)
                lines.append(
                    f"- `{hit.category.value}` / {hit.label}: confidence {hit.confidence:.2f}; "
                    f"matched: {terms}"
                )
        else:
            lines.append("- No explicit EU AI Act trigger detected.")

        lines.extend(["", "## Evidence Verification"])
        for check in self.evidence_checks:
            lines.append(f"- `{check.status.value}` {check.artifact}: {check.detail}")

        lines.extend(["", "## Obligations"])
        lines.extend(f"- {item}" for item in self.obligations)

        lines.extend(["", "## Gaps"])
        lines.extend(f"- {item}" for item in self.gaps or ["No material evidence gaps found."])

        lines.extend(["", "## Next Actions"])
        lines.extend(f"- {item}" for item in self.next_actions)

        lines.extend(["", "## Timeline Notes"])
        lines.extend(f"- {item}" for item in self.timeline_notes)

        lines.extend(["", "## Disclaimer", self.disclaimer])
        return "\n".join(lines)


PROHIBITED_RULES = (
    DetectionRule(
        "P1",
        RiskCategory.PROHIBITED,
        "harmful manipulation or deception",
        ("subliminal", "manipulation", "manipulative", "deceptive", "dark pattern", "materially distort"),
        "The Act bans certain harmful manipulation/deception practices.",
        100,
    ),
    DetectionRule(
        "P2",
        RiskCategory.PROHIBITED,
        "exploitation of vulnerabilities",
        ("children", "minor", "disability", "vulnerable", "elderly", "addiction"),
        "Systems exploiting age, disability, or social/economic vulnerability may be prohibited.",
        95,
    ),
    DetectionRule(
        "P3",
        RiskCategory.PROHIBITED,
        "social scoring",
        ("social score", "social scoring", "trust score", "citizen score", "public behaviour score"),
        "Public/private social scoring of natural persons can fall under prohibited practices.",
        100,
    ),
    DetectionRule(
        "P4",
        RiskCategory.PROHIBITED,
        "individual criminal risk prediction",
        ("criminal risk", "predict crime", "recidivism prediction", "offence risk"),
        "Certain individual criminal offence risk assessment or prediction is prohibited.",
        95,
    ),
    DetectionRule(
        "P5",
        RiskCategory.PROHIBITED,
        "untargeted facial recognition scraping",
        ("scrape cctv", "scrape internet faces", "facial recognition database", "face database"),
        "Untargeted scraping of internet/CCTV material to build facial recognition databases is prohibited.",
        100,
    ),
    DetectionRule(
        "P6",
        RiskCategory.PROHIBITED,
        "emotion recognition in workplace or education",
        ("emotion recognition", "sentiment of employees", "student emotion", "worker emotion"),
        "Emotion recognition in workplaces and education institutions is generally prohibited.",
        90,
    ),
    DetectionRule(
        "P7",
        RiskCategory.PROHIBITED,
        "biometric categorisation of protected traits",
        ("biometric categorisation", "infer race", "infer religion", "infer sexual orientation"),
        "Biometric categorisation to deduce protected characteristics is prohibited.",
        100,
    ),
    DetectionRule(
        "P8",
        RiskCategory.PROHIBITED,
        "real-time remote biometric identification in public spaces",
        ("real-time facial recognition", "remote biometric identification", "public space surveillance"),
        "Real-time remote biometric identification in publicly accessible spaces is heavily restricted.",
        100,
    ),
)


HIGH_RISK_RULES = (
    DetectionRule(
        "H1",
        RiskCategory.HIGH_RISK,
        "critical infrastructure safety component",
        ("critical infrastructure", "transport", "energy grid", "water supply", "traffic control"),
        "AI safety components in critical infrastructure can be high-risk.",
        80,
    ),
    DetectionRule(
        "H2",
        RiskCategory.HIGH_RISK,
        "education or vocational training",
        ("exam scoring", "student scoring", "student assessment", "admissions", "education institution", "vocational training"),
        "Systems determining access, progress, or assessment in education can be high-risk.",
        80,
    ),
    DetectionRule(
        "H3",
        RiskCategory.HIGH_RISK,
        "employment or worker management",
        ("recruitment", "cv sorting", "resume screening", "hiring", "promotion", "termination", "worker management"),
        "Employment, recruitment, and worker-management systems can be high-risk.",
        85,
    ),
    DetectionRule(
        "H4",
        RiskCategory.HIGH_RISK,
        "essential public or private services",
        ("credit scoring", "loan", "insurance eligibility", "public benefit", "welfare", "essential service"),
        "Systems deciding access to essential services can be high-risk.",
        85,
    ),
    DetectionRule(
        "H5",
        RiskCategory.HIGH_RISK,
        "biometrics",
        ("biometric", "face recognition", "speaker identification", "fingerprint", "emotion recognition"),
        "Certain biometric identification, categorisation, and emotion-recognition uses can be high-risk.",
        80,
    ),
    DetectionRule(
        "H6",
        RiskCategory.HIGH_RISK,
        "law enforcement",
        ("law enforcement", "police", "evidence reliability", "crime analytics", "investigation"),
        "Law-enforcement AI use cases affecting fundamental rights can be high-risk.",
        85,
    ),
    DetectionRule(
        "H7",
        RiskCategory.HIGH_RISK,
        "migration, asylum, or border control",
        ("visa", "asylum", "migration", "border control", "deportation"),
        "Migration, asylum, and border-control management systems can be high-risk.",
        85,
    ),
    DetectionRule(
        "H8",
        RiskCategory.HIGH_RISK,
        "justice or democratic processes",
        ("court", "judicial", "legal ruling", "election", "voter", "democratic process"),
        "Systems used in administration of justice or democratic processes can be high-risk.",
        85,
    ),
    DetectionRule(
        "H9",
        RiskCategory.HIGH_RISK,
        "regulated product safety component",
        ("medical device", "toy", "lift", "machinery", "robot-assisted surgery", "safety component"),
        "AI safety components in regulated products can be high-risk.",
        90,
    ),
)


TRANSPARENCY_RULES = (
    DetectionRule(
        "T1",
        RiskCategory.TRANSPARENCY,
        "chatbot or human interaction disclosure",
        ("chatbot", "virtual assistant", "conversational agent", "customer support bot"),
        "Users may need to be informed that they are interacting with an AI system.",
        50,
    ),
    DetectionRule(
        "T2",
        RiskCategory.TRANSPARENCY,
        "generative AI content labelling",
        ("generate image", "generate audio", "deepfake", "synthetic media", "ai-generated content"),
        "Generated or manipulated content may require marking or labelling.",
        60,
    ),
    DetectionRule(
        "T3",
        RiskCategory.TRANSPARENCY,
        "public-interest generated text",
        ("news article", "public interest", "political content", "public information"),
        "Generated text informing the public on public-interest matters may require clear disclosure.",
        60,
    ),
)


GPAI_RULES = (
    DetectionRule(
        "G1",
        RiskCategory.GPAI,
        "general-purpose AI model provider",
        ("foundation model", "general-purpose", "gpai", "large language model", "llm provider"),
        "Providers of GPAI models have AI Act obligations around transparency, copyright, and risk.",
        70,
    ),
    DetectionRule(
        "G2",
        RiskCategory.GPAI,
        "systemic-risk model indicators",
        ("frontier model", "systemic risk", "very capable model", "multi-purpose model"),
        "Very capable GPAI models may trigger additional safety and security obligations.",
        75,
    ),
)


ALL_RULES = PROHIBITED_RULES + HIGH_RISK_RULES + TRANSPARENCY_RULES + GPAI_RULES


EVIDENCE_REQUIREMENTS: dict[RiskCategory, tuple[str, ...]] = {
    RiskCategory.PROHIBITED: (
        "legal_basis_analysis",
        "prohibited_practice_review",
        "fundamental_rights_screening",
        "go_no_go_decision",
    ),
    RiskCategory.HIGH_RISK: (
        "intended_purpose_statement",
        "risk_management_file",
        "data_governance_record",
        "technical_documentation",
        "logging_and_traceability_design",
        "instructions_for_use",
        "human_oversight_plan",
        "accuracy_robustness_cybersecurity_tests",
        "conformity_assessment_plan",
        "post_market_monitoring_plan",
        "incident_reporting_process",
        "fundamental_rights_impact_assessment",
    ),
    RiskCategory.TRANSPARENCY: (
        "ai_interaction_disclosure",
        "generated_content_labelling",
        "user_notice_copy",
        "deepfake_or_synthetic_media_controls",
    ),
    RiskCategory.GPAI: (
        "model_card",
        "technical_documentation",
        "copyright_policy",
        "training_data_summary",
        "downstream_provider_information",
        "systemic_risk_evaluation",
        "safety_and_security_controls",
    ),
    RiskCategory.MINIMAL: (
        "ai_inventory_entry",
        "basic_risk_screening",
        "user_feedback_channel",
    ),
    RiskCategory.NEEDS_REVIEW: (
        "ai_inventory_entry",
        "intended_purpose_statement",
        "human_review_notes",
    ),
}


OBLIGATIONS: dict[RiskCategory, tuple[str, ...]] = {
    RiskCategory.PROHIBITED: (
        "Stop or redesign the use case unless a narrow legal exception applies.",
        "Escalate to legal/compliance before development, procurement, or deployment.",
        "Document why the use case is outside prohibited-practice scope if proceeding.",
    ),
    RiskCategory.HIGH_RISK: (
        "Maintain risk management and mitigation controls across the lifecycle.",
        "Use appropriate data governance and quality controls.",
        "Enable logging and traceability.",
        "Maintain technical documentation and instructions for use.",
        "Implement human oversight, robustness, accuracy, and cybersecurity controls.",
        "Plan conformity assessment and post-market monitoring.",
        "Report serious incidents and malfunctioning through the required process.",
    ),
    RiskCategory.TRANSPARENCY: (
        "Inform users when they interact with AI where required.",
        "Mark or label AI-generated/deepfake content where required.",
        "Make disclosures clear, visible, and appropriate for the affected users.",
    ),
    RiskCategory.GPAI: (
        "Prepare model-level technical documentation.",
        "Provide downstream information for AI-system providers.",
        "Maintain copyright policy and training-content summary.",
        "Assess and mitigate systemic risks where the model has systemic-risk characteristics.",
    ),
    RiskCategory.MINIMAL: (
        "Maintain inventory entry and basic governance records.",
        "Use voluntary good practices for transparency, monitoring, and user feedback.",
    ),
    RiskCategory.NEEDS_REVIEW: (
        "Collect missing intended-purpose, user, geography, and impact information.",
        "Escalate ambiguous cases to legal/compliance or an AI governance board.",
    ),
}


TIMELINE_NOTES = (
    "The EU AI Act entered into force on 1 August 2024.",
    "Prohibited-practice and AI-literacy obligations entered into application from 2 February 2025.",
    "Governance rules and GPAI obligations became applicable on 2 August 2025.",
    "Most AI Act provisions apply from 2 August 2026, including transparency obligations.",
    "Current Commission simplification notes indicate certain standalone high-risk area rules apply from 2 December 2027.",
    "High-risk systems integrated into regulated products have an extended transition period until 2 August 2028.",
)


DISCLAIMER = (
    "This automated assessment is a triage and preparation aid only. It is not legal advice, "
    "does not determine legal compliance, and should be reviewed by qualified legal, risk, "
    "and domain experts before deployment or market placement."
)


class EUAIActAssessor:
    """Rules-based EU AI Act detection, verification, and assessment engine."""

    def assess(self, profile: AISystemProfile) -> AssessmentReport:
        detections = self.detect(profile)
        primary_category = self.classify(profile, detections)
        evidence_checks = self.verify_evidence(profile, primary_category, detections)
        gaps = self.find_gaps(evidence_checks, primary_category)
        obligations = list(OBLIGATIONS[primary_category])
        next_actions = self.recommend_actions(primary_category, gaps, detections, profile)
        confidence = self.estimate_confidence(primary_category, detections, profile)

        return AssessmentReport(
            profile_name=profile.name,
            assessed_on=TODAY,
            primary_category=primary_category,
            actor_role=profile.actor_role,
            confidence=confidence,
            detections=detections,
            evidence_checks=evidence_checks,
            obligations=obligations,
            gaps=gaps,
            next_actions=next_actions,
            timeline_notes=list(TIMELINE_NOTES),
            disclaimer=DISCLAIMER,
        )

    def detect(self, profile: AISystemProfile) -> list[DetectionHit]:
        hits = [hit for rule in ALL_RULES if (hit := rule.match(profile)) is not None]

        if profile.is_gpai_model_provider:
            hits.append(
                DetectionHit(
                    "G0",
                    RiskCategory.GPAI,
                    "explicit GPAI model provider flag",
                    ("is_gpai_model_provider",),
                    "The profile explicitly indicates GPAI model-provider status.",
                    0.95,
                    80,
                )
            )
        if profile.is_generative_ai:
            hits.append(
                DetectionHit(
                    "T0",
                    RiskCategory.TRANSPARENCY,
                    "explicit generative AI flag",
                    ("is_generative_ai",),
                    "The profile explicitly indicates generative AI functionality.",
                    0.8,
                    65,
                )
            )
        if profile.is_biometric_system:
            hits.append(
                DetectionHit(
                    "H0",
                    RiskCategory.HIGH_RISK,
                    "explicit biometric system flag",
                    ("is_biometric_system",),
                    "The profile explicitly indicates biometric AI functionality.",
                    0.85,
                    85,
                )
            )
        if profile.is_safety_component or profile.integrated_into_regulated_product:
            hits.append(
                DetectionHit(
                    "H10",
                    RiskCategory.HIGH_RISK,
                    "explicit safety/product integration flag",
                    ("safety_component_or_regulated_product",),
                    "AI safety components or regulated-product integration can trigger high-risk obligations.",
                    0.85,
                    90,
                )
            )

        return sorted(hits, key=lambda hit: (hit.severity, hit.confidence), reverse=True)

    def classify(self, profile: AISystemProfile, hits: list[DetectionHit]) -> RiskCategory:
        categories = {hit.category for hit in hits}
        if RiskCategory.PROHIBITED in categories:
            return RiskCategory.PROHIBITED
        if RiskCategory.HIGH_RISK in categories:
            return RiskCategory.HIGH_RISK
        if RiskCategory.GPAI in categories:
            return RiskCategory.GPAI
        if RiskCategory.TRANSPARENCY in categories:
            return RiskCategory.TRANSPARENCY

        if missing_core_profile_fields(profile):
            return RiskCategory.NEEDS_REVIEW
        return RiskCategory.MINIMAL

    def verify_evidence(
        self,
        profile: AISystemProfile,
        primary_category: RiskCategory,
        detections: list[DetectionHit],
    ) -> list[EvidenceCheck]:
        required_categories = {primary_category}
        required_categories.update(hit.category for hit in detections if hit.category != RiskCategory.MINIMAL)

        artifacts: dict[str, set[RiskCategory]] = {}
        for category in required_categories:
            for artifact in EVIDENCE_REQUIREMENTS[category]:
                artifacts.setdefault(artifact, set()).add(category)

        checks: list[EvidenceCheck] = []
        for artifact, categories in sorted(artifacts.items()):
            raw_status = profile.evidence.get(artifact, "").strip().lower()
            if raw_status in {"present", "yes", "complete", "done"}:
                status = EvidenceStatus.PRESENT
                detail = "Evidence marked present."
            elif raw_status in {"partial", "draft", "in_progress", "in progress"}:
                status = EvidenceStatus.PARTIAL
                detail = "Evidence exists but appears incomplete."
            elif raw_status in {"n/a", "na", "not_applicable", "not applicable"}:
                status = EvidenceStatus.NOT_APPLICABLE
                detail = "Evidence marked not applicable; verify rationale."
            else:
                status = EvidenceStatus.MISSING
                detail = "Evidence not supplied in profile."

            checks.append(
                EvidenceCheck(
                    artifact=artifact,
                    status=status,
                    detail=detail,
                    required_for=tuple(sorted(categories, key=lambda item: item.value)),
                )
            )
        return checks

    def find_gaps(
        self,
        evidence_checks: list[EvidenceCheck],
        primary_category: RiskCategory,
    ) -> list[str]:
        gaps: list[str] = []
        for check in evidence_checks:
            if check.status == EvidenceStatus.MISSING:
                gaps.append(f"Missing {check.artifact} for {', '.join(c.value for c in check.required_for)}.")
            elif check.status == EvidenceStatus.PARTIAL:
                gaps.append(f"Incomplete {check.artifact}; finish and approve before relying on it.")

        if primary_category == RiskCategory.PROHIBITED:
            gaps.insert(0, "Potential prohibited-practice trigger requires immediate legal review.")
        return gaps

    def recommend_actions(
        self,
        primary_category: RiskCategory,
        gaps: list[str],
        detections: list[DetectionHit],
        profile: AISystemProfile,
    ) -> list[str]:
        actions: list[str] = []
        if primary_category == RiskCategory.PROHIBITED:
            actions.extend(
                [
                    "Pause deployment or procurement until prohibited-practice analysis is complete.",
                    "Redesign the use case to remove prohibited functionality, or document a valid legal exception.",
                ]
            )
        elif primary_category == RiskCategory.HIGH_RISK:
            actions.extend(
                [
                    "Create or update the high-risk AI compliance file.",
                    "Map provider/deployer responsibilities and ownership.",
                    "Prepare conformity-assessment, monitoring, and incident-reporting plans.",
                ]
            )
            if profile.actor_role == ActorRole.DEPLOYER:
                actions.append("Assess whether a Fundamental Rights Impact Assessment is required before use.")
        elif primary_category == RiskCategory.GPAI:
            actions.extend(
                [
                    "Confirm whether you are the GPAI model provider or only an AI-system provider/deployer using a model.",
                    "Prepare model documentation, copyright policy, and training-content summary where applicable.",
                ]
            )
        elif primary_category == RiskCategory.TRANSPARENCY:
            actions.extend(
                [
                    "Design user-facing AI disclosure and content-labelling controls.",
                    "Test whether disclosures are visible, timely, and understandable for affected users.",
                ]
            )
        elif primary_category == RiskCategory.NEEDS_REVIEW:
            actions.append("Complete the inventory profile before classification.")
        else:
            actions.append("Maintain inventory entry and monitor for scope or purpose changes.")

        if gaps:
            actions.append("Resolve missing or partial evidence artifacts listed in the gaps section.")
        if any(hit.confidence < 0.6 for hit in detections):
            actions.append("Manually review low-confidence keyword matches to remove false positives.")
        return actions

    def estimate_confidence(
        self,
        primary_category: RiskCategory,
        detections: list[DetectionHit],
        profile: AISystemProfile,
    ) -> float:
        if primary_category == RiskCategory.NEEDS_REVIEW:
            return 0.35
        if not detections:
            return 0.6 if not missing_core_profile_fields(profile) else 0.4
        top = max(hit.confidence for hit in detections)
        evidence_bonus = 0.05 if profile.evidence else 0.0
        return round(min(0.98, top + evidence_bonus), 2)


def missing_core_profile_fields(profile: AISystemProfile) -> bool:
    required = [profile.description, profile.intended_purpose, profile.users, profile.affected_persons]
    return any(not value.strip() for value in required)


def keyword_matches(corpus: str, keyword: str) -> bool:
    """Match keywords as words/phrases, not accidental substrings."""

    normalized = " ".join(corpus.lower().split())
    escaped = re.escape(keyword.lower().strip())
    pattern = rf"(?<![a-z0-9_]){escaped}(?![a-z0-9_])"
    return re.search(pattern, normalized) is not None


def load_profile(path: Path) -> AISystemProfile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return AISystemProfile.from_mapping(payload)


def demo_profile() -> AISystemProfile:
    return AISystemProfile(
        name="Recruitment CV Screening Assistant",
        description=(
            "Ranks resumes, screens candidates, and recommends interview shortlists "
            "for recruiters using a machine learning model."
        ),
        intended_purpose="Support hiring teams by ranking applicants for open roles.",
        actor_role=ActorRole.DEPLOYER,
        users="Recruiters and hiring managers in EU offices.",
        affected_persons="Job applicants and internal transfer candidates.",
        geography="European Union",
        domain="employment and recruitment",
        model_type="LLM and ranking model",
        autonomy_level="Human-in-the-loop recommendation",
        data_categories=("CV data", "employment history", "education", "skills"),
        outputs=("candidate score", "ranked shortlist", "interview recommendation"),
        decisions_supported=("hiring", "candidate screening", "interview selection"),
        evidence={
            "intended_purpose_statement": "present",
            "human_oversight_plan": "partial",
            "technical_documentation": "partial",
            "data_governance_record": "missing",
        },
    )


def sample_profile_json() -> str:
    return json.dumps(asdict(demo_profile()), indent=2)


def guide() -> str:
    return dedent(
        """
        EU AI Act detection, verification, and assessment workflow:

        1. Create an AI system profile
           Capture intended purpose, actor role, users, affected persons, geography,
           domain, data categories, outputs, decisions supported, and evidence status.

        2. Detect risk triggers
           The rule engine screens for prohibited practices, high-risk use cases,
           transparency duties, and GPAI model-provider obligations.

        3. Classify risk
           Priority order is: prohibited -> high-risk -> GPAI -> transparency ->
           needs review -> minimal/no risk.

        4. Verify evidence
           The checker validates whether expected governance artifacts are present,
           missing, partial, or marked not applicable.

        5. Assess and remediate
           The report lists likely obligations, gaps, next actions, and timeline notes.

        Commands:
           python ai/eu-ai-act.py --mode guide
           python ai/eu-ai-act.py --mode sample-profile
           python ai/eu-ai-act.py --mode demo --format markdown
           python ai/eu-ai-act.py --mode assess --input profile.json --format json
        """
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="EU AI Act detection and assessment helper")
    parser.add_argument(
        "--mode",
        choices=("guide", "sample-profile", "demo", "assess"),
        default="guide",
    )
    parser.add_argument("--input", help="Path to AI system profile JSON.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()

    if args.mode == "guide":
        print(guide())
        return

    if args.mode == "sample-profile":
        print(sample_profile_json())
        return

    profile = demo_profile() if args.mode == "demo" else load_profile(Path(args.input or ""))
    report = EUAIActAssessor().assess(profile)
    print(report.to_markdown() if args.format == "markdown" else report.to_json())


if __name__ == "__main__":
    main()
