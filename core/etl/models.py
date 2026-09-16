"""Contracts emitted by the dimensional ETL planning engine."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ETLPlanStatus(str, Enum):
    BLOCKED = "BLOCKED"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    READY_FOR_DRY_RUN = "READY_FOR_DRY_RUN"


class MappingRole(str, Enum):
    DIRECT = "DIRECT"
    DIMENSION_LOOKUP = "DIMENSION_LOOKUP"
    SURROGATE_KEY_LOOKUP = "SURROGATE_KEY_LOOKUP"
    DERIVED = "DERIVED"
    DEFAULT_VALUE = "DEFAULT_VALUE"
    UNKNOWN_MEMBER = "UNKNOWN_MEMBER"
    IGNORED = "IGNORED"
    UNRESOLVED = "UNRESOLVED"


class DimensionLoadType(str, Enum):
    FULL_REBUILD = "FULL_REBUILD"
    UPSERT = "UPSERT"
    INCREMENTAL_INSERT = "INCREMENTAL_INSERT"
    SCD_PROCESS = "SCD_PROCESS"
    UNKNOWN = "UNKNOWN"


class MissingLookupAction(str, Enum):
    INSERT_DIMENSION_MEMBER = "INSERT_DIMENSION_MEMBER"
    USE_UNKNOWN_MEMBER = "USE_UNKNOWN_MEMBER"
    REJECT_ROW = "REJECT_ROW"
    DEFER = "DEFER"
    BLOCK = "BLOCK"


class RejectionAction(str, Enum):
    REJECT = "REJECT"
    QUARANTINE = "QUARANTINE"
    LOAD_WITH_WARNING = "LOAD_WITH_WARNING"
    USE_UNKNOWN_MEMBER = "USE_UNKNOWN_MEMBER"
    BLOCK_BATCH = "BLOCK_BATCH"


class IncrementalLoadStrategy(str, Enum):
    FULL = "FULL"
    APPEND = "APPEND"
    UPSERT = "UPSERT"
    CHANGE_DETECTION = "CHANGE_DETECTION"
    UNKNOWN = "UNKNOWN"


class ReconciliationCapability(str, Enum):
    RECONCILABLE = "RECONCILABLE"
    NOT_RECONCILABLE = "NOT_RECONCILABLE"
    REQUIRES_VALIDATION = "REQUIRES_VALIDATION"


class ETLSourceContract(BaseModel):
    prepared_dataset_id: str
    fingerprint: str
    row_count: int
    schema_fields: list[dict[str, Any]]
    effective_fields: list[str]
    source_row_id: str = "source_row_id"
    quality_gate: str
    unresolved_issues: list[str]
    readiness: str

    @property
    def schema(self) -> list[dict[str, Any]]:
        return self.schema_fields


class FieldMapping(BaseModel):
    source_field_id: str | None
    prepared_field_name: str | None
    effective_semantic_role: str | None = None
    target_table: str | None
    target_column: str | None
    mapping_role: MappingRole
    transformation: str
    source_type: str | None
    target_type: str | None
    nullable: bool
    required_for_load: bool
    lookup_dimension: str | None = None
    lineage: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ColumnTransformationPlan(BaseModel):
    target_table: str
    target_column: str
    source_field_id: str | None
    effective_value: str
    transformation: str
    lookup: str | None = None
    default: str | None = None
    null_policy: str
    validations: list[str] = Field(default_factory=list)


class DerivedFieldRule(BaseModel):
    rule_id: str
    reason: str
    inputs: list[str]
    output: str


class UnknownMemberPlan(BaseModel):
    enabled: bool
    reserved_key: int | str
    business_key_value: str
    description: str
    applicable_dimensions: list[str]
    reason: str


class SurrogateKeyResolutionPlan(BaseModel):
    resolution_id: str
    fact_id: str
    dimension_id: str
    target_fact_column: str
    dimension_table: str
    dimension_surrogate_key: str
    source_business_key_fields: list[str]
    normalization: list[str]
    found_action: str = "USE_RESOLVED_SURROGATE_KEY"
    missing_action: MissingLookupAction
    optional: bool


class SCDType1LoadPlan(BaseModel):
    dimension_id: str
    business_key: list[str]
    attributes_to_update: list[str]
    comparison_fields: list[str]
    update_policy: str = "UPDATE_CHANGED_ATTRIBUTES"
    null_handling: str = "FOLLOW_VALIDATED_NULLABILITY"
    audit_fields: list[str] = Field(default_factory=list)


class SCDType2LoadPlan(BaseModel):
    dimension_id: str
    business_key: list[str]
    tracked_attributes: list[str]
    effective_from: str
    effective_to: str
    current_flag: str
    change_detection_fields: list[str]
    close_current_row_action: str = "CLOSE_CURRENT_VERSION_DECLARATIVELY"
    insert_new_version_action: str = "INSERT_NEW_VERSION_DECLARATIVELY"
    timestamp_source: str = "PREPARED_DATASET_CREATED_AT"
    audit_fields: list[str] = Field(default_factory=list)


class DimensionLoadPlan(BaseModel):
    dimension_id: str
    target_table: str
    business_key: list[str]
    surrogate_key: str
    attributes: list[str]
    source_fields: list[str]
    deduplication_strategy: str
    scd_strategy: str
    unknown_member_strategy: str
    load_type: DimensionLoadType
    lookup_strategy: str
    quality_dependencies: list[str]
    preconditions: list[str]
    postconditions: list[str]
    execution_rank: int = 0
    required_date_min: str | None = None
    required_date_max: str | None = None


class FactLoadPlan(BaseModel):
    fact_id: str
    target_table: str
    fact_type: str
    grain: list[str]
    source_fields: list[str]
    measure_mappings: list[FieldMapping]
    degenerate_dimension_mappings: list[FieldMapping]
    fact_attribute_mappings: list[FieldMapping]
    surrogate_key_lookups: list[str]
    required_dimensions: list[str]
    optional_dimensions: list[str]
    duplicate_policy: str
    rejection_policy: str
    aggregation_risks: list[str]
    preconditions: list[str]
    postconditions: list[str]
    execution_rank: int = 0


class BridgeLoadPlan(BaseModel):
    bridge_id: str
    bridge_table: str
    left_dimension: str
    right_dimension: str
    business_mappings: list[FieldMapping]
    surrogate_lookups: list[str]
    deduplication_key: list[str]
    weight_allocation_field: str | None = None
    load_strategy: str = "INSERT_DISTINCT_VALIDATED_RELATIONSHIPS"
    execution_rank: int = 0


class RejectedRowContract(BaseModel):
    fields: list[str] = Field(default_factory=lambda: [
        "source_row_id", "reason_code", "field", "source_value", "effective_value",
        "severity", "action", "retryable", "lineage"])


class RejectionPolicy(BaseModel):
    default_action: RejectionAction
    required_key_action: RejectionAction
    invalid_type_action: RejectionAction
    no_silent_discard: bool = True
    rejected_row_contract: RejectedRowContract = Field(default_factory=RejectedRowContract)
    quarantine_schema_plan: str = "FUTURE_QUARANTINE_DATASET"
    quarantine_fields: list[str] = Field(default_factory=lambda: ["source_row_id", "reason_code", "field"])


class MeasureReconciliation(BaseModel):
    source_field_id: str
    target_table: str
    target_column: str
    status: ReconciliationCapability
    comparison: str | None = None
    reason: str


class ReconciliationPlan(BaseModel):
    source_row_count: int
    prepared_row_count: int
    expected_fact_rows: dict[str, str]
    expected_dimension_member_counts: dict[str, int | None]
    measure_reconciliations: list[MeasureReconciliation]
    rejected_row_policy: str
    tolerance_rules: list[str]
    aggregation_risk_notes: list[str]
    status: str


class IdempotencyPlan(BaseModel):
    strategy: str
    load_batch_id_planned: bool = True
    duplicate_prevention: str


class RestartPlan(BaseModel):
    checkpoint_strategy: str
    completed_steps: list[str] = Field(default_factory=list)
    failed_step: str | None = None
    replay_policy: str
    safe_restart_point: str


class ETLRunAuditPlan(BaseModel):
    fields: list[str] = Field(default_factory=lambda: [
        "run_id", "plan_id", "dataset_fingerprint", "ddl_fingerprint", "started_at",
        "finished_at", "status", "source_rows", "prepared_rows", "loaded_dimension_rows",
        "loaded_fact_rows", "rejected_rows", "warning_count", "reconciliation_status"])


class ETLLineage(BaseModel):
    source_document_id: str
    analysis_id: str
    prepared_dataset_id: str
    prepared_dataset_version: int
    star_schema_contract_id: str
    physical_schema_plan_id: str
    ddl_artifact_id: str


class DimensionalETLPlan(BaseModel):
    etl_plan_id: str
    analysis_id: str
    source_document_id: str
    prepared_dataset_id: str
    prepared_dataset_version: int
    physical_schema_plan_id: str
    ddl_artifact_id: str
    star_schema_contract_id: str
    version: int = Field(ge=1)
    status: ETLPlanStatus
    source_contract: ETLSourceContract
    field_mappings: list[FieldMapping]
    column_transformation_plans: list[ColumnTransformationPlan]
    derived_field_rules: list[DerivedFieldRule]
    dimension_load_plans: list[DimensionLoadPlan]
    fact_load_plans: list[FactLoadPlan]
    bridge_load_plans: list[BridgeLoadPlan]
    surrogate_key_resolution_plans: list[SurrogateKeyResolutionPlan]
    scd_plans: list[SCDType1LoadPlan | SCDType2LoadPlan]
    unknown_member_plans: list[UnknownMemberPlan]
    rejection_policy: RejectionPolicy
    reconciliation_plan: ReconciliationPlan
    idempotency_plan: IdempotencyPlan
    restart_plan: RestartPlan
    incremental_strategy: IncrementalLoadStrategy
    load_audit_plan: ETLRunAuditPlan
    execution_order: list[str]
    dependencies: dict[str, list[str]]
    validation_rules: list[dict[str, Any]]
    warnings: list[str]
    blockers: list[str]
    target_coverage_percentage: float
    source_coverage_percentage: float
    lineage: ETLLineage
    fingerprint: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ValidatedDimensionalETLPlan(BaseModel):
    validation_id: str
    etl_plan_id: str
    plan: DimensionalETLPlan
    validated_by: str = "user"
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = Field(ge=1)
