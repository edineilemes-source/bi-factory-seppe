"""Pure transformation from an Effective Star Schema Contract to PostgreSQL DDL."""

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from core.ddl.identifiers import PostgresIdentifierNormalizer
from core.ddl.models import (
    DDLGenerationStatus, DDLLineage, DDLMode, IndexPlan, PhysicalColumn,
    PhysicalConstraint, PhysicalSchemaPlan, PhysicalTable, PostgreSQLDDLArtifact,
)
from core.ddl.types import PostgresTypeMapper
from core.ddl.validation import validate_postgresql_ddl
from core.star.models import (
    ContractItemStatus, ContractStatus, LogicalDataType, Nullability, ReadinessStatus,
    SCDType, StarSchemaContract, ValidatedStarSchemaContract,
)


@dataclass(frozen=True)
class DDLGeneratorConfig:
    target_schema: str = "bi"
    ddl_mode: DDLMode = DDLMode.STRICT_CREATE
    postgresql_version_target: str = "14+"
    unknown_type_policy: str = "TEXT_WITH_WARNING"
    numeric_precision_margin: int = 2
    generate_fk_indexes: bool = True
    generate_comments: bool = True


def _stable_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _not_null(nullable: Nullability) -> bool:
    return nullable == Nullability.NOT_NULLABLE


def _contract_and_readiness(value: StarSchemaContract | ValidatedStarSchemaContract) -> tuple[StarSchemaContract, ReadinessStatus]:
    if isinstance(value, ValidatedStarSchemaContract):
        return value.contract, value.readiness
    # An Effective contract is necessarily the validated output. Blockers still
    # protect callers that bypass the effective resolver.
    readiness = (ReadinessStatus.NOT_READY if value.status != ContractStatus.VALIDATED
                 or any(item.blocker for item in value.warnings) else ReadinessStatus.READY_FOR_DDL)
    return value, readiness


class _Planner:
    def __init__(self, contract: StarSchemaContract, config: DDLGeneratorConfig):
        self.contract, self.config = contract, config
        self.names = PostgresIdentifierNormalizer()
        self.mapper = PostgresTypeMapper(unknown_policy=config.unknown_type_policy,
                                         numeric_precision_margin=config.numeric_precision_margin)
        self.schema = self.names.normalize(config.target_schema, scope="schema")
        self.warnings = [warning.message for warning in contract.warnings if not warning.blocker]
        self.table_names: dict[str, str] = {}

    def column(self, table_id: str, logical_name: str, logical_type: LogicalDataType,
               nullable: Nullability, role: str, source_field_id: str | None = None) -> PhysicalColumn:
        physical = self.names.normalize(logical_name, scope=f"column:{table_id}")
        postgres_type, metadata, warning = self.mapper.map(logical_type)
        if warning:
            self.warnings.append(f"{self.table_names.get(table_id, table_id)}.{physical}: {warning}")
        return PhysicalColumn(column_id=f"{table_id}:{physical}", logical_name=logical_name,
                              physical_name=physical, postgres_type=postgres_type,
                              nullable=not _not_null(nullable), role=role,
                              source_field_id=source_field_id, metadata=metadata)

    def constraint(self, kind: str, table: str, columns: list[str], *, referenced_table: str | None = None,
                   referenced_columns: list[str] | None = None) -> PhysicalConstraint:
        raw = f"{kind.lower()}_{table}_{'_'.join(columns)}"
        name = self.names.normalize(raw, scope="constraints")
        return PhysicalConstraint(name=name, constraint_type=kind, table_name=table, columns=columns,
                                  referenced_table=referenced_table,
                                  referenced_columns=referenced_columns or [])

    def build(self) -> tuple[list[PhysicalTable], list[IndexPlan], list[str]]:
        dimensions = sorted(self.contract.dimension_tables, key=lambda item: (item.logical_name, item.dimension_id))
        facts = sorted(self.contract.fact_tables, key=lambda item: (item.logical_name, item.fact_id))
        bridges = sorted((item for item in self.contract.bridge_candidates if not item.requires_validation),
                         key=lambda item: item.bridge_id)
        for item in [*dimensions, *bridges, *facts]:
            item_id = (getattr(item, "dimension_id", None) or getattr(item, "bridge_id", None)
                       or getattr(item, "fact_id", ""))
            logical = getattr(item, "logical_name", None) or getattr(item, "bridge_id", item_id)
            self.table_names[item_id] = self.names.normalize(logical, scope="tables")

        tables: list[PhysicalTable] = []
        indexes: list[IndexPlan] = []
        dimension_keys: dict[str, str] = {}
        for dim in dimensions:
            table = self.table_names[dim.dimension_id]
            sk = self.column(dim.dimension_id, dim.surrogate_key_plan.name, LogicalDataType.INTEGER,
                             Nullability.NOT_NULLABLE, "SURROGATE_KEY")
            sk.postgres_type = "BIGINT GENERATED BY DEFAULT AS IDENTITY"
            columns = [sk]
            logical_to_physical = {dim.surrogate_key_plan.name: sk.physical_name}
            for field in list(dict.fromkeys(dim.business_key_fields.fields + dim.attributes)):
                if field == dim.surrogate_key_plan.name:
                    continue
                role = "BUSINESS_KEY" if field in dim.business_key_fields.fields else "ATTRIBUTE"
                nullable = dim.business_key_fields.nullability if role == "BUSINESS_KEY" else Nullability.UNKNOWN
                col = self.column(dim.dimension_id, field, LogicalDataType.UNKNOWN, nullable, role, field)
                columns.append(col); logical_to_physical[field] = col.physical_name
            scd = dim.scd_strategy
            if scd.strategy == SCDType.TYPE_2 and not scd.requires_validation:
                for logical, dtype, nullable in (
                    (scd.effective_from_field_plan, LogicalDataType.DATETIME, Nullability.NOT_NULLABLE),
                    (scd.effective_to_field_plan, LogicalDataType.DATETIME, Nullability.NULLABLE),
                    (scd.current_flag_plan, LogicalDataType.BOOLEAN, Nullability.NOT_NULLABLE)):
                    if logical and logical not in logical_to_physical:
                        col = self.column(dim.dimension_id, logical, dtype, nullable, "SCD_TYPE_2")
                        columns.append(col); logical_to_physical[logical] = col.physical_name
            elif scd.strategy == SCDType.UNKNOWN:
                self.warnings.append(f"{table}: estratégia SCD UNKNOWN; nenhuma coluna histórica foi criada.")
            pk = self.constraint("PRIMARY_KEY", table, [sk.physical_name])
            uniques = []
            bk = dim.business_key_fields
            bk_cols = [logical_to_physical[field] for field in bk.fields if field in logical_to_physical]
            uniqueness_valid = bk.uniqueness_expected and bk.uniqueness_validation_status.upper().startswith("VALIDATED")
            if uniqueness_valid and not any(getattr(dep, "blocking", False) for dep in bk.quality_dependencies):
                uniques.append(self.constraint("UNIQUE", table, bk_cols))
            elif bk.uniqueness_expected:
                self.warnings.append(f"{table}: UNIQUE da business key não gerada sem validação suficiente.")
            if scd.strategy == SCDType.TYPE_2 and not scd.requires_validation and bk_cols and scd.current_flag_plan:
                current = logical_to_physical[scd.current_flag_plan]
                idx_name = self.names.normalize(f"idx_{table}_{'_'.join(bk_cols)}_{current}", scope="indexes")
                indexes.append(IndexPlan(name=idx_name, table_name=table, columns=bk_cols + [current],
                                         reason="SCD Type 2 current-row lookup"))
            dimension_keys[dim.dimension_id] = sk.physical_name
            tables.append(PhysicalTable(table_id=dim.dimension_id, logical_name=dim.logical_name,
                                        physical_name=table, table_type="DIMENSION", columns=columns,
                                        primary_key=pk, unique_constraints=uniques,
                                        metadata={"scd_strategy": scd.strategy.value,
                                                  "business_key": bk.fields,
                                                  "quality_dependencies": [str(x) for x in dim.quality_dependencies]}))

        for bridge in bridges:
            table = self.table_names[bridge.bridge_id]
            columns, fks = [], []
            for side, entity in (("left", bridge.left_entity), ("right", bridge.right_entity)):
                col = self.column(bridge.bridge_id, f"{side}_sk", LogicalDataType.INTEGER,
                                  Nullability.NOT_NULLABLE, "FOREIGN_KEY")
                columns.append(col)
                if entity in self.table_names and entity in dimension_keys:
                    fks.append(self.constraint("FOREIGN_KEY", table, [col.physical_name],
                                               referenced_table=self.table_names[entity],
                                               referenced_columns=[dimension_keys[entity]]))
            pk = self.constraint("PRIMARY_KEY", table, [column.physical_name for column in columns])
            tables.append(PhysicalTable(table_id=bridge.bridge_id, logical_name=bridge.bridge_id,
                                        physical_name=table, table_type="BRIDGE", columns=columns,
                                        primary_key=pk, foreign_keys=fks, metadata={"reason": bridge.reason}))

        for fact in facts:
            table = self.table_names[fact.fact_id]
            columns: list[PhysicalColumn] = []
            logical_to_physical: dict[str, str] = {}
            pk = None
            if fact.surrogate_key_plan:
                col = self.column(fact.fact_id, fact.surrogate_key_plan.name, LogicalDataType.INTEGER,
                                  Nullability.NOT_NULLABLE, "SURROGATE_KEY")
                col.postgres_type = "BIGINT GENERATED BY DEFAULT AS IDENTITY"
                columns.append(col); logical_to_physical[col.logical_name] = col.physical_name
                pk = self.constraint("PRIMARY_KEY", table, [col.physical_name])
            fks: list[PhysicalConstraint] = []
            for fk in sorted((item for item in fact.foreign_keys
                              if item.validation_status == ContractItemStatus.VALIDATED),
                             key=lambda item: (item.fact_fk_name, item.dimension_id)):
                col = self.column(fact.fact_id, fk.fact_fk_name, LogicalDataType.INTEGER,
                                  fk.optionality, "FOREIGN_KEY")
                columns.append(col); logical_to_physical[fk.fact_fk_name] = col.physical_name
                if fk.dimension_id in dimension_keys:
                    constraint = self.constraint("FOREIGN_KEY", table, [col.physical_name],
                                                 referenced_table=self.table_names[fk.dimension_id],
                                                 referenced_columns=[dimension_keys[fk.dimension_id]])
                    fks.append(constraint)
                    if self.config.generate_fk_indexes:
                        name = self.names.normalize(f"idx_{table}_{col.physical_name}", scope="indexes")
                        indexes.append(IndexPlan(name=name, table_name=table, columns=[col.physical_name],
                                                 reason="Fact foreign-key lookup"))
            for item in fact.degenerate_identifiers:
                if item.validation_status == ContractItemStatus.VALIDATED and item.logical_name not in logical_to_physical:
                    col = self.column(fact.fact_id, item.logical_name, LogicalDataType.UNKNOWN,
                                      Nullability.UNKNOWN, "DEGENERATE_DIMENSION", item.source_field_id)
                    columns.append(col); logical_to_physical[item.logical_name] = col.physical_name
            for item in fact.fact_attributes:
                if item.logical_name not in logical_to_physical:
                    col = self.column(fact.fact_id, item.logical_name, item.type, item.nullable,
                                      "FACT_ATTRIBUTE", item.source_field_id)
                    columns.append(col); logical_to_physical[item.logical_name] = col.physical_name
            for item in fact.measures:
                if item.validation_status == ContractItemStatus.VALIDATED and item.logical_name not in logical_to_physical:
                    col = self.column(fact.fact_id, item.logical_name, item.prepared_type, item.nullable,
                                      "MEASURE", item.source_field_id)
                    col.metadata.update({"aggregation_type": item.aggregation_type.value,
                                         "aggregation_risk": str(item.aggregation_risk) if item.aggregation_risk else None,
                                         "quality_dependencies": [str(x) for x in item.quality_dependencies]})
                    columns.append(col); logical_to_physical[item.logical_name] = col.physical_name
            tables.append(PhysicalTable(table_id=fact.fact_id, logical_name=fact.logical_name,
                                        physical_name=table, table_type="FACT", columns=columns,
                                        primary_key=pk, foreign_keys=fks,
                                        metadata={"grain": fact.grain_description,
                                                  "grain_fields": fact.grain_fields,
                                                  "aggregation_risks": [str(x) for x in fact.aggregation_risks],
                                                  "quality_dependencies": [str(x) for x in fact.quality_dependencies]}))
        comments = self._comments(tables) if self.config.generate_comments else []
        return tables, indexes, comments

    def _comments(self, tables: Iterable[PhysicalTable]) -> list[str]:
        comments = []
        for table in tables:
            if table.table_type == "FACT":
                comments.append(f"COMMENT ON TABLE {self.schema}.{table.physical_name} IS {_sql_literal('Grain: ' + table.metadata['grain'])}")
            elif table.table_type == "DIMENSION":
                comments.append(f"COMMENT ON TABLE {self.schema}.{table.physical_name} IS {_sql_literal('SCD: ' + table.metadata['scd_strategy'])}")
            for column in table.columns:
                notes = []
                if column.role == "BUSINESS_KEY": notes.append("Business key")
                if column.role == "MEASURE": notes.append(f"Aggregation: {column.metadata.get('aggregation_type')}")
                if column.metadata.get("aggregation_risk"): notes.append("Aggregation risk preserved in artifact metadata")
                if notes:
                    comments.append(f"COMMENT ON COLUMN {self.schema}.{table.physical_name}.{column.physical_name} IS {_sql_literal('; '.join(notes))}")
        return comments


def _render_sql(schema: str, tables: list[PhysicalTable], indexes: list[IndexPlan], comments: list[str],
                mode: DDLMode) -> str:
    safe = " IF NOT EXISTS" if mode == DDLMode.SAFE_CREATE else ""
    statements = [f"CREATE SCHEMA{safe} {schema}"]
    for table in tables:
        definitions = []
        for column in table.columns:
            definitions.append(f"    {column.physical_name} {column.postgres_type}" + (" NOT NULL" if not column.nullable else ""))
        constraints = ([table.primary_key] if table.primary_key else []) + table.unique_constraints + table.check_constraints + table.foreign_keys
        for constraint in constraints:
            prefix = f"    CONSTRAINT {constraint.name} "
            cols = ", ".join(constraint.columns)
            if constraint.constraint_type == "PRIMARY_KEY": definition = f"PRIMARY KEY ({cols})"
            elif constraint.constraint_type == "UNIQUE": definition = f"UNIQUE ({cols})"
            elif constraint.constraint_type == "FOREIGN_KEY":
                definition = (f"FOREIGN KEY ({cols}) REFERENCES {schema}.{constraint.referenced_table}"
                              f" ({', '.join(constraint.referenced_columns)})")
            else: definition = f"CHECK ({constraint.columns[0]})"
            definitions.append(prefix + definition)
        statements.append(f"CREATE TABLE{safe} {schema}.{table.physical_name} (\n" + ",\n".join(definitions) + "\n)")
    for index in indexes:
        statements.append(f"CREATE {'UNIQUE ' if index.unique else ''}INDEX{safe} {index.name} ON {schema}.{index.table_name} ({', '.join(index.columns)})")
    statements.extend(comments)
    return ";\n\n".join(statements) + ";\n"


def generate_postgresql_ddl(
    effective_contract: StarSchemaContract | ValidatedStarSchemaContract, *,
    config: DDLGeneratorConfig | None = None, version: int = 1,
) -> tuple[PhysicalSchemaPlan, PostgreSQLDDLArtifact]:
    """Generate but never execute a complete PostgreSQL schema."""
    config = config or DDLGeneratorConfig()
    contract, readiness = _contract_and_readiness(effective_contract)
    blockers = [warning.message for warning in contract.warnings if warning.blocker]
    if readiness != ReadinessStatus.READY_FOR_DDL or blockers:
        raise ValueError("DDL generation BLOCKED: Effective Star Schema Contract não está READY_FOR_DDL."
                         + (" " + " ".join(blockers) if blockers else ""))
    planner = _Planner(contract, config)
    tables, indexes, comments = planner.build()
    sql = _render_sql(planner.schema, tables, indexes, comments, config.ddl_mode)
    fingerprint = hashlib.sha256(sql.encode("utf-8")).hexdigest()
    lineage = DDLLineage(source_document_id=contract.source_document_id, analysis_id=contract.analysis_id,
                         prepared_dataset_id=contract.prepared_dataset_id,
                         grain_definition_id=contract.grain_definition_id,
                         dimensional_discovery_id=contract.dimensional_discovery_id,
                         star_schema_contract_id=contract.contract_id,
                         star_schema_contract_version=contract.version)
    config_identity = {"contract": contract.contract_id, "contract_version": contract.version,
                       "schema": planner.schema, "mode": config.ddl_mode.value,
                       "postgres": config.postgresql_version_target, "artifact_version": version,
                       "fingerprint": fingerprint}
    plan_id = "physical-plan:" + _stable_hash(config_identity)[:24]
    status = DDLGenerationStatus.GENERATED_WITH_WARNINGS if planner.warnings else DDLGenerationStatus.GENERATED
    all_columns = [column for table in tables for column in table.columns]
    pks = [table.primary_key for table in tables if table.primary_key]
    fks = [constraint for table in tables for constraint in table.foreign_keys]
    uniques = [constraint for table in tables for constraint in table.unique_constraints]
    checks = [constraint for table in tables for constraint in table.check_constraints]
    plan_payload = {"tables": [table.model_dump(mode="json") for table in tables],
                    "indexes": [index.model_dump(mode="json") for index in indexes],
                    "schema": planner.schema, "ddl_fingerprint": fingerprint}
    plan = PhysicalSchemaPlan(physical_schema_plan_id=plan_id,
                              star_schema_contract_id=contract.contract_id,
                              star_schema_contract_version=contract.version,
                              analysis_id=contract.analysis_id, source_document_id=contract.source_document_id,
                              prepared_dataset_id=contract.prepared_dataset_id, target_schema=planner.schema,
                              tables=tables, columns=all_columns, primary_keys=pks, foreign_keys=fks,
                              unique_constraints=uniques, check_constraints=checks, indexes=indexes,
                              comments=comments, warnings=planner.warnings, lineage=lineage,
                              fingerprint=_stable_hash(plan_payload), version=version, status=status)
    validation = validate_postgresql_ddl(sql, plan)
    if not validation.passed:
        raise ValueError("DDL structural validation failed: " + "; ".join(validation.errors))
    artifact = PostgreSQLDDLArtifact(ddl_artifact_id="postgres-ddl:" + _stable_hash(config_identity)[:24],
                                     physical_schema_plan_id=plan_id,
                                     postgresql_version_compatibility_target=config.postgresql_version_target,
                                     schema_name=planner.schema, sql=sql,
                                     statement_count=sql.count(";"), table_count=len(tables),
                                     index_count=len(indexes),
                                     constraint_count=len(pks) + len(fks) + len(uniques) + len(checks),
                                     fingerprint=fingerprint, warnings=planner.warnings,
                                     lineage=lineage, version=version, status=status,
                                     validation_passed=True)
    return plan, artifact
