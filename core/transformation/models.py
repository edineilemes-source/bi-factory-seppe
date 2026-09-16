"""Results and metadata for local dimensional transformation runs."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TransformationRunStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    COMPLETED_WITH_REJECTIONS = "COMPLETED_WITH_REJECTIONS"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class TransformationRunReadiness(str, Enum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    FAIL = "FAIL"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TransformationCheckpoint(BaseModel):
    run_id: str
    step_id: str
    status: StepStatus
    fingerprint: str
    artifact_paths: list[str]
    completed_at: datetime | None = None


class SurrogateKeyMapEntry(BaseModel):
    dimension_id: str
    business_key: list[Any]
    staging_surrogate_key: int | str
    source_rows: list[str]
    unknown_member: bool = False
    status: str = "RESOLVED"


class QuarantineResult(BaseModel):
    source_row_id: str
    source_data_reference: str
    reason_code: str
    field: str | None = None
    effective_value: Any = None
    action: str
    retryable: bool
    target_step: str
    lineage: list[str]


class StagedDimensionResult(BaseModel):
    dimension_id: str
    target_table: str
    row_count: int
    inserted_member_count: int
    updated_member_count: int
    unchanged_member_count: int
    unknown_member_created: bool
    surrogate_key_map: list[SurrogateKeyMapEntry]
    staged_rows: list[dict[str, Any]]
    rejected_rows: list[QuarantineResult]
    warnings: list[str]
    artifact_path: str | None = None
    fingerprint: str


class MeasureMetric(BaseModel):
    target_column: str
    count: int
    total: str | None
    minimum: str | None
    maximum: str | None


class StagedFactResult(BaseModel):
    fact_id: str
    target_table: str
    grain: list[str]
    source_row_count: int
    staged_row_count: int
    rejected_row_count: int
    unknown_member_usage_count: int
    unresolved_lookup_count: int
    measure_metrics: list[MeasureMetric]
    staged_rows: list[dict[str, Any]]
    warnings: list[str]
    artifact_path: str | None = None
    fingerprint: str


class StagedBridgeResult(BaseModel):
    bridge_id: str
    target_table: str
    staged_row_count: int
    duplicate_pair_count: int
    unresolved_lookup_count: int
    staged_rows: list[dict[str, Any]]
    warnings: list[str]
    artifact_path: str | None = None
    fingerprint: str


class MeasureReconciliationResult(BaseModel):
    source_field_id: str
    target_table: str
    target_column: str
    source_total: str | None
    staged_total: str | None
    difference: str | None
    percentage_difference: str | None
    tolerance: str
    status: str


class FKResolutionMetric(BaseModel):
    dimension_id: str
    resolved_lookups: int
    unresolved_lookups: int
    unknown_member_uses: int
    rejected_lookups: int
    resolution_rate: float


class TransformationReconciliationReport(BaseModel):
    source_row_count: int
    prepared_row_count: int
    staged_fact_row_count: int
    rejected_row_count: int
    quarantined_row_count: int
    explicitly_excluded_count: int
    fk_resolution_rates: list[FKResolutionMetric]
    unknown_member_usage: int
    measure_reconciliations: list[MeasureReconciliationResult]
    duplicate_checks: dict[str, int]
    grain_checks: dict[str, bool]
    status: str
    tolerances: list[str]
    failures: list[str]
    warnings: list[str]
    artifact_path: str | None = None
    fingerprint: str


class TransformationMetrics(BaseModel):
    prepared_rows: int
    staged_dimension_rows: int
    staged_fact_rows: int
    staged_bridge_rows: int
    rejected_rows: int
    quarantined_rows: int
    unknown_member_uses: int
    target_field_coverage_percentage: float


class TransformationLineage(BaseModel):
    source_document_id: str
    analysis_id: str
    prepared_dataset_id: str
    prepared_dataset_version: int
    etl_plan_id: str
    etl_plan_version: int
    physical_schema_plan_id: str


class DimensionalTransformationRun(BaseModel):
    run_id: str
    load_batch_id: str
    etl_plan_id: str
    etl_plan_version: int
    prepared_dataset_id: str
    prepared_dataset_version: int
    prepared_dataset_fingerprint: str
    physical_schema_plan_id: str
    status: TransformationRunStatus
    readiness: TransformationRunReadiness
    ready_for_database_dry_run: bool
    started_at: datetime
    finished_at: datetime | None
    execution_steps: list[TransformationCheckpoint]
    dimension_results: list[StagedDimensionResult]
    fact_results: list[StagedFactResult]
    bridge_results: list[StagedBridgeResult]
    surrogate_key_maps: list[SurrogateKeyMapEntry]
    rejected_rows: list[QuarantineResult]
    quarantine_rows: list[QuarantineResult]
    reconciliation_report: TransformationReconciliationReport
    metrics: TransformationMetrics
    warnings: list[str]
    blockers: list[str]
    artifact_root: str | None
    lineage: TransformationLineage
    fingerprint: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
