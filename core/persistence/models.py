"""Persistence-facing records independent from Streamlit."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel

from core.semantic.models import AnalysisStatus, SemanticValidationReport
from core.prepared.models import PreparedDatasetStatus
from core.grain.models import GrainDefinition, GrainDiscoveryReport
from core.dimensional.models import DimensionalDiscoveryReport, ValidatedDimensionalDiscovery
from core.star.models import StarSchemaContractReport, ValidatedStarSchemaContract
from core.ddl.models import PhysicalSchemaPlan, PostgreSQLDDLArtifact
from core.etl.models import DimensionalETLPlan, ValidatedDimensionalETLPlan
from core.transformation.models import DimensionalTransformationRun
from core.database_dry_run.models import DatabaseDryRun


class SourceDocument(BaseModel):
    source_document_id: str
    content_sha256: str
    original_name: str
    size_bytes: int
    created_at: datetime


class AnalysisRecord(BaseModel):
    analysis_id: str
    source_document_id: str
    status: AnalysisStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    report: SemanticValidationReport


class AnalysisStage(str, Enum):
    INGESTION = "INGESTION"
    PROFILING = "PROFILING"
    SEMANTIC_VALIDATION = "SEMANTIC_VALIDATION"
    QUALITY = "QUALITY"
    PREPARED_DATASET = "PREPARED_DATASET"
    GRAIN_DISCOVERY = "GRAIN_DISCOVERY"
    DIMENSIONAL_DISCOVERY = "DIMENSIONAL_DISCOVERY"
    STAR_SCHEMA = "STAR_SCHEMA"
    DDL = "DDL"
    ETL_PLAN = "ETL_PLAN"
    TRANSFORMATION = "TRANSFORMATION"
    DATABASE_DRY_RUN = "DATABASE_DRY_RUN"
    COMPLETED = "COMPLETED"
    UNKNOWN = "UNKNOWN"


class AnalysisHistoryItem(BaseModel):
    """Read-only projection of one analysis and its persisted artifacts."""

    analysis_id: str
    source_document_id: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    status: str
    semantic_status: str
    semantic_question_count: int = 0
    semantic_answered_count: int = 0
    semantic_pending_count: int = 0
    semantic_reuse_count: int = 0
    quality_status: str = "not_started"
    quality_report_id: str | None = None
    quality_score: float | None = None
    quality_issue_count: int = 0
    prepared_dataset_status: str = "not_started"
    prepared_dataset_id: str | None = None
    prepared_dataset_version: int | None = None
    grain_status: str = "not_started"
    grain_definition_id: str | None = None
    dimensional_status: str = "not_started"
    star_schema_status: str = "not_started"
    ddl_status: str = "not_started"
    etl_plan_status: str = "not_started"
    transformation_status: str = "not_started"
    database_dry_run_status: str = "not_started"
    current_stage: AnalysisStage = AnalysisStage.UNKNOWN
    last_successful_stage: AnalysisStage = AnalysisStage.UNKNOWN
    artifact_count: int = 0
    has_unfinished_work: bool = True
    is_completed: bool = False
    is_latest: bool = False
    is_resumable: bool = False
    artifact_ids: dict[str, str] = {}
    warnings: list[str] = []


class AnalysisResumeResult(BaseModel):
    analysis_id: str
    source_document_id: str
    current_stage: AnalysisStage
    last_successful_stage: AnalysisStage
    loaded_artifacts: dict[str, Any] = {}
    missing_artifacts: list[str] = []
    warnings: list[str] = []
    resumable: bool
    status: str


class PreparedDatasetRecord(BaseModel):
    prepared_dataset_id: str
    analysis_id: str
    source_document_id: str
    version: int
    status: PreparedDatasetStatus
    fingerprint: str
    ruleset_version: str
    row_count: int
    field_count: int
    artifact_location: str | None = None
    created_at: datetime
    metadata_json: str


class GrainDiscoveryRecord(BaseModel):
    grain_discovery_report_id: str
    prepared_dataset_id: str
    analysis_id: str
    version: int
    created_at: datetime
    report: GrainDiscoveryReport


class GrainDefinitionRecord(BaseModel):
    grain_id: str
    grain_discovery_report_id: str
    prepared_dataset_id: str
    analysis_id: str
    version: int
    created_at: datetime
    definition: GrainDefinition


class DimensionalDiscoveryRecord(BaseModel):
    report_id: str
    prepared_dataset_id: str
    grain_definition_id: str
    analysis_id: str
    version: int
    created_at: datetime
    report: DimensionalDiscoveryReport


class ValidatedDimensionalRecord(BaseModel):
    validation_id: str
    report_id: str
    prepared_dataset_id: str
    grain_definition_id: str
    analysis_id: str
    version: int
    created_at: datetime
    validation: ValidatedDimensionalDiscovery


class StarSchemaContractRecord(BaseModel):
    report_id: str
    prepared_dataset_id: str
    dimensional_discovery_id: str
    analysis_id: str
    version: int
    created_at: datetime
    report: StarSchemaContractReport


class ValidatedStarSchemaRecord(BaseModel):
    validation_id: str
    report_id: str
    prepared_dataset_id: str
    dimensional_discovery_id: str
    analysis_id: str
    version: int
    created_at: datetime
    validation: ValidatedStarSchemaContract


class PhysicalSchemaPlanRecord(BaseModel):
    physical_schema_plan_id: str
    star_schema_contract_id: str
    analysis_id: str
    version: int
    created_at: datetime
    plan: PhysicalSchemaPlan


class PostgreSQLDDLArtifactRecord(BaseModel):
    ddl_artifact_id: str
    physical_schema_plan_id: str
    analysis_id: str
    version: int
    generated_at: datetime
    artifact: PostgreSQLDDLArtifact


class DimensionalETLPlanRecord(BaseModel):
    etl_plan_id: str
    physical_schema_plan_id: str
    prepared_dataset_id: str
    analysis_id: str
    version: int
    created_at: datetime
    plan: DimensionalETLPlan


class ValidatedDimensionalETLPlanRecord(BaseModel):
    validation_id: str
    etl_plan_id: str
    prepared_dataset_id: str
    analysis_id: str
    version: int
    created_at: datetime
    validation: ValidatedDimensionalETLPlan


class DimensionalTransformationRunRecord(BaseModel):
    run_id: str
    etl_plan_id: str
    prepared_dataset_id: str
    analysis_id: str
    status: str
    fingerprint: str
    created_at: datetime
    run: DimensionalTransformationRun


class DatabaseDryRunRecord(BaseModel):
    dry_run_id: str
    transformation_run_id: str
    analysis_id: str
    status: str
    fingerprint: str
    created_at: datetime
    run: DatabaseDryRun
