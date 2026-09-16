"""Logical and database-independent Star Schema contracts."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from core.dimensional.models import DimensionRole, FactType
from core.grain.models import AggregationRisk, MeasureAggregationHint, QualityDependency


class ContractStatus(str, Enum):
    OBSERVED = "OBSERVED"
    NEEDS_VALIDATION = "NEEDS_VALIDATION"
    VALIDATED = "VALIDATED"


class ReadinessStatus(str, Enum):
    NOT_READY = "NOT_READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    READY_FOR_DDL = "READY_FOR_DDL"


class ContractItemStatus(str, Enum):
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    REQUIRES_VALIDATION = "REQUIRES_VALIDATION"


class LogicalDataType(str, Enum):
    TEXT = "TEXT"
    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    DATE = "DATE"
    DATETIME = "DATETIME"
    BOOLEAN = "BOOLEAN"
    UUID = "UUID"
    UNKNOWN = "UNKNOWN"


class Nullability(str, Enum):
    NULLABLE = "true"
    NOT_NULLABLE = "false"
    UNKNOWN = "unknown"


class Cardinality(str, Enum):
    MANY_TO_ONE = "MANY_TO_ONE"
    ONE_TO_ONE = "ONE_TO_ONE"
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_MANY = "MANY_TO_MANY"
    UNKNOWN = "UNKNOWN"


class AggregationType(str, Enum):
    SUM = "SUM"
    COUNT = "COUNT"
    MIN = "MIN"
    MAX = "MAX"
    AVG = "AVG"
    DISTINCT_COUNT = "DISTINCT_COUNT"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class SCDType(str, Enum):
    TYPE_0 = "TYPE_0"
    TYPE_1 = "TYPE_1"
    TYPE_2 = "TYPE_2"
    TYPE_3 = "TYPE_3"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class WarningType(str, Enum):
    MANY_TO_MANY_RELATIONSHIP = "MANY_TO_MANY_RELATIONSHIP"
    UNRESOLVED_BUSINESS_KEY = "UNRESOLVED_BUSINESS_KEY"
    UNKNOWN_SCD_STRATEGY = "UNKNOWN_SCD_STRATEGY"
    AGGREGATION_RISK = "AGGREGATION_RISK"
    QUALITY_DEPENDENCY = "QUALITY_DEPENDENCY"
    UNRESOLVED_FIELD = "UNRESOLVED_FIELD"
    NAME_COLLISION = "NAME_COLLISION"
    UNKNOWN_CARDINALITY = "UNKNOWN_CARDINALITY"
    GRAIN_MISMATCH = "GRAIN_MISMATCH"


class WarningSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    BLOCKER = "BLOCKER"


class ModelingWarning(BaseModel):
    warning_id: str
    warning_type: WarningType
    severity: WarningSeverity
    message: str
    related_ids: list[str] = Field(default_factory=list)
    blocker: bool = False


class SurrogateKeyPlan(BaseModel):
    name: str
    logical_type: LogicalDataType = LogicalDataType.INTEGER
    generated_by_system: bool = True
    source_derived: bool = False
    stable_internal_identity: bool = True


class BusinessKeyContract(BaseModel):
    fields: list[str]
    uniqueness_expected: bool = False
    uniqueness_validation_status: str = "REQUIRES_VALIDATION"
    nullability: Nullability = Nullability.UNKNOWN
    quality_dependencies: list[QualityDependency] = Field(default_factory=list)
    source_confidence: float = Field(default=0, ge=0, le=1)
    requires_validation: bool = True


class ForeignKeyContract(BaseModel):
    logical_name: str
    fact_id: str
    dimension_id: str
    fact_fk_name: str
    dimension_surrogate_key_name: str
    source_mapping_fields: list[str]
    cardinality: Cardinality = Cardinality.MANY_TO_ONE
    optionality: Nullability = Nullability.UNKNOWN
    role_name: str | None = None
    conformed_reference: bool = False
    validation_status: ContractItemStatus = ContractItemStatus.REQUIRES_VALIDATION


class MeasureContract(BaseModel):
    source_field_id: str
    logical_name: str
    prepared_type: LogicalDataType
    aggregation_type: AggregationType
    additivity: MeasureAggregationHint
    grain_compatibility: bool
    aggregation_risk: AggregationRisk | None = None
    quality_dependencies: list[QualityDependency] = Field(default_factory=list)
    nullable: Nullability = Nullability.UNKNOWN
    validation_status: ContractItemStatus = ContractItemStatus.REQUIRES_VALIDATION


class DegenerateDimensionContract(BaseModel):
    source_field_id: str
    logical_name: str
    reason: str
    quality_dependencies: list[QualityDependency] = Field(default_factory=list)
    validation_status: ContractItemStatus = ContractItemStatus.REQUIRES_VALIDATION


class FactAttributeContract(BaseModel):
    source_field_id: str
    logical_name: str
    type: LogicalDataType
    reason: str
    nullable: Nullability


class HierarchyContract(BaseModel):
    name: str
    levels: list[str]
    observed_dependency_support: list[str] = Field(default_factory=list)
    validation_status: ContractItemStatus = ContractItemStatus.REQUIRES_VALIDATION


class SCDStrategyContract(BaseModel):
    dimension_id: str
    strategy: SCDType = SCDType.UNKNOWN
    tracked_attributes: list[str] = Field(default_factory=list)
    effective_from_field_plan: str | None = None
    effective_to_field_plan: str | None = None
    current_flag_plan: str | None = None
    reason: str
    requires_validation: bool = True

    @model_validator(mode="after")
    def require_type_2_plans(self) -> "SCDStrategyContract":
        if self.strategy == SCDType.TYPE_2 and not all((
            self.effective_from_field_plan, self.effective_to_field_plan, self.current_flag_plan)):
            raise ValueError("SCD TYPE_2 exige planos effective_from, effective_to e current_flag.")
        return self


class DimensionTableContract(BaseModel):
    dimension_id: str
    logical_name: str
    human_readable_name: str
    role: DimensionRole
    business_concept_id: str | None = None
    surrogate_key_plan: SurrogateKeyPlan
    business_key_fields: BusinessKeyContract
    attributes: list[str] = Field(default_factory=list)
    hierarchies: list[HierarchyContract] = Field(default_factory=list)
    scd_strategy: SCDStrategyContract
    conformed_candidate: bool = False
    role_playing_base_dimension: str | None = None
    quality_dependencies: list[QualityDependency] = Field(default_factory=list)
    status: ContractItemStatus = ContractItemStatus.REQUIRES_VALIDATION


class RolePlayingDimensionContract(BaseModel):
    base_dimension_id: str
    role_name: str
    source_field_id: str
    fact_fk_name: str
    relationship_name: str


class RelationshipContract(BaseModel):
    relationship_id: str
    source_table: str
    target_table: str
    relationship_type: str = "FACT_TO_DIMENSION"
    source_fields: list[str]
    target_fields: list[str]
    fact_fk: str
    dimension_key: str
    cardinality: Cardinality
    optionality: Nullability
    role_name: str | None = None
    evidence: list[str] = Field(default_factory=list)
    validation_status: ContractItemStatus = ContractItemStatus.REQUIRES_VALIDATION


class BridgeTableCandidate(BaseModel):
    bridge_id: str
    left_entity: str
    right_entity: str
    reason: str
    cardinality_evidence: list[str]
    requires_validation: bool = True


class ConformedDimensionContractCandidate(BaseModel):
    dimension_id: str
    business_concept_id: str | None = None
    business_key: BusinessKeyContract
    reuse_scope: str = "MULTIPLE_FACTS_OR_DATASETS"
    compatibility_requirements: list[str] = Field(default_factory=list)
    status: ContractItemStatus = ContractItemStatus.REQUIRES_VALIDATION


class FactTableContract(BaseModel):
    fact_id: str
    logical_name: str
    human_readable_name: str
    fact_type: FactType
    process: str | None = None
    event: str | None = None
    grain_description: str
    grain_fields: list[str]
    surrogate_key_plan: SurrogateKeyPlan | None = None
    degenerate_identifiers: list[DegenerateDimensionContract] = Field(default_factory=list)
    measures: list[MeasureContract] = Field(default_factory=list)
    foreign_keys: list[ForeignKeyContract] = Field(default_factory=list)
    fact_attributes: list[FactAttributeContract] = Field(default_factory=list)
    quality_dependencies: list[QualityDependency] = Field(default_factory=list)
    aggregation_risks: list[AggregationRisk] = Field(default_factory=list)
    status: ContractItemStatus = ContractItemStatus.REQUIRES_VALIDATION


class StarSchemaLineage(BaseModel):
    source_document_id: str
    analysis_id: str
    prepared_dataset_id: str
    prepared_dataset_version: int
    prepared_dataset_fingerprint: str
    grain_definition_id: str
    grain_version: int
    dimensional_discovery_id: str
    dimensional_discovery_version: int


class StarSchemaContract(BaseModel):
    contract_id: str
    analysis_id: str
    source_document_id: str
    prepared_dataset_id: str
    prepared_dataset_version: int
    grain_definition_id: str
    grain_version: int
    dimensional_discovery_id: str
    dimensional_discovery_version: int
    version: int = Field(ge=1)
    status: ContractStatus
    schema_name_suggestion: str
    fact_tables: list[FactTableContract]
    dimension_tables: list[DimensionTableContract]
    relationships: list[RelationshipContract]
    role_playing_relationships: list[RolePlayingDimensionContract] = Field(default_factory=list)
    conformed_dimension_candidates: list[ConformedDimensionContractCandidate] = Field(default_factory=list)
    bridge_candidates: list[BridgeTableCandidate] = Field(default_factory=list)
    warnings: list[ModelingWarning] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)
    ignored_fields: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    lineage: StarSchemaLineage
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    validated_at: datetime | None = None

    @model_validator(mode="after")
    def validate_references(self) -> "StarSchemaContract":
        fact_ids = {item.fact_id for item in self.fact_tables}
        dimension_ids = {item.dimension_id for item in self.dimension_tables}
        names = [item.logical_name for item in self.fact_tables + self.dimension_tables]
        if len(names) != len(set(names)):
            raise ValueError("Nomes lógicos devem ser únicos.")
        if any(not fact.grain_fields and not fact.grain_description for fact in self.fact_tables):
            raise ValueError("Toda fato deve possuir grão.")
        if any(rel.source_table not in fact_ids or rel.target_table not in dimension_ids
               for rel in self.relationships):
            raise ValueError("Relacionamento referencia fato ou dimensão inexistente.")
        if any(role.base_dimension_id not in dimension_ids for role in self.role_playing_relationships):
            raise ValueError("Role-playing relationship sem dimensão base válida.")
        measure_fields = {measure.source_field_id for fact in self.fact_tables for measure in fact.measures}
        business_fields = {field for dimension in self.dimension_tables
                           for field in dimension.business_key_fields.fields}
        if measure_fields & business_fields:
            raise ValueError("Uma medida não pode ser business key dimensional.")
        if any(field.casefold() == "source_row_id" or field.casefold().endswith("::source_row_id")
               for field in business_fields):
            raise ValueError("Technical key não pode ser business key.")
        degenerate_fields = {item.source_field_id for fact in self.fact_tables
                             for item in fact.degenerate_identifiers}
        if degenerate_fields & business_fields:
            raise ValueError("Identificador degenerado deve permanecer na fato.")
        return self


class ValidationResult(BaseModel):
    rule: str
    passed: bool
    severity: WarningSeverity = WarningSeverity.ERROR
    message: str


class FieldCoverage(BaseModel):
    total_fields: int
    tracked_fields: int
    percentage: float = Field(ge=0, le=100)
    classifications: dict[str, int] = Field(default_factory=dict)


class StarSchemaContractReport(BaseModel):
    report_id: str
    contract: StarSchemaContract
    validation_results: list[ValidationResult]
    warnings: list[ModelingWarning]
    field_coverage: FieldCoverage
    lineage: StarSchemaLineage
    readiness: ReadinessStatus = ReadinessStatus.NOT_READY
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = Field(ge=1)
    max_relationships: int
    max_bridge_candidates: int
    max_warnings: int


class ValidatedStarSchemaContract(BaseModel):
    validation_id: str
    report_id: str
    observed_contract_id: str
    contract: StarSchemaContract
    readiness: ReadinessStatus
    validated_by: str = "user"
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = Field(ge=1)
