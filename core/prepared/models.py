"""Auditable contracts for effective values in a prepared dataset."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from core.profiling.models import SemanticRole
from core.quality.models import (
    FieldApplicability, FieldQualityStatus, FieldRequirement, QualityIssue,
)


class TransformationType(str, Enum):
    TRIM_WHITESPACE = "TRIM_WHITESPACE"
    PLACEHOLDER_TO_NULL = "PLACEHOLDER_TO_NULL"
    IDENTIFIER_CANONICALIZATION = "IDENTIFIER_CANONICALIZATION"
    DATE_CANONICALIZATION = "DATE_CANONICALIZATION"
    BOOLEAN_CANONICALIZATION = "BOOLEAN_CANONICALIZATION"
    TYPE_CANONICALIZATION = "TYPE_CANONICALIZATION"


class PreparedDatasetStatus(str, Enum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    BLOCKED = "BLOCKED"


class PreparedGenerationStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


class PreparedGenerationStepMetric(BaseModel):
    stage: str
    rows_processed: int = 0
    rss_mb: float
    elapsed_seconds: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PreparedGenerationMetrics(BaseModel):
    started_at: datetime
    finished_at: datetime | None = None
    rows: int = 0
    columns: int = 0
    estimated_dataframe_memory_bytes: int = 0
    rss_start_mb: float
    rss_peak_mb: float
    rss_end_mb: float | None = None
    step_metrics: list[PreparedGenerationStepMetric] = Field(default_factory=list)
    artifact_size_bytes: int = 0
    status: PreparedGenerationStatus = PreparedGenerationStatus.NOT_STARTED


class PreparedProgressEvent(BaseModel):
    stage: str
    rows_processed: int
    total_rows: int | None = None
    elapsed_seconds: float
    message: str


class PreparedField(BaseModel):
    source_field_id: str
    sheet_name: str
    source_name: str
    technical_name: str
    effective_semantic_role: SemanticRole
    recommended_type: str
    prepared_type: str
    nullable: bool = True
    requirement: FieldRequirement = FieldRequirement.UNKNOWN
    applicability: FieldApplicability = FieldApplicability.UNKNOWN
    transformation_rules: list[TransformationType] = Field(default_factory=list)
    quality_status: FieldQualityStatus = FieldQualityStatus.NOT_EVALUATED


class PreparedRow(BaseModel):
    """Technical row identity plus effective values keyed by source field id."""

    source_row_id: str
    sheet_name: str
    source_row_number: int
    values: dict[str, Any]


class TransformationRecord(BaseModel):
    transformation_id: str
    analysis_id: str
    source_document_id: str
    source_row_id: str
    row_id: str
    source_field_id: str
    transformation_type: TransformationType
    source_value: Any
    resulting_value: Any
    reason: str
    rule_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PreparedDataset(BaseModel):
    prepared_dataset_id: str
    source_document_id: str
    analysis_id: str
    version: int = Field(ge=1)
    ruleset_version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    row_count: int
    field_count: int
    status: PreparedDatasetStatus
    schema_fields: list[PreparedField] = Field(alias="schema")
    rows: list[PreparedRow]
    transformations: list[TransformationRecord] = Field(default_factory=list)
    transformation_summary: dict[str, int] = Field(default_factory=dict)
    unresolved_quality_issues: list[QualityIssue] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)
    fingerprint: str
    artifact_location: str | None = None

    model_config = {"populate_by_name": True}


class PreparedDatasetArtifact(BaseModel):
    """Lightweight persisted prepared dataset reference safe for UI sessions."""

    prepared_dataset_id: str
    source_document_id: str
    analysis_id: str
    version: int
    ruleset_version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    row_count: int
    field_count: int
    status: PreparedDatasetStatus
    generation_status: PreparedGenerationStatus
    schema_fields: list[PreparedField] = Field(alias="schema")
    transformation_summary: dict[str, int] = Field(default_factory=dict)
    transformations_by_field: dict[str, int] = Field(default_factory=dict)
    total_transformations: int = 0
    statistics: dict[str, Any] = Field(default_factory=dict)
    fingerprint: str
    artifact_location: str
    transformations_location: str | None = None
    artifact_format: str = "csv"
    artifact_size_bytes: int = 0
    artifact_sha256: str
    preview: list[dict[str, Any]] = Field(default_factory=list)
    metrics: PreparedGenerationMetrics

    model_config = {"populate_by_name": True}
