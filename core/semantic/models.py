"""Contracts for explainable, auditable semantic validation."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, computed_field

from core.profiling.models import SemanticRole, WorkbookProfile


class DecisionLevel(str, Enum):
    AUTO_ACCEPT = "auto_accept"
    CONFIRM = "confirm"
    ASK = "ask"
    DEFERRED_NO_EVIDENCE = "deferred_no_evidence"
    REUSE = "reuse"
    RECONFIRM = "reconfirm"


class EvidenceClass(str, Enum):
    LEXICAL_HINT = "LEXICAL_HINT"
    STRUCTURAL_EVIDENCE = "STRUCTURAL_EVIDENCE"
    CONTENT_EVIDENCE = "CONTENT_EVIDENCE"
    VALIDATED_KNOWLEDGE = "VALIDATED_KNOWLEDGE"


class SemanticReuseAction(str, Enum):
    REUSE = "REUSE"
    RECONFIRM = "RECONFIRM"
    ASK = "ASK"
    DEFER = "DEFER"
    AUTO_ACCEPT = "AUTO_ACCEPT"
    OPTIONAL_CONFIRM = "OPTIONAL_CONFIRM"


class KnowledgeValidationSource(str, Enum):
    USER_CONFIRMED = "USER_CONFIRMED"
    USER_CORRECTED = "USER_CORRECTED"
    AUTO_ACCEPTED = "AUTO_ACCEPTED"
    SYSTEM_INFERRED = "SYSTEM_INFERRED"
    IMPORTED = "IMPORTED"


class KnowledgeValidationStatus(str, Enum):
    VALIDATED = "VALIDATED"
    NEEDS_RECONFIRMATION = "NEEDS_RECONFIRMATION"


class QuestionType(str, Enum):
    SEMANTIC_ROLE = "semantic_role"
    IDENTIFIER_MEANING = "identifier_meaning"
    CODE_MEANING = "code_meaning"
    MEASURE_MEANING = "measure_meaning"
    DATE_MEANING = "date_meaning"
    FIELD_PURPOSE = "field_purpose"
    TYPE_CONFIRMATION = "type_confirmation"


class QuestionStatus(str, Enum):
    PENDING = "pending"
    ANSWERED = "answered"
    SKIPPED = "skipped"


class QuestionPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ValidationStatus(str, Enum):
    AUTO_ACCEPTED = "auto_accepted"
    USER_CONFIRMED = "user_confirmed"
    USER_CORRECTED = "user_corrected"
    UNRESOLVED = "unresolved"


class AnalysisStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    COMPLETED_WITH_UNRESOLVED = "completed_with_unresolved"


class SemanticConflict(BaseModel):
    """Conflict between independent sources of semantic evidence."""

    code: str
    message: str
    sources: list[str]
    severity: QuestionPriority = QuestionPriority.HIGH
    evidence_class: EvidenceClass = EvidenceClass.STRUCTURAL_EVIDENCE


class SemanticQuestion(BaseModel):
    question_id: str
    sheet_name: str
    field_name: str
    technical_name: str
    question_type: QuestionType
    title: str
    question_text: str
    reason: str
    current_hypothesis: SemanticRole
    confidence: float = Field(ge=0.0, le=1.0)
    options: list[str]
    allows_custom_answer: bool = True
    required: bool = False
    priority: QuestionPriority
    evidence: list[str] = Field(default_factory=list)
    conflicts: list[SemanticConflict] = Field(default_factory=list)
    examples: list[Any] = Field(default_factory=list, max_length=5)
    detected_type: str
    recommended_type: str
    status: QuestionStatus = QuestionStatus.PENDING
    previous_validated_role: SemanticRole | None = None
    reuse_action: SemanticReuseAction = SemanticReuseAction.ASK


class SemanticValidation(BaseModel):
    """Validated knowledge kept apart from the observed source profile."""

    sheet_name: str
    field_name: str
    technical_name: str
    source_field_id: str
    business_concept_id: str | None = None
    original_hypothesis: SemanticRole
    original_confidence: float = Field(ge=0.0, le=1.0)
    validated_role: SemanticRole | None = None
    user_answer: str | None = None
    validation_status: ValidationStatus
    validated_at: datetime | None = None
    knowledge_reused: bool = False
    previous_validated_role: SemanticRole | None = None
    semantic_knowledge_id: str | None = None


class SemanticKnowledgeRecord(BaseModel):
    semantic_knowledge_id: str
    source_document_id: str
    source_field_id: str
    normalized_field_name: str
    business_concept_id: str
    validated_semantic_role: SemanticRole
    validation_source: KnowledgeValidationSource
    confidence: float = Field(ge=0, le=1)
    validation_status: KnowledgeValidationStatus = KnowledgeValidationStatus.VALIDATED
    first_validated_analysis_id: str
    last_confirmed_analysis_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evidence_snapshot: list[str] = Field(default_factory=list)
    compatibility_fingerprint: str
    version: int = Field(ge=1)
    origin_question_id: str | None = None
    historical_answer: str | None = None
    migrated_by: str | None = None


class SemanticKnowledgeMigrationStatus(str, Enum):
    COMPLETED = "COMPLETED"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    FAILED = "FAILED"


class SemanticKnowledgeMigrationDecision(BaseModel):
    field: str
    source_analysis_id: str
    question_id: str | None = None
    historical_answer: str | None = None
    mapped_role: SemanticRole | None = None
    migration_action: str
    knowledge_version: int | None = None
    reason: str


class SemanticKnowledgeMigration(BaseModel):
    migration_id: str
    migration_version: int
    started_at: datetime
    completed_at: datetime
    status: SemanticKnowledgeMigrationStatus
    records_scanned: int
    records_eligible: int
    records_created: int
    records_updated_versioned: int
    records_skipped: int
    records_unresolved: int
    conflicts: int
    decisions: list[SemanticKnowledgeMigrationDecision]
    idempotency_status: str
    fingerprint: str


class SemanticCompatibilityResult(BaseModel):
    compatible: bool
    compatibility_score: float = Field(ge=0, le=1)
    supporting_evidence: list[str] = Field(default_factory=list)
    conflicting_evidence: list[str] = Field(default_factory=list)
    reason: str
    action: SemanticReuseAction


class SemanticReuseDecision(BaseModel):
    source_field_id: str
    normalized_field_name: str
    action: SemanticReuseAction
    current_role: SemanticRole
    effective_role: SemanticRole | None = None
    previous_validated_role: SemanticRole | None = None
    semantic_knowledge_id: str | None = None
    compatibility: SemanticCompatibilityResult


class SemanticReuseReport(BaseModel):
    analysis_id: str | None = None
    source_document_id: str | None = None
    total_fields: int
    reused_count: int
    auto_accepted_count: int
    reconfirm_count: int
    ask_count: int
    deferred_count: int
    decisions: list[SemanticReuseDecision]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ValidationSummary(BaseModel):
    fields_analyzed: int
    auto_accepted: int
    need_confirmation: int
    need_answer: int
    confirmed: int
    corrected: int
    unresolved: int


class SemanticValidationReport(BaseModel):
    """Consolidated two-layer report: observation plus validated knowledge."""

    observed_profile: WorkbookProfile
    analysis_id: str | None = None
    source_document_id: str | None = None
    analysis_status: AnalysisStatus = AnalysisStatus.IN_PROGRESS
    questions: list[SemanticQuestion] = Field(default_factory=list)
    validated_semantics: list[SemanticValidation] = Field(default_factory=list)
    decision_by_source_field: dict[str, DecisionLevel] = Field(default_factory=dict)
    summary: ValidationSummary
    reuse_report: SemanticReuseReport | None = None

    @computed_field
    @property
    def auto_accepted_fields(self) -> list[SemanticValidation]:
        return [v for v in self.validated_semantics if v.validation_status == ValidationStatus.AUTO_ACCEPTED]

    @computed_field
    @property
    def confirmed_fields(self) -> list[SemanticValidation]:
        return [v for v in self.validated_semantics if v.validation_status == ValidationStatus.USER_CONFIRMED]

    @computed_field
    @property
    def corrected_fields(self) -> list[SemanticValidation]:
        return [v for v in self.validated_semantics if v.validation_status == ValidationStatus.USER_CORRECTED]

    @computed_field
    @property
    def unresolved_fields(self) -> list[SemanticValidation]:
        return [
            v for v in self.validated_semantics
            if v.validation_status == ValidationStatus.UNRESOLVED
            and v.validated_at is not None
        ]
