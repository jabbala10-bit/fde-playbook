"""
GDPR detection, verification, and assessment helper.

This module is a practical preparation/demo tool for privacy engineering and
governance workflows. It does not provide legal advice and does not replace a
formal privacy review, Data Protection Officer review, or counsel review.

What it does:
    1. Detect likely GDPR triggers from a system/process description.
    2. Classify privacy risk and special compliance triggers.
    3. Verify evidence artifacts such as lawful basis, privacy notice, ROPA,
       DPIA, DPA, SCCs, retention plan, DSR workflow, and security controls.
    4. Produce JSON or Markdown reports with gaps and remediation actions.

Official sources used for the rule model:
    - European Commission data protection legal framework:
      https://commission.europa.eu/law/law-topic/data-protection/legal-framework-eu-data-protection_en
    - Regulation (EU) 2016/679 (GDPR):
      https://eur-lex.europa.eu/eli/reg/2016/679/oj

Examples:
    python ai/gdpr.py --mode guide
    python ai/gdpr.py --mode demo --format markdown
    python ai/gdpr.py --mode assess --input processing_profile.json --format json
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
from typing import Any, Optional


TODAY = date.today().isoformat()


class PrivacyRisk(str, Enum):
    NO_PERSONAL_DATA = "no_personal_data"
    STANDARD_PERSONAL_DATA = "standard_personal_data"
    HIGH_RISK_PROCESSING = "high_risk_processing"
    SPECIAL_CATEGORY_DATA = "special_category_data"
    CHILDREN_DATA = "children_data"
    CRIMINAL_OFFENCE_DATA = "criminal_offence_data"
    AUTOMATED_DECISION_MAKING = "automated_decision_making"
    INTERNATIONAL_TRANSFER = "international_transfer"
    NEEDS_REVIEW = "needs_review"


class ActorRole(str, Enum):
    CONTROLLER = "controller"
    PROCESSOR = "processor"
    JOINT_CONTROLLER = "joint_controller"
    SUBPROCESSOR = "subprocessor"
    UNKNOWN = "unknown"


class LawfulBasis(str, Enum):
    CONSENT = "consent"
    CONTRACT = "contract"
    LEGAL_OBLIGATION = "legal_obligation"
    VITAL_INTERESTS = "vital_interests"
    PUBLIC_TASK = "public_task"
    LEGITIMATE_INTERESTS = "legitimate_interests"
    UNKNOWN = "unknown"


class EvidenceStatus(str, Enum):
    PRESENT = "present"
    MISSING = "missing"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class ProcessingActivityProfile:
    """Structured input for GDPR screening."""

    name: str
    description: str
    purpose: str
    actor_role: ActorRole = ActorRole.UNKNOWN
    lawful_basis: LawfulBasis = LawfulBasis.UNKNOWN
    controller_name: str = ""
    processor_name: str = ""
    data_subjects: tuple[str, ...] = field(default_factory=tuple)
    personal_data_categories: tuple[str, ...] = field(default_factory=tuple)
    special_category_data: tuple[str, ...] = field(default_factory=tuple)
    criminal_offence_data: bool = False
    children_data: bool = False
    automated_decision_making: bool = False
    profiling: bool = False
    large_scale_processing: bool = False
    systematic_monitoring: bool = False
    public_area_monitoring: bool = False
    ai_or_analytics: bool = False
    recipients: tuple[str, ...] = field(default_factory=tuple)
    processors: tuple[str, ...] = field(default_factory=tuple)
    subprocessors: tuple[str, ...] = field(default_factory=tuple)
    source_systems: tuple[str, ...] = field(default_factory=tuple)
    retention_period: str = ""
    geography: str = "EU/EEA"
    transfers_outside_eea: bool = False
    transfer_countries: tuple[str, ...] = field(default_factory=tuple)
    security_measures: tuple[str, ...] = field(default_factory=tuple)
    evidence: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "ProcessingActivityProfile":
        payload = dict(payload)
        payload["actor_role"] = ActorRole(payload.get("actor_role", ActorRole.UNKNOWN))
        payload["lawful_basis"] = LawfulBasis(payload.get("lawful_basis", LawfulBasis.UNKNOWN))
        tuple_fields = (
            "data_subjects",
            "personal_data_categories",
            "special_category_data",
            "recipients",
            "processors",
            "subprocessors",
            "source_systems",
            "transfer_countries",
            "security_measures",
        )
        for key in tuple_fields:
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
                self.purpose,
                self.controller_name,
                self.processor_name,
                self.retention_period,
                self.geography,
                " ".join(self.data_subjects),
                " ".join(self.personal_data_categories),
                " ".join(self.special_category_data),
                " ".join(self.recipients),
                " ".join(self.processors),
                " ".join(self.subprocessors),
                " ".join(self.source_systems),
                " ".join(self.transfer_countries),
                " ".join(self.security_measures),
            ]
        ).lower()


@dataclass(frozen=True)
class DetectionRule:
    rule_id: str
    category: PrivacyRisk
    label: str
    keywords: tuple[str, ...]
    rationale: str
    severity: int

    def match(self, profile: ProcessingActivityProfile) -> Optional["DetectionHit"]:
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
    category: PrivacyRisk
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
    required_for: tuple[PrivacyRisk, ...]


@dataclass(frozen=True)
class GDPRAssessmentReport:
    profile_name: str
    assessed_on: str
    primary_risk: PrivacyRisk
    actor_role: ActorRole
    lawful_basis: LawfulBasis
    confidence: float
    detections: list[DetectionHit]
    evidence_checks: list[EvidenceCheck]
    principles: list[str]
    obligations: list[str]
    gaps: list[str]
    next_actions: list[str]
    disclaimer: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    def to_markdown(self) -> str:
        lines = [
            f"# GDPR Assessment: {self.profile_name}",
            "",
            f"- Assessed on: {self.assessed_on}",
            f"- Primary risk: `{self.primary_risk.value}`",
            f"- Actor role: `{self.actor_role.value}`",
            f"- Lawful basis: `{self.lawful_basis.value}`",
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
            lines.append("- No GDPR personal-data trigger detected.")

        lines.extend(["", "## GDPR Principles"])
        lines.extend(f"- {item}" for item in self.principles)

        lines.extend(["", "## Evidence Verification"])
        for check in self.evidence_checks:
            lines.append(f"- `{check.status.value}` {check.artifact}: {check.detail}")

        lines.extend(["", "## Obligations"])
        lines.extend(f"- {item}" for item in self.obligations)

        lines.extend(["", "## Gaps"])
        lines.extend(f"- {item}" for item in self.gaps or ["No material evidence gaps found."])

        lines.extend(["", "## Next Actions"])
        lines.extend(f"- {item}" for item in self.next_actions)

        lines.extend(["", "## Disclaimer", self.disclaimer])
        return "\n".join(lines)


PERSONAL_DATA_RULES = (
    DetectionRule(
        "PD1",
        PrivacyRisk.STANDARD_PERSONAL_DATA,
        "direct identifiers",
        ("name", "email", "phone", "address", "customer id", "employee id", "user id"),
        "Direct or indirect identifiers can make data personal data under GDPR.",
        40,
    ),
    DetectionRule(
        "PD2",
        PrivacyRisk.STANDARD_PERSONAL_DATA,
        "online identifiers",
        ("ip address", "cookie id", "device id", "advertising id", "session id"),
        "Online identifiers can be personal data when linked or linkable to a person.",
        45,
    ),
    DetectionRule(
        "PD3",
        PrivacyRisk.STANDARD_PERSONAL_DATA,
        "business records about people",
        ("invoice", "order", "support ticket", "crm", "account", "profile"),
        "Business records tied to customers, employees, or users may contain personal data.",
        35,
    ),
)

SPECIAL_CATEGORY_RULES = (
    DetectionRule(
        "SC1",
        PrivacyRisk.SPECIAL_CATEGORY_DATA,
        "special category data",
        ("health", "medical", "biometric", "genetic", "race", "ethnic", "religion", "political", "trade union", "sexual orientation"),
        "Special category data needs an Article 9 condition in addition to Article 6 lawful basis.",
        90,
    ),
)

HIGH_RISK_RULES = (
    DetectionRule(
        "HR1",
        PrivacyRisk.HIGH_RISK_PROCESSING,
        "large-scale monitoring or profiling",
        ("large scale", "systematic monitoring", "behavior tracking", "profiling", "scoring", "surveillance"),
        "Large-scale monitoring, profiling, or scoring can trigger DPIA and stronger controls.",
        80,
    ),
    DetectionRule(
        "HR2",
        PrivacyRisk.AUTOMATED_DECISION_MAKING,
        "automated decisions with significant effects",
        ("automated decision", "auto reject", "eligibility decision", "credit decision", "hiring decision", "loan decision"),
        "Solely automated decisions with legal or similarly significant effects trigger Article 22 review.",
        90,
    ),
    DetectionRule(
        "HR3",
        PrivacyRisk.CHILDREN_DATA,
        "children data",
        ("child", "children", "minor", "student under 16", "underage"),
        "Children's data requires heightened transparency, safeguards, and consent analysis where relevant.",
        85,
    ),
    DetectionRule(
        "HR4",
        PrivacyRisk.CRIMINAL_OFFENCE_DATA,
        "criminal offence data",
        ("criminal offence", "conviction", "criminal record", "background check"),
        "Criminal offence data is subject to additional Article 10 restrictions.",
        85,
    ),
    DetectionRule(
        "HR5",
        PrivacyRisk.INTERNATIONAL_TRANSFER,
        "international data transfer",
        ("outside eea", "third country", "international transfer", "standard contractual clauses", "scc"),
        "Transfers outside the EEA need a valid Chapter V transfer mechanism.",
        80,
    ),
)

ALL_RULES = PERSONAL_DATA_RULES + SPECIAL_CATEGORY_RULES + HIGH_RISK_RULES


GDPR_PRINCIPLES = (
    "Lawfulness, fairness, and transparency.",
    "Purpose limitation.",
    "Data minimisation.",
    "Accuracy.",
    "Storage limitation.",
    "Integrity and confidentiality.",
    "Accountability.",
)


EVIDENCE_REQUIREMENTS: dict[PrivacyRisk, tuple[str, ...]] = {
    PrivacyRisk.NO_PERSONAL_DATA: ("scope_assessment",),
    PrivacyRisk.STANDARD_PERSONAL_DATA: (
        "processing_inventory_ropa",
        "lawful_basis_assessment",
        "privacy_notice",
        "data_minimisation_review",
        "retention_schedule",
        "data_subject_request_workflow",
        "security_controls",
        "breach_response_plan",
    ),
    PrivacyRisk.SPECIAL_CATEGORY_DATA: (
        "processing_inventory_ropa",
        "lawful_basis_assessment",
        "article_9_condition",
        "dpia",
        "privacy_notice",
        "data_minimisation_review",
        "security_controls",
        "access_control_review",
        "retention_schedule",
    ),
    PrivacyRisk.CHILDREN_DATA: (
        "children_privacy_assessment",
        "age_appropriate_notice",
        "parental_consent_or_guardian_basis",
        "data_minimisation_review",
        "security_controls",
        "retention_schedule",
    ),
    PrivacyRisk.CRIMINAL_OFFENCE_DATA: (
        "article_10_condition",
        "legal_authorisation_review",
        "access_control_review",
        "dpia",
        "security_controls",
    ),
    PrivacyRisk.AUTOMATED_DECISION_MAKING: (
        "article_22_assessment",
        "meaningful_information_about_logic",
        "human_review_or_contestation_workflow",
        "dpia",
        "fairness_and_accuracy_testing",
    ),
    PrivacyRisk.INTERNATIONAL_TRANSFER: (
        "transfer_mapping",
        "transfer_impact_assessment",
        "adequacy_or_sccs",
        "supplementary_measures",
        "processor_subprocessor_register",
    ),
    PrivacyRisk.HIGH_RISK_PROCESSING: (
        "dpia",
        "risk_assessment",
        "processing_inventory_ropa",
        "data_protection_by_design_review",
        "security_controls",
        "monitoring_and_audit_plan",
    ),
    PrivacyRisk.NEEDS_REVIEW: (
        "processing_inventory_ropa",
        "purpose_statement",
        "data_mapping",
        "human_privacy_review_notes",
    ),
}


OBLIGATIONS: dict[PrivacyRisk, tuple[str, ...]] = {
    PrivacyRisk.NO_PERSONAL_DATA: (
        "Document why the activity is outside GDPR scope.",
        "Reassess if identifiers, logs, or user-linked records are later added.",
    ),
    PrivacyRisk.STANDARD_PERSONAL_DATA: (
        "Identify controller/processor roles and maintain processing records where required.",
        "Document a valid lawful basis for each purpose.",
        "Provide transparent privacy information to data subjects.",
        "Support data subject rights such as access, rectification, erasure, restriction, portability, and objection where applicable.",
        "Apply privacy by design/default, security controls, retention limits, and breach response procedures.",
    ),
    PrivacyRisk.SPECIAL_CATEGORY_DATA: (
        "Document Article 6 lawful basis and an Article 9 special-category condition.",
        "Run or review a DPIA where high risk is likely.",
        "Apply strong access controls, minimisation, retention, and security safeguards.",
    ),
    PrivacyRisk.CHILDREN_DATA: (
        "Use child-appropriate transparency and safeguards.",
        "Assess age, consent, parental responsibility, and local Member State requirements.",
        "Minimise collection and restrict profiling or marketing uses.",
    ),
    PrivacyRisk.CRIMINAL_OFFENCE_DATA: (
        "Confirm Article 10 authority or legal authorisation.",
        "Apply strict access controls and auditability.",
    ),
    PrivacyRisk.AUTOMATED_DECISION_MAKING: (
        "Assess whether Article 22 applies to solely automated decisions with legal or similarly significant effects.",
        "Provide meaningful information, human intervention, contestation, and safeguards where required.",
    ),
    PrivacyRisk.INTERNATIONAL_TRANSFER: (
        "Map transfers outside the EEA.",
        "Confirm adequacy decision or use SCCs/other transfer mechanism.",
        "Complete transfer impact assessment and supplementary measures where needed.",
    ),
    PrivacyRisk.HIGH_RISK_PROCESSING: (
        "Complete DPIA before processing if high risk is likely.",
        "Implement privacy by design/default, security, monitoring, and risk controls.",
        "Consult the supervisory authority if residual high risk remains after mitigation.",
    ),
    PrivacyRisk.NEEDS_REVIEW: (
        "Complete the processing profile before classifying GDPR obligations.",
        "Escalate ambiguous scope or role questions to privacy counsel or DPO.",
    ),
}


DISCLAIMER = (
    "This automated assessment is a triage and preparation aid only. It is not legal advice, "
    "does not determine GDPR compliance, and should be reviewed by qualified privacy, legal, "
    "security, and data protection professionals before launch or material processing changes."
)


class GDPRAssessor:
    """Rules-based GDPR detection, verification, and assessment engine."""

    def assess(self, profile: ProcessingActivityProfile) -> GDPRAssessmentReport:
        detections = self.detect(profile)
        primary_risk = self.classify(profile, detections)
        evidence_checks = self.verify_evidence(profile, primary_risk, detections)
        gaps = self.find_gaps(evidence_checks, profile, primary_risk)
        obligations = self.collect_obligations(primary_risk, detections)
        next_actions = self.recommend_actions(primary_risk, gaps, detections, profile)
        confidence = self.estimate_confidence(primary_risk, detections, profile)

        return GDPRAssessmentReport(
            profile_name=profile.name,
            assessed_on=TODAY,
            primary_risk=primary_risk,
            actor_role=profile.actor_role,
            lawful_basis=profile.lawful_basis,
            confidence=confidence,
            detections=detections,
            evidence_checks=evidence_checks,
            principles=list(GDPR_PRINCIPLES),
            obligations=obligations,
            gaps=gaps,
            next_actions=next_actions,
            disclaimer=DISCLAIMER,
        )

    def detect(self, profile: ProcessingActivityProfile) -> list[DetectionHit]:
        hits = [hit for rule in ALL_RULES if (hit := rule.match(profile)) is not None]

        if profile.personal_data_categories:
            hits.append(
                DetectionHit(
                    "PD0",
                    PrivacyRisk.STANDARD_PERSONAL_DATA,
                    "explicit personal-data categories",
                    ("personal_data_categories",),
                    0.85,
                    "The profile explicitly lists personal data categories.",
                    55,
                )
            )
        if profile.special_category_data:
            hits.append(
                DetectionHit(
                    "SC0",
                    PrivacyRisk.SPECIAL_CATEGORY_DATA,
                    "explicit special-category data",
                    ("special_category_data",),
                    0.9,
                    "The profile explicitly lists special-category data.",
                    95,
                )
            )
        if profile.children_data:
            hits.append(
                DetectionHit(
                    "C0",
                    PrivacyRisk.CHILDREN_DATA,
                    "explicit children-data flag",
                    ("children_data",),
                    0.9,
                    "The profile explicitly indicates children's data.",
                    90,
                )
            )
        if profile.criminal_offence_data:
            hits.append(
                DetectionHit(
                    "CR0",
                    PrivacyRisk.CRIMINAL_OFFENCE_DATA,
                    "explicit criminal-offence-data flag",
                    ("criminal_offence_data",),
                    0.9,
                    "The profile explicitly indicates criminal offence or conviction data.",
                    90,
                )
            )
        if profile.automated_decision_making:
            hits.append(
                DetectionHit(
                    "ADM0",
                    PrivacyRisk.AUTOMATED_DECISION_MAKING,
                    "explicit automated-decision flag",
                    ("automated_decision_making",),
                    0.9,
                    "The profile explicitly indicates automated decision-making.",
                    92,
                )
            )
        if profile.transfers_outside_eea or profile.transfer_countries:
            hits.append(
                DetectionHit(
                    "TR0",
                    PrivacyRisk.INTERNATIONAL_TRANSFER,
                    "explicit international-transfer flag",
                    ("transfers_outside_eea",),
                    0.9,
                    "The profile explicitly indicates transfers outside the EEA.",
                    88,
                )
            )
        if profile.large_scale_processing or profile.systematic_monitoring or profile.public_area_monitoring:
            hits.append(
                DetectionHit(
                    "HR0",
                    PrivacyRisk.HIGH_RISK_PROCESSING,
                    "explicit high-risk-processing flag",
                    ("large_scale_or_monitoring",),
                    0.88,
                    "The profile explicitly indicates large-scale processing or systematic monitoring.",
                    86,
                )
            )

        return sorted(hits, key=lambda hit: (hit.severity, hit.confidence), reverse=True)

    def classify(
        self,
        profile: ProcessingActivityProfile,
        detections: list[DetectionHit],
    ) -> PrivacyRisk:
        if missing_core_profile_fields(profile):
            return PrivacyRisk.NEEDS_REVIEW

        categories = {hit.category for hit in detections}
        priority = (
            PrivacyRisk.SPECIAL_CATEGORY_DATA,
            PrivacyRisk.AUTOMATED_DECISION_MAKING,
            PrivacyRisk.CRIMINAL_OFFENCE_DATA,
            PrivacyRisk.CHILDREN_DATA,
            PrivacyRisk.HIGH_RISK_PROCESSING,
            PrivacyRisk.INTERNATIONAL_TRANSFER,
            PrivacyRisk.STANDARD_PERSONAL_DATA,
        )
        for category in priority:
            if category in categories:
                return category

        if profile.ai_or_analytics or profile.processors or profile.recipients:
            return PrivacyRisk.NEEDS_REVIEW
        return PrivacyRisk.NO_PERSONAL_DATA

    def verify_evidence(
        self,
        profile: ProcessingActivityProfile,
        primary_risk: PrivacyRisk,
        detections: list[DetectionHit],
    ) -> list[EvidenceCheck]:
        required_categories = {primary_risk}
        required_categories.update(hit.category for hit in detections)
        if PrivacyRisk.STANDARD_PERSONAL_DATA in required_categories:
            required_categories.add(PrivacyRisk.STANDARD_PERSONAL_DATA)

        artifacts: dict[str, set[PrivacyRisk]] = {}
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
        profile: ProcessingActivityProfile,
        primary_risk: PrivacyRisk,
    ) -> list[str]:
        gaps: list[str] = []
        if primary_risk != PrivacyRisk.NO_PERSONAL_DATA and profile.lawful_basis == LawfulBasis.UNKNOWN:
            gaps.append("Lawful basis is unknown; document one Article 6 basis per purpose.")
        if primary_risk != PrivacyRisk.NO_PERSONAL_DATA and not profile.retention_period.strip():
            gaps.append("Retention period is missing; define deletion or review schedule.")
        if profile.actor_role == ActorRole.UNKNOWN and primary_risk != PrivacyRisk.NO_PERSONAL_DATA:
            gaps.append("Controller/processor role is unknown; allocate GDPR responsibilities.")

        for check in evidence_checks:
            if check.status == EvidenceStatus.MISSING:
                gaps.append(f"Missing {check.artifact} for {', '.join(c.value for c in check.required_for)}.")
            elif check.status == EvidenceStatus.PARTIAL:
                gaps.append(f"Incomplete {check.artifact}; finish and approve before relying on it.")

        return gaps

    def collect_obligations(
        self,
        primary_risk: PrivacyRisk,
        detections: list[DetectionHit],
    ) -> list[str]:
        categories = {primary_risk}
        categories.update(hit.category for hit in detections)
        ordered = [
            PrivacyRisk.NO_PERSONAL_DATA,
            PrivacyRisk.STANDARD_PERSONAL_DATA,
            PrivacyRisk.SPECIAL_CATEGORY_DATA,
            PrivacyRisk.CHILDREN_DATA,
            PrivacyRisk.CRIMINAL_OFFENCE_DATA,
            PrivacyRisk.AUTOMATED_DECISION_MAKING,
            PrivacyRisk.INTERNATIONAL_TRANSFER,
            PrivacyRisk.HIGH_RISK_PROCESSING,
            PrivacyRisk.NEEDS_REVIEW,
        ]
        obligations: list[str] = []
        for category in ordered:
            if category in categories:
                for item in OBLIGATIONS[category]:
                    if item not in obligations:
                        obligations.append(item)
        return obligations

    def recommend_actions(
        self,
        primary_risk: PrivacyRisk,
        gaps: list[str],
        detections: list[DetectionHit],
        profile: ProcessingActivityProfile,
    ) -> list[str]:
        actions: list[str] = []
        if primary_risk == PrivacyRisk.NO_PERSONAL_DATA:
            actions.append("Keep a scope memo and reassess if identifiers or logs are added.")
            return actions

        actions.extend(
            [
                "Create or update the Record of Processing Activities.",
                "Map data flows from collection through deletion, including processors and recipients.",
                "Confirm lawful basis, transparency notice, minimisation, retention, and security controls.",
            ]
        )
        if profile.actor_role in {ActorRole.PROCESSOR, ActorRole.SUBPROCESSOR}:
            actions.append("Confirm Article 28 processor terms and customer instructions.")
        if primary_risk in {
            PrivacyRisk.SPECIAL_CATEGORY_DATA,
            PrivacyRisk.HIGH_RISK_PROCESSING,
            PrivacyRisk.AUTOMATED_DECISION_MAKING,
            PrivacyRisk.CRIMINAL_OFFENCE_DATA,
        }:
            actions.append("Run or refresh the DPIA and document residual risk decisions.")
        if profile.transfers_outside_eea or PrivacyRisk.INTERNATIONAL_TRANSFER in {hit.category for hit in detections}:
            actions.append("Validate transfer mechanism, SCCs, transfer impact assessment, and supplementary measures.")
        if profile.lawful_basis == LawfulBasis.LEGITIMATE_INTERESTS:
            actions.append("Complete and approve a Legitimate Interests Assessment.")
        if profile.lawful_basis == LawfulBasis.CONSENT:
            actions.append("Verify consent is specific, informed, freely given, recorded, and withdrawable.")
        if gaps:
            actions.append("Resolve missing or partial evidence artifacts listed in the gaps section.")
        return actions

    def estimate_confidence(
        self,
        primary_risk: PrivacyRisk,
        detections: list[DetectionHit],
        profile: ProcessingActivityProfile,
    ) -> float:
        if primary_risk == PrivacyRisk.NEEDS_REVIEW:
            return 0.35
        if not detections:
            return 0.75 if primary_risk == PrivacyRisk.NO_PERSONAL_DATA else 0.55
        top = max(hit.confidence for hit in detections)
        evidence_bonus = 0.05 if profile.evidence else 0.0
        explicit_bonus = 0.05 if profile.personal_data_categories else 0.0
        return round(min(0.98, top + evidence_bonus + explicit_bonus), 2)


def missing_core_profile_fields(profile: ProcessingActivityProfile) -> bool:
    required = [profile.description, profile.purpose]
    return any(not value.strip() for value in required)


def keyword_matches(corpus: str, keyword: str) -> bool:
    """Match keywords as words/phrases, not accidental substrings."""

    normalized = " ".join(corpus.lower().split())
    escaped = re.escape(keyword.lower().strip())
    pattern = rf"(?<![a-z0-9_]){escaped}(?![a-z0-9_])"
    return re.search(pattern, normalized) is not None


def load_profile(path: Path) -> ProcessingActivityProfile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ProcessingActivityProfile.from_mapping(payload)


def demo_profile() -> ProcessingActivityProfile:
    return ProcessingActivityProfile(
        name="Customer Support AI Assistant",
        description=(
            "Processes customer support tickets, email addresses, order IDs, CRM notes, "
            "chat transcripts, and refund history to draft support responses."
        ),
        purpose="Resolve support requests and improve response quality.",
        actor_role=ActorRole.CONTROLLER,
        lawful_basis=LawfulBasis.CONTRACT,
        controller_name="Example Retail Ltd",
        data_subjects=("customers", "support agents"),
        personal_data_categories=("name", "email", "address", "order history", "support transcript"),
        recipients=("cloud model provider", "support platform"),
        processors=("LLM API provider", "CRM vendor"),
        source_systems=("CRM", "support inbox", "orders database"),
        retention_period="Support tickets retained for 24 months unless legal hold applies.",
        geography="EU/EEA",
        transfers_outside_eea=True,
        transfer_countries=("United States",),
        security_measures=("encryption", "access control", "audit logs", "PII redaction"),
        ai_or_analytics=True,
        evidence={
            "processing_inventory_ropa": "partial",
            "lawful_basis_assessment": "present",
            "privacy_notice": "partial",
            "data_minimisation_review": "missing",
            "retention_schedule": "present",
            "security_controls": "partial",
            "transfer_mapping": "partial",
            "adequacy_or_sccs": "missing",
        },
    )


def sample_profile_json() -> str:
    return json.dumps(asdict(demo_profile()), indent=2)


def guide() -> str:
    return dedent(
        """
        GDPR detection, verification, and assessment workflow:

        1. Create a processing activity profile
           Capture purpose, role, lawful basis, data subjects, personal data,
           processors, recipients, retention, security measures, and transfers.

        2. Detect privacy triggers
           The rule engine screens for personal data, special category data,
           children data, criminal offence data, automated decision-making,
           high-risk processing, and international transfers.

        3. Classify privacy risk
           Priority order is: special category -> automated decision-making ->
           criminal offence -> children data -> high-risk processing ->
           international transfer -> standard personal data -> no personal data.

        4. Verify evidence
           The checker validates ROPA, lawful basis, privacy notice, DSR workflow,
           DPIA, processor terms, SCCs, retention, security, and breach response.

        5. Assess and remediate
           The report lists principles, likely obligations, gaps, and next actions.

        Commands:
           python ai/gdpr.py --mode guide
           python ai/gdpr.py --mode sample-profile
           python ai/gdpr.py --mode demo --format markdown
           python ai/gdpr.py --mode assess --input processing_profile.json --format json
        """
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="GDPR detection and assessment helper")
    parser.add_argument(
        "--mode",
        choices=("guide", "sample-profile", "demo", "assess"),
        default="guide",
    )
    parser.add_argument("--input", help="Path to processing activity profile JSON.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()

    if args.mode == "guide":
        print(guide())
        return

    if args.mode == "sample-profile":
        print(sample_profile_json())
        return

    profile = demo_profile() if args.mode == "demo" else load_profile(Path(args.input or ""))
    report = GDPRAssessor().assess(profile)
    print(report.to_markdown() if args.format == "markdown" else report.to_json())


if __name__ == "__main__":
    main()
