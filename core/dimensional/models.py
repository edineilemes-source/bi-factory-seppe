"""Explainable, persistable contracts for dimensional discovery."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from core.grain.models import AggregationRisk, MeasureAggregationHint, QualityDependency
from core.profiling.models import SemanticRole


class ProposalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    NEEDS_VALIDATION = "NEEDS_VALIDATION"
    VALIDATED = "VALIDATED"
    BLOCKED_BY_GRAIN = "BLOCKED_BY_GRAIN"
    READY_FOR_STAR_SCHEMA = "READY_FOR_STAR_SCHEMA"


class CandidateStatus(str, Enum):
    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"
    CORRECTED = "CORRECTED"
    REJECTED = "REJECTED"
    REQUIRES_VALIDATION = "REQUIRES_VALIDATION"


class FactType(str, Enum):
    TRANSACTION = "TRANSACTION"
    PERIODIC_SNAPSHOT = "PERIODIC_SNAPSHOT"
    ACCUMULATING_SNAPSHOT = "ACCUMULATING_SNAPSHOT"
    FACTLESS = "FACTLESS"
    UNKNOWN = "UNKNOWN"


class DimensionRole(str, Enum):
    REGULAR_DIMENSION = "REGULAR_DIMENSION"
    DEGENERATE_DIMENSION = "DEGENERATE_DIMENSION"
    DEGENERATE_DIMENSION_CANDIDATE = "DEGENERATE_DIMENSION_CANDIDATE"
    ROLE_PLAYING_DIMENSION = "ROLE_PLAYING_DIMENSION"
    ROLE_PLAYING_DIMENSION_CANDIDATE = "ROLE_PLAYING_DIMENSION_CANDIDATE"
    CONFORMED_DIMENSION_CANDIDATE = "CONFORMED_DIMENSION_CANDIDATE"
    JUNK_DIMENSION_CANDIDATE = "JUNK_DIMENSION_CANDIDATE"
    UNKNOWN_DIMENSION_ROLE = "UNKNOWN_DIMENSION_ROLE"


class ModelingRole(str, Enum):
    FACT_ATTRIBUTE = "FACT_ATTRIBUTE"
    DIMENSION_ATTRIBUTE = "DIMENSION_ATTRIBUTE"
    MEASURE = "MEASURE"
    DEGENERATE_IDENTIFIER = "DEGENERATE_IDENTIFIER"
    IGNORED_FOR_ANALYTICS = "IGNORED_FOR_ANALYTICS"
    UNRESOLVED = "UNRESOLVED"


class MeasureCandidate(BaseModel):
    source_field_id: str
    name: str
    effective_semantic_role: SemanticRole
    prepared_type: str
    aggregation_hint: MeasureAggregationHint = MeasureAggregationHint.UNKNOWN
    additivity: MeasureAggregationHint = MeasureAggregationHint.UNKNOWN
    grain_compatibility: bool
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    aggregation_risk: AggregationRisk | None = None
    measure_modeling_warning: str | None = None
    quality_dependencies: list[QualityDependency] = Field(default_factory=list)
    status: CandidateStatus = CandidateStatus.PROPOSED


class DimensionCandidate(BaseModel):
    dimension_candidate_id: str
    name: str
    human_readable_name: str
    source_fields: list[str]
    business_identifier_fields: list[str] = Field(default_factory=list)
    business_key_candidates: list[str] = Field(default_factory=list)
    descriptive_attributes: list[str] = Field(default_factory=list)
    hierarchy_candidates: list[list[str]] = Field(default_factory=list)
    cardinality: int = 0
    dependency_evidence: list[str] = Field(default_factory=list)
    conformed_candidate: bool = False
    role: DimensionRole = DimensionRole.REGULAR_DIMENSION
    role_playing_roles: list[str] = Field(default_factory=list)
    business_concept_id: str | None = None
    suggested_surrogate_key_name: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    quality_dependencies: list[QualityDependency] = Field(default_factory=list)
    status: CandidateStatus = CandidateStatus.PROPOSED


class ConformedDimensionCandidate(BaseModel):
    dimension_candidate_id: str
    business_concept_id: str | None = None
    evidence: list[str] = Field(default_factory=list)
    requires_validation: bool = True


class FieldModelingDecision(BaseModel):
    source_field_id: str
    effective_semantic_role: SemanticRole
    observed_modeling_role: ModelingRole
    validated_modeling_role: ModelingRole | None = None
    effective_modeling_role: ModelingRole
    modeling_role: ModelingRole
    target_candidate_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    requires_validation: bool = False


class FactCandidate(BaseModel):
    fact_candidate_id: str
    prepared_dataset_id: str
    grain_definition_id: str
    name: str
    human_readable_name: str
    process: str | None = None
    event: str | None = None
    fact_type: FactType = FactType.UNKNOWN
    grain_description: str
    grain_fields: list[str]
    measure_candidates: list[str] = Field(default_factory=list)
    degenerate_dimensions: list[str] = Field(default_factory=list)
    foreign_dimension_candidates: list[str] = Field(default_factory=list)
    fact_attributes: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    aggregation_risks: list[AggregationRisk] = Field(default_factory=list)
    quality_dependencies: list[QualityDependency] = Field(default_factory=list)
    status: CandidateStatus = CandidateStatus.PROPOSED


class RecommendedStructure(BaseModel):
    possible_main_fact: str | None = None
    grain: str
    measures: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    degenerate_dimensions: list[str] = Field(default_factory=list)
    conformed_candidates: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    disclaimer: str = "Proposta preliminar; não representa um Star Schema definitivo."


class DimensionalDiscoveryReport(BaseModel):
    report_id: str
    source_document_id: str
    prepared_dataset_id: str
    prepared_dataset_version: int
    prepared_dataset_fingerprint: str
    grain_definition_id: str
    grain_version: int
    analysis_id: str
    status: ProposalStatus
    fact_candidates: list[FactCandidate] = Field(default_factory=list)
    dimension_candidates: list[DimensionCandidate] = Field(default_factory=list)
    measure_candidates: list[MeasureCandidate] = Field(default_factory=list)
    field_decisions: list[FieldModelingDecision] = Field(default_factory=list)
    conformed_candidates: list[ConformedDimensionCandidate] = Field(default_factory=list)
    role_playing_candidates: list[str] = Field(default_factory=list)
    junk_candidates: list[str] = Field(default_factory=list)
    aggregation_risks: list[AggregationRisk] = Field(default_factory=list)
    quality_dependencies: list[QualityDependency] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    recommended_structure: RecommendedStructure
    requires_user_validation: bool = True
    max_fact_candidates: int
    max_dimension_candidates: int
    candidates_truncated: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def ensure_complete_coverage(self) -> "DimensionalDiscoveryReport":
        ids = [item.source_field_id for item in self.field_decisions]
        if len(ids) != len(set(ids)):
            raise ValueError("Cada campo deve possuir exatamente uma decisão de modelagem.")
        return self


class ValidatedDimensionalDiscovery(BaseModel):
    validation_id: str
    report_id: str
    source_document_id: str
    analysis_id: str
    prepared_dataset_id: str
    prepared_dataset_version: int
    prepared_dataset_fingerprint: str
    grain_definition_id: str
    grain_version: int
    status: ProposalStatus
    fact_candidates: list[FactCandidate]
    dimension_candidates: list[DimensionCandidate]
    measure_candidates: list[MeasureCandidate]
    field_decisions: list[FieldModelingDecision]
    accepted_unresolved_fields: list[str] = Field(default_factory=list)
    validated_by: str = "user"
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = Field(ge=1)

