"""Auditable contracts for deterministic data-quality analysis."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from core.profiling.models import SemanticRole


class IdentifierKind(str, Enum):
    TECHNICAL_KEY = "technical_key"
    BUSINESS_IDENTIFIER = "business_identifier"
    BUSINESS_KEY = "business_key"


class ValueLayer(BaseModel):
    """Value lineage; source_value is immutable after observation."""

    model_config = ConfigDict(frozen=True)
    source_value: Any
    normalized_value: Any | None = None
    validated_value: Any | None = None

    @computed_field
    @property
    def effective_value(self) -> Any:
        """Resolve explicit validated/normalized values, including an explicit NULL."""
        if "validated_value" in self.model_fields_set:
            return self.validated_value
        if "normalized_value" in self.model_fields_set:
            return self.normalized_value
        return self.source_value


class FieldIdentity(BaseModel):
    source_document_id: str
    analysis_id: str
    source_field_id: str
    technical_key: str | None = None
    business_identifier: str | None = None
    business_key: str | None = None


class QualityStatus(str, Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ISSUES = "completed_with_issues"


class QualitySeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class FieldRequirement(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    CONDITIONAL = "conditional"
    UNKNOWN = "unknown"


class FieldApplicability(str, Enum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    CONDITIONAL = "conditional"
    UNKNOWN = "unknown"


class FieldQualityStatus(str, Enum):
    EVALUATED = "evaluated"
    NOT_EVALUATED = "not_evaluated"
    NEEDS_BUSINESS_RULE = "needs_business_rule"


class QualityDefectStatus(str, Enum):
    OBSERVED_ANOMALY = "observed_anomaly"
    SUSPECTED = "suspected"
    CONFIRMED_DEFECT = "confirmed_defect"
    NOT_A_DEFECT = "not_a_defect"
    NEEDS_BUSINESS_RULE = "needs_business_rule"


class BlockingScope(str, Enum):
    QUALITY = "quality"
    PREPARED_DATASET = "prepared_dataset"
    GRAIN = "grain"
    DIMENSIONAL = "dimensional"
    DDL = "ddl"
    ETL = "etl"
    GLOBAL = "global"


class QualityGateStatus(str, Enum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    BLOCKED = "BLOCKED"


class IdentifierConstraint(BaseModel):
    """Minimal future grain contract; identifiers are non-unique by default."""

    unique: bool = False
    business_key: bool = False
    grain_declared: bool = False
    technical_key: bool = False
    pattern: str | None = None
    exact_length: int | None = Field(default=None, ge=1)
    validated: bool = False


class QualityIssueType(str, Enum):
    MISSING_VALUE = "missing_value"
    PLACEHOLDER_VALUE = "placeholder_value"
    INVALID_TYPE = "invalid_type"
    FORMAT_INCONSISTENCY = "format_inconsistency"
    DUPLICATE_VALUE = "duplicate_value"
    DUPLICATE_RECORD = "duplicate_record"
    OUTLIER = "outlier"
    DOMAIN_INCONSISTENCY = "domain_inconsistency"
    IDENTIFIER_INCONSISTENCY = "identifier_inconsistency"
    IDENTIFIER_LENGTH_VARIATION = "identifier_length_variation"
    INVALID_IDENTIFIER_FORMAT = "invalid_identifier_format"
    REFERENTIAL_CANDIDATE_ISSUE = "referential_candidate_issue"
    # Backward-compatible preliminary names.
    INVALID_FORMAT = "invalid_format"
    DUPLICATE = "duplicate"
    INCONSISTENT_VALUE = "inconsistent_value"
    REFERENTIAL_INTEGRITY = "referential_integrity"


# Referential checks need declared relationships, which do not exist before
# multidimensional modeling. The contract is explicit instead of guessing.
QUALITY_RULE_IMPLEMENTATION_STATUS: dict[QualityIssueType, str] = {
    issue_type: ("not_implemented_requires_declared_relationships"
                 if issue_type == QualityIssueType.REFERENTIAL_CANDIDATE_ISSUE
                 else "implemented")
    for issue_type in QualityIssueType
}


class QualityIssue(BaseModel):
    """One grouped finding, never one message per affected cell."""

    issue_id: str
    analysis_id: str
    source_field_id: str | None = None
    sheet_name: str | None = None
    field_name: str | None = None
    issue_type: QualityIssueType
    severity: QualitySeverity = QualitySeverity.WARNING
    source_value: Any | None = None  # retained for compatibility/single-value findings
    affected_count: int = 1
    affected_percentage: float = 0.0
    examples: list[Any] = Field(default_factory=list, max_length=5)
    row_numbers: list[int] = Field(default_factory=list, max_length=5)
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    suggested_action: str = "Inspecionar os valores na fonte; nenhuma correção foi aplicada."
    quality_defect_status: QualityDefectStatus = QualityDefectStatus.OBSERVED_ANOMALY
    blocking_eligible: bool = False
    blocking_reason: str | None = None
    blocking_scope: list[BlockingScope] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def derive_legacy_evidence(cls, data: Any) -> Any:
        if not isinstance(data, dict) or "quality_defect_status" in data:
            return data
        evidence = data.get("evidence") or {}
        if evidence.get("quality_defect") is True:
            data = dict(data)
            data["quality_defect_status"] = QualityDefectStatus.CONFIRMED_DEFECT.value
            data["blocking_eligible"] = True
            data["blocking_reason"] = "Regra explícita registrada no relatório legado."
            data["blocking_scope"] = [BlockingScope.PREPARED_DATASET.value]
        return data


class FieldQualitySummary(BaseModel):
    source_field_id: str
    sheet_name: str
    field_name: str
    semantic_role: SemanticRole
    effective_semantic_role: SemanticRole | None = None
    requirement: FieldRequirement = FieldRequirement.UNKNOWN
    applicability: FieldApplicability = FieldApplicability.UNKNOWN
    quality_status: FieldQualityStatus = FieldQualityStatus.EVALUATED
    score: float | None = Field(default=None, ge=0, le=100)
    quality_score: float | None = Field(default=None, ge=0, le=100)
    missing_count: int = 0
    missing_percentage: float = 0.0
    placeholder_count: int = 0
    placeholder_percentage: float = 0.0
    observed_completeness: float = Field(default=100.0, ge=0, le=100)
    issues_count: int
    affected_count: int
    affected_percentage: float
    maximum_severity: QualitySeverity | None = None

    @model_validator(mode="after")
    def populate_compatibility_fields(self) -> "FieldQualitySummary":
        """Read old reports while persisting both old and contextual names."""
        if self.effective_semantic_role is None:
            self.effective_semantic_role = self.semantic_role
        if self.quality_score is None and self.score is not None:
            self.quality_score = self.score
        if self.score is None and self.quality_score is not None:
            self.score = self.quality_score
        return self


class ReconciliationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReconciliationCandidate(BaseModel):
    """Conservative proposal only; never an automatic correction."""

    candidate_id: str
    analysis_id: str
    source_field_id: str
    source_value: Any
    normalized_value: Any | None = None
    proposed_validated_value: Any | None = None
    candidate_value: Any | None = None
    reason: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    status: ReconciliationStatus = ReconciliationStatus.PENDING
    evidence: list[str] = Field(default_factory=list)
    requires_validation: bool = True


class QualityGateDecision(BaseModel):
    status: QualityGateStatus
    blocking_issues: int = 0
    non_blocking_issues: int = 0
    unresolved_business_rules: int = 0
    warnings: int = 0
    reason: str
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DataQualityReport(BaseModel):
    analysis_id: str
    quality_report_id: str | None = None
    status: QualityStatus = QualityStatus.NOT_STARTED
    total_rows: int = 0
    total_fields: int = 0
    score: float = Field(default=100, ge=0, le=100)
    observed_completeness: float = Field(default=100, ge=0, le=100)
    eligible_cells: int = 0
    evaluated_fields: int = 0
    not_evaluated_fields: int = 0
    issues_count: int = 0
    affected_rows: int = 0
    critical_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    issues: list[QualityIssue] = Field(default_factory=list)
    field_summaries: list[FieldQualitySummary] = Field(default_factory=list)
    reconciliation_candidates: list[ReconciliationCandidate] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
    ruleset_version: str = "quality-contextual-v1"
    fingerprint: str | None = None
    gate_decision: QualityGateDecision | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    score_formula: str = (
        "100 - min(100, 100 * weighted_quality_defects / eligible_cells), "
        "pesos INFO=0.25, WARNING=0.5, ERROR=1, CRITICAL=2; ausências não "
        "exigidas não são defeitos e campos NOT_EVALUATED ficam fora do denominador"
    )


class LineageEvent(BaseModel):
    """Future audit event; source values are always retained separately."""

    event_type: str
    source_field_id: str
    row_number: int | None = None
    value_layer: ValueLayer
    reason: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PreparedDataset(BaseModel):
    """Contract only: no definitive prepared file is produced in Sprint 2.1."""

    analysis_id: str
    source_document_id: str
    quality_report_id: str | None = None
    lineage: list[LineageEvent] = Field(default_factory=list)
    generated: bool = False
