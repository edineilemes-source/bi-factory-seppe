"""Auditable contracts for database dry runs (credentials are intentionally excluded)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, SecretStr


class CleanupPolicy(str, Enum):
    ALWAYS = "ALWAYS"
    ON_SUCCESS = "ON_SUCCESS"
    NEVER = "NEVER"


class DatabaseTargetType(str, Enum):
    POSTGRESQL_LOCAL = "POSTGRESQL_LOCAL"
    IN_MEMORY = "IN_MEMORY"
    SUPABASE_POSTGRESQL = "SUPABASE_POSTGRESQL"  # reserved, deliberately unsupported


class LoadStrategy(str, Enum):
    BATCH_INSERT = "BATCH_INSERT"
    COPY = "COPY"
    UNKNOWN = "UNKNOWN"


class TransactionPolicy(str, Enum):
    ALL_OR_NOTHING = "ALL_OR_NOTHING"
    STEP_TRANSACTION = "STEP_TRANSACTION"
    BATCH_TRANSACTION = "BATCH_TRANSACTION"


class DatabaseDryRunStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    PROVISIONING = "PROVISIONING"
    DDL_RUNNING = "DDL_RUNNING"
    LOADING_DIMENSIONS = "LOADING_DIMENSIONS"
    LOADING_BRIDGES = "LOADING_BRIDGES"
    LOADING_FACTS = "LOADING_FACTS"
    VALIDATING = "VALIDATING"
    RECONCILING = "RECONCILING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    BLOCKED = "BLOCKED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"
    CLEANED = "CLEANED"
    SKIPPED_ENVIRONMENT = "SKIPPED_ENVIRONMENT"


class DatabaseDryRunReadiness(str, Enum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    FAIL = "FAIL"


class DatabaseDryRunConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    database: str = "postgres"
    user: str = "postgres"
    password: SecretStr | None = Field(default=None, exclude=True, repr=False)
    password_env: str = "PGPASSWORD"
    test_schema_prefix: str = "dryrun_"
    cleanup_policy: CleanupPolicy = CleanupPolicy.ALWAYS
    statement_timeout: int = 30_000
    batch_size: int = 1_000
    ssl_mode: str = "prefer"
    target_type: DatabaseTargetType = DatabaseTargetType.POSTGRESQL_LOCAL
    load_strategy: LoadStrategy = LoadStrategy.BATCH_INSERT
    transaction_policy: TransactionPolicy = TransactionPolicy.STEP_TRANSACTION

    def safe_target(self) -> dict[str, Any]:
        return {"host": self.host, "port": self.port, "database": self.database,
                "user": self.user, "ssl_mode": self.ssl_mode, "target_type": self.target_type.value,
                "password": "***" if self.password else f"env:{self.password_env}"}


class DatabaseTransactionPlan(BaseModel):
    policy: TransactionPolicy = TransactionPolicy.STEP_TRANSACTION
    checkpoint_after_each_step: bool = True


class DDLExecutionResult(BaseModel):
    statement_count: int = 0
    successful_statements: int = 0
    success: bool = False
    execution_time_ms: float = 0
    error_statement: str | None = None
    postgres_error_code: str | None = None
    error_message: str | None = None


class LoadResult(BaseModel):
    object_id: str
    target_table: str
    attempted_rows: int
    loaded_rows: int
    rejected_rows: int = 0
    status: str = "PASS"
    execution_time_ms: float = 0


class PhysicalSurrogateKeyMap(BaseModel):
    dimension_id: str
    business_key: list[Any]
    staging_surrogate_key: int | str
    physical_surrogate_key: int | str
    dry_run_id: str
    status: str = "RESOLVED"


class SchemaDifference(BaseModel):
    difference_type: str
    object_name: str
    expected: Any = None
    actual: Any = None


class SchemaValidationResult(BaseModel):
    expected_table_count: int
    actual_table_count: int
    differences: list[SchemaDifference] = Field(default_factory=list)
    status: str = "PASS"


class ValidationCheck(BaseModel):
    name: str
    checked: int = 0
    failures: int = 0
    resolution_rate: float | None = None
    details: list[str] = Field(default_factory=list)
    status: str = "PASS"


class DatabaseReconciliationReport(BaseModel):
    prepared_rows: int
    staged_rows: int
    loaded_rows: int
    rejected_rows: int
    quarantined_rows: int
    dimension_counts: dict[str, dict[str, int]]
    fact_counts: dict[str, dict[str, int]]
    bridge_counts: dict[str, dict[str, int]]
    measure_reconciliations: list[dict[str, Any]]
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    status: str = "PASS"
    fingerprint: str


class DatabaseValidationReport(BaseModel):
    schema_validation: SchemaValidationResult
    pk_validation: ValidationCheck
    fk_validation: ValidationCheck
    unique_validation: ValidationCheck
    nullability_validation: ValidationCheck
    type_roundtrip: ValidationCheck
    precision_roundtrip: ValidationCheck
    row_count_validation: ValidationCheck
    dimension_count_validation: ValidationCheck
    fact_count_validation: ValidationCheck
    reconciliation: DatabaseReconciliationReport
    idempotency: ValidationCheck
    restartability: ValidationCheck
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    status: DatabaseDryRunReadiness = DatabaseDryRunReadiness.FAIL


class CleanupResult(BaseModel):
    attempted: bool = False
    schema_dropped: bool = False
    safety_guard_passed: bool = False
    status: str = "NOT_REQUESTED"
    message: str | None = None


class DatabaseDryRunLineage(BaseModel):
    source_document_id: str
    analysis_id: str
    prepared_dataset_id: str
    transformation_run_id: str
    etl_plan_id: str
    ddl_artifact_id: str
    physical_schema_plan_id: str


class DatabaseDryRun(BaseModel):
    dry_run_id: str
    transformation_run_id: str
    ddl_artifact_id: str
    physical_schema_plan_id: str
    target_config_fingerprint: str
    test_schema: str
    status: DatabaseDryRunStatus
    started_at: datetime
    finished_at: datetime | None = None
    ddl_result: DDLExecutionResult
    dimension_load_results: list[LoadResult] = Field(default_factory=list)
    bridge_load_results: list[LoadResult] = Field(default_factory=list)
    fact_load_results: list[LoadResult] = Field(default_factory=list)
    physical_surrogate_key_maps: list[PhysicalSurrogateKeyMap] = Field(default_factory=list)
    validation_results: DatabaseValidationReport | None = None
    reconciliation_results: DatabaseReconciliationReport | None = None
    rollback_tests: ValidationCheck = Field(default_factory=lambda: ValidationCheck(name="ROLLBACK"))
    idempotency_results: ValidationCheck = Field(default_factory=lambda: ValidationCheck(name="IDEMPOTENCY"))
    cleanup_result: CleanupResult = Field(default_factory=CleanupResult)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    lineage: DatabaseDryRunLineage
    readiness: DatabaseDryRunReadiness = DatabaseDryRunReadiness.FAIL
    ready_for_controlled_deployment: bool = False
    fingerprint: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
