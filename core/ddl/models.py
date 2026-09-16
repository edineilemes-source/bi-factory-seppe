"""Database-independent physical plan and PostgreSQL artifact models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DDLMode(str, Enum):
    STRICT_CREATE = "STRICT_CREATE"
    SAFE_CREATE = "SAFE_CREATE"


class DDLGenerationStatus(str, Enum):
    BLOCKED = "BLOCKED"
    GENERATED_WITH_WARNINGS = "GENERATED_WITH_WARNINGS"
    GENERATED = "GENERATED"


class PhysicalSchemaStatus(str, Enum):
    GENERATED = "GENERATED"
    VALIDATED = "VALIDATED"
    EFFECTIVE = "EFFECTIVE"


class PhysicalColumn(BaseModel):
    column_id: str
    logical_name: str
    physical_name: str
    postgres_type: str
    nullable: bool = True
    role: str = "ATTRIBUTE"
    source_field_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PhysicalConstraint(BaseModel):
    name: str
    constraint_type: str
    table_name: str
    columns: list[str]
    referenced_table: str | None = None
    referenced_columns: list[str] = Field(default_factory=list)


class IndexPlan(BaseModel):
    name: str
    table_name: str
    columns: list[str]
    unique: bool = False
    reason: str


class PhysicalTable(BaseModel):
    table_id: str
    logical_name: str
    physical_name: str
    table_type: str
    columns: list[PhysicalColumn]
    primary_key: PhysicalConstraint | None = None
    unique_constraints: list[PhysicalConstraint] = Field(default_factory=list)
    check_constraints: list[PhysicalConstraint] = Field(default_factory=list)
    foreign_keys: list[PhysicalConstraint] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DDLLineage(BaseModel):
    source_document_id: str
    analysis_id: str
    prepared_dataset_id: str
    grain_definition_id: str
    dimensional_discovery_id: str
    star_schema_contract_id: str
    star_schema_contract_version: int


class PhysicalSchemaPlan(BaseModel):
    physical_schema_plan_id: str
    star_schema_contract_id: str
    star_schema_contract_version: int
    analysis_id: str
    source_document_id: str
    prepared_dataset_id: str
    target_platform: str = "POSTGRESQL"
    target_schema: str
    tables: list[PhysicalTable]
    columns: list[PhysicalColumn]
    primary_keys: list[PhysicalConstraint]
    foreign_keys: list[PhysicalConstraint]
    unique_constraints: list[PhysicalConstraint]
    check_constraints: list[PhysicalConstraint]
    indexes: list[IndexPlan]
    comments: list[str]
    warnings: list[str]
    lineage: DDLLineage
    fingerprint: str
    version: int = Field(ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: DDLGenerationStatus
    lifecycle_status: PhysicalSchemaStatus = PhysicalSchemaStatus.GENERATED


class PostgreSQLDDLArtifact(BaseModel):
    ddl_artifact_id: str
    physical_schema_plan_id: str
    postgresql_version_compatibility_target: str
    schema_name: str
    sql: str
    statement_count: int
    table_count: int
    index_count: int
    constraint_count: int
    fingerprint: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    warnings: list[str]
    lineage: DDLLineage
    version: int = Field(ge=1)
    status: DDLGenerationStatus
    validation_passed: bool = False
    human_validated: bool = False
    ready_for_dimensional_etl: bool = False
