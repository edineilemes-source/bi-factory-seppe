"""Persistable contracts separating process, event, grain and business key."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GrainClassification(str, Enum):
    SINGLE_GRAIN = "SINGLE_GRAIN"
    MULTI_GRAIN = "MULTI_GRAIN"
    AMBIGUOUS_GRAIN = "AMBIGUOUS_GRAIN"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class GrainDiscoveryStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    DISCOVERED = "DISCOVERED"
    NEEDS_VALIDATION = "NEEDS_VALIDATION"
    VALIDATED = "VALIDATED"
    AMBIGUOUS = "AMBIGUOUS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class CandidateStatus(str, Enum):
    PROPOSED = "PROPOSED"
    RECOMMENDED = "RECOMMENDED"
    REJECTED = "REJECTED"
    SELECTED = "SELECTED"


class GrainValidationStatus(str, Enum):
    OBSERVED = "OBSERVED"
    CONFIRMED = "CONFIRMED"
    CORRECTED = "CORRECTED"
    UNKNOWN = "UNKNOWN"


class KnowledgeValidationStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    CORRECTED = "CORRECTED"
    UNKNOWN = "UNKNOWN"


class GrainReadiness(str, Enum):
    READY_FOR_DIMENSIONAL_MODELING = "READY_FOR_DIMENSIONAL_MODELING"
    NOT_READY = "NOT_READY"


class MeasureAggregationHint(str, Enum):
    UNKNOWN = "UNKNOWN"
    ADDITIVE = "ADDITIVE"
    SEMI_ADDITIVE = "SEMI_ADDITIVE"
    NON_ADDITIVE = "NON_ADDITIVE"
    REQUIRES_VALIDATION = "REQUIRES_VALIDATION"
    # Compatibility with persisted Sprint 3.0 reports.
    ADDITIVE_CANDIDATE = "ADDITIVE_CANDIDATE"
    NON_ADDITIVE_CANDIDATE = "NON_ADDITIVE_CANDIDATE"
    SEMI_ADDITIVE_CANDIDATE = "SEMI_ADDITIVE_CANDIDATE"
    REQUIRES_GRAIN_VALIDATION = "REQUIRES_GRAIN_VALIDATION"


class ProcessCandidate(BaseModel):
    name: str
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)


class EventCandidate(BaseModel):
    name: str
    confidence: float = Field(ge=0, le=1)
    source_fields: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class QualityDependency(BaseModel):
    source_field_id: str | None = None
    issue_id: str
    issue_type: str
    severity: str
    affected_count: int
    description: str


class ObservedFunctionalDependency(BaseModel):
    determinant: list[str]
    dependent: str
    support: int
    violations: int
    confidence: float = Field(ge=0, le=1)
    observed_only: bool = True


class IdentifierHierarchy(BaseModel):
    parent: str
    child: str
    evidence: str
    confidence: float = Field(ge=0, le=1)


class AggregationRisk(BaseModel):
    risk_id: str
    measure_field_id: str
    repeated_at_fields: list[str]
    candidate_grain_fields: list[str]
    affected_groups: int
    affected_rows: int
    aggregation_hint: MeasureAggregationHint = MeasureAggregationHint.REQUIRES_GRAIN_VALIDATION
    description: str
    evidence: list[str] = Field(default_factory=list)


class GrainCandidate(BaseModel):
    candidate_id: str
    human_readable_description: str
    candidate_fields: list[str]
    inferred_process: str | None = None
    inferred_event: str | None = None
    row_count: int
    complete_row_count: int | None = None
    distinct_count: int
    duplicate_count: int
    uniqueness_ratio: float = Field(ge=0, le=1)
    coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    null_ratio: float = Field(ge=0, le=1)
    stability: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    semantic_evidence_score: float | None = Field(default=None, ge=0, le=1)
    business_process_compatibility: str | None = None
    evidence: list[str] = Field(default_factory=list)
    counter_evidence: list[str] = Field(default_factory=list)
    quality_dependencies: list[QualityDependency] = Field(default_factory=list)
    status: CandidateStatus = CandidateStatus.PROPOSED


class GrainDiscoveryReport(BaseModel):
    grain_discovery_report_id: str
    source_document_id: str
    prepared_dataset_id: str
    prepared_dataset_version: int
    prepared_dataset_fingerprint: str
    analysis_id: str
    status: GrainDiscoveryStatus
    dataset_row_count: int
    candidate_count: int
    grain_classification: GrainClassification
    process_candidates: list[ProcessCandidate] = Field(default_factory=list)
    event_candidates: list[EventCandidate] = Field(default_factory=list)
    grain_candidates: list[GrainCandidate] = Field(default_factory=list)
    functional_dependencies: list[ObservedFunctionalDependency] = Field(default_factory=list)
    identifier_hierarchies: list[IdentifierHierarchy] = Field(default_factory=list)
    aggregation_risks: list[AggregationRisk] = Field(default_factory=list)
    quality_dependencies: list[QualityDependency] = Field(default_factory=list)
    recommended_candidate_id: str | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    requires_user_validation: bool = True
    candidate_limit_configured: int
    candidates_truncated: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = Field(ge=1)
    engine_version: str = "legacy-grain-v1"


class GrainDefinition(BaseModel):
    grain_id: str
    grain_discovery_report_id: str
    source_document_id: str
    prepared_dataset_id: str
    prepared_dataset_version: int
    prepared_dataset_fingerprint: str
    analysis_id: str
    status: GrainReadiness
    description: str
    user_grain_description: str | None = None
    grain_type: GrainClassification
    observed_process: str | None = None
    validated_process: str | None = None
    process_validation_status: KnowledgeValidationStatus = KnowledgeValidationStatus.UNKNOWN
    observed_event: str | None = None
    validated_event: str | None = None
    event_validation_status: KnowledgeValidationStatus = KnowledgeValidationStatus.UNKNOWN
    grain_fields: list[str] = Field(default_factory=list)
    # Explicit groups for validated MULTI_GRAIN definitions. Older definitions
    # remain compatible and fall back to one group per grain field.
    grain_groups: list[list[str]] = Field(default_factory=list)
    selected_candidate_id: str | None = None
    supporting_fields: list[str] = Field(default_factory=list)
    candidate_business_key: list[str] = Field(default_factory=list)
    uniqueness_percentage: float = 0
    duplicate_percentage: float = 0
    confidence: float = Field(default=0, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    validation_status: GrainValidationStatus
    validated_by: str | None = None
    validated_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = Field(ge=1)

    @property
    def effective_process(self) -> str | None:
        return self.validated_process or self.observed_process

    @property
    def effective_event(self) -> str | None:
        return self.validated_event or self.observed_event

    @property
    def effective_grain_description(self) -> str:
        return self.user_grain_description or self.description
