"""Deterministic planning from prepared data and effective physical/logical contracts."""

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import UUID

from core.ddl.models import PhysicalSchemaPlan, PhysicalSchemaStatus, PostgreSQLDDLArtifact
from core.etl.models import (
    BridgeLoadPlan, ColumnTransformationPlan, DerivedFieldRule, DimensionLoadPlan, DimensionLoadType,
    DimensionalETLPlan, ETLLineage, ETLPlanStatus, ETLRunAuditPlan, ETLSourceContract,
    FactLoadPlan, FieldMapping, IdempotencyPlan, IncrementalLoadStrategy, MappingRole,
    MeasureReconciliation, MissingLookupAction, ReconciliationCapability,
    ReconciliationPlan, RejectionAction, RejectionPolicy, RestartPlan, SCDType1LoadPlan,
    SCDType2LoadPlan, SurrogateKeyResolutionPlan, UnknownMemberPlan,
)
from core.grain.models import GrainDefinition, MeasureAggregationHint
from core.prepared.models import PreparedDataset
from core.quality.models import DataQualityReport, IdentifierConstraint, QualitySeverity
from core.star.models import Nullability, SCDType, StarSchemaContract


@dataclass(frozen=True)
class ETLPlanningConfig:
    unknown_member_enabled: bool = True
    unknown_member_reserved_key: int = 0
    unknown_member_business_key_value: str = "UNKNOWN"
    rejection_action: RejectionAction = RejectionAction.QUARANTINE
    required_key_action: RejectionAction = RejectionAction.REJECT
    incremental_strategy: IncrementalLoadStrategy = IncrementalLoadStrategy.UNKNOWN
    fact_duplicate_policy: str = "DETECT_REPLAY_BY_VALIDATED_GRAIN_AND_BATCH"
    idempotency_strategy: str = "LOAD_BATCH_ID"


def _hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def topological_execution_order(dependencies: dict[str, list[str]]) -> list[str]:
    """Stable Kahn ordering; dependencies map node -> prerequisites."""
    nodes = set(dependencies)
    nodes.update(dep for values in dependencies.values() for dep in values)
    remaining = {node: set(dependencies.get(node, [])) for node in nodes}
    order: list[str] = []
    while remaining:
        ready = sorted(node for node, deps in remaining.items() if not deps)
        if not ready:
            raise ValueError("Dependency cycle detected: " + ", ".join(sorted(remaining)))
        for node in ready:
            order.append(node); remaining.pop(node)
        for deps in remaining.values():
            deps.difference_update(ready)
    return order


def _physical_maps(physical: PhysicalSchemaPlan):
    by_id = {table.table_id: table for table in physical.tables}
    columns = {(table.table_id, column.source_field_id): column for table in physical.tables
               for column in table.columns if column.source_field_id}
    return by_id, columns


def _precision_scale(values: list[object]) -> tuple[int, int] | None:
    maximum_precision = maximum_scale = 0
    found = False
    for value in values:
        if value is None: continue
        try: decimal = Decimal(str(value))
        except (InvalidOperation, ValueError): continue
        found = True
        sign, digits, exponent = decimal.as_tuple()
        scale = max(0, -exponent)
        maximum_scale = max(maximum_scale, scale)
        maximum_precision = max(maximum_precision, len(digits) + max(0, exponent))
    return (maximum_precision, maximum_scale) if found else None


def _mapping(field, table, column, role: MappingRole, *, lookup=None, required=False, warning=None):
    transformations = [item.value for item in field.transformation_rules] if field else []
    transformation = " | ".join(transformations) if transformations else "IDENTITY_EFFECTIVE_VALUE"
    return FieldMapping(source_field_id=field.source_field_id if field else None,
                        prepared_field_name=field.technical_name if field else None,
                        effective_semantic_role=field.effective_semantic_role.value if field else None,
                        target_table=table.physical_name if table else None,
                        target_column=column.physical_name if column else None,
                        mapping_role=role, transformation=transformation,
                        source_type=field.prepared_type if field else None,
                        target_type=column.postgres_type if column else None,
                        nullable=column.nullable if column else True,
                        required_for_load=required, lookup_dimension=lookup,
                        lineage=[field.source_field_id, column.column_id] if field and column else [],
                        warnings=[warning] if warning else [])


def build_dimensional_etl_plan(
    dataset: PreparedDataset, star: StarSchemaContract, physical: PhysicalSchemaPlan,
    ddl_artifact: PostgreSQLDDLArtifact, *, grain: GrainDefinition | None = None,
    quality_report: DataQualityReport | None = None,
    identifier_constraints: dict[str, IdentifierConstraint] | None = None,
    config: ETLPlanningConfig | None = None, version: int = 1,
) -> DimensionalETLPlan:
    """Build an immutable plan. It never writes target data or regenerates DDL."""
    config = config or ETLPlanningConfig()
    constraints = identifier_constraints or {}
    blockers: list[str] = []
    warnings: list[str] = []
    if dataset.prepared_dataset_id != star.prepared_dataset_id or dataset.version != star.prepared_dataset_version:
        blockers.append("Prepared Dataset version does not match Effective Star Schema Contract.")
    if dataset.fingerprint != star.lineage.prepared_dataset_fingerprint:
        blockers.append("Prepared Dataset fingerprint mismatch.")
    if physical.star_schema_contract_id != star.contract_id or physical.star_schema_contract_version != star.version:
        blockers.append("Effective Physical Schema does not match Star Schema Contract.")
    if ddl_artifact.physical_schema_plan_id != physical.physical_schema_plan_id:
        blockers.append("DDL artifact does not match Physical Schema Plan.")
    if ddl_artifact.fingerprint != hashlib.sha256(ddl_artifact.sql.encode()).hexdigest():
        blockers.append("DDL fingerprint mismatch.")
    if not ddl_artifact.validation_passed or not ddl_artifact.human_validated:
        blockers.append("DDL must be structurally and human validated.")
    if physical.lifecycle_status != PhysicalSchemaStatus.EFFECTIVE:
        blockers.append("Physical Schema is not EFFECTIVE.")
    if grain and (grain.grain_id != star.grain_definition_id
                  or grain.prepared_dataset_fingerprint != dataset.fingerprint):
        blockers.append("Effective Grain mismatch.")
    if quality_report and quality_report.critical_count:
        blockers.append("Quality report contains critical blockers.")

    fields = {field.source_field_id: field for field in dataset.schema_fields}
    tables, physical_columns = _physical_maps(physical)
    mappings: list[FieldMapping] = []
    transformations: list[ColumnTransformationPlan] = []
    derived_rules: list[DerivedFieldRule] = []
    dimensions: list[DimensionLoadPlan] = []
    facts: list[FactLoadPlan] = []
    bridges: list[BridgeLoadPlan] = []
    lookups: list[SurrogateKeyResolutionPlan] = []
    scd_plans = []
    unknown_plans: list[UnknownMemberPlan] = []
    mapped_sources: set[str] = set()
    mapped_targets: set[tuple[str, str]] = set()

    for dimension in sorted(star.dimension_tables, key=lambda item: (item.logical_name, item.dimension_id)):
        table = tables.get(dimension.dimension_id)
        if not table:
            blockers.append(f"Missing physical table for dimension {dimension.dimension_id}."); continue
        bk = dimension.business_key_fields
        validated_bk = bool(bk.fields) and bk.uniqueness_validation_status.upper().startswith("VALIDATED")
        if not validated_bk:
            blockers.append(f"Dimension {table.physical_name} lacks a validated business key.")
        source_fields = list(dict.fromkeys(bk.fields + dimension.attributes))
        date_sources = [source for source in source_fields if fields.get(source)
                        and fields[source].effective_semantic_role.value == "date"]
        for source_id in source_fields:
            field, column = fields.get(source_id), physical_columns.get((dimension.dimension_id, source_id))
            if field and column:
                mapping = _mapping(field, table, column, MappingRole.DIRECT,
                                   required=source_id in bk.fields and bk.nullability == Nullability.NOT_NULLABLE)
                mappings.append(mapping); mapped_sources.add(source_id); mapped_targets.add((table.table_id, column.physical_name))
            elif source_id in {"date", "full_date", "year", "month", "day", "quarter", "semester", "day_of_week", "month_name"} and date_sources:
                column = physical_columns.get((dimension.dimension_id, source_id))
                if column:
                    mapping = _mapping(fields[date_sources[0]], table, column, MappingRole.DERIVED)
                    mapping.transformation = f"DATE_COMPONENT:{source_id}"
                    mappings.append(mapping); mapped_targets.add((table.table_id, column.physical_name))
                    derived_rules.append(DerivedFieldRule(rule_id=f"gregorian:{dimension.dimension_id}:{source_id}",
                        reason="Deterministic Gregorian attribute contracted by the date dimension.",
                        inputs=[date_sources[0]], output=column.physical_name))
        sk = next((c for c in table.columns if c.role == "SURROGATE_KEY"), None)
        if sk:
            mappings.append(_mapping(None, table, sk, MappingRole.DEFAULT_VALUE))
            mappings[-1].transformation = "SYSTEM_GENERATED_IDENTITY"
            mapped_targets.add((table.table_id, sk.physical_name))
        strategy = dimension.scd_strategy
        if strategy.strategy == SCDType.TYPE_1 and not strategy.requires_validation:
            scd_plans.append(SCDType1LoadPlan(dimension_id=dimension.dimension_id,
                business_key=bk.fields, attributes_to_update=dimension.attributes,
                comparison_fields=dimension.attributes))
            load_type = DimensionLoadType.UPSERT
        elif strategy.strategy == SCDType.TYPE_2 and not strategy.requires_validation:
            scd_plans.append(SCDType2LoadPlan(dimension_id=dimension.dimension_id,
                business_key=bk.fields, tracked_attributes=strategy.tracked_attributes or dimension.attributes,
                effective_from=strategy.effective_from_field_plan, effective_to=strategy.effective_to_field_plan,
                current_flag=strategy.current_flag_plan,
                change_detection_fields=strategy.tracked_attributes or dimension.attributes))
            load_type = DimensionLoadType.SCD_PROCESS
            for name in (strategy.effective_from_field_plan, strategy.effective_to_field_plan, strategy.current_flag_plan):
                column = next((c for c in table.columns if c.logical_name == name), None)
                if column:
                    mappings.append(_mapping(None, table, column, MappingRole.DERIVED))
                    mappings[-1].transformation = "CONTRACTED_SCD_TYPE_2_SYSTEM_VALUE"
                    mapped_targets.add((table.table_id, column.physical_name))
        else:
            load_type = DimensionLoadType.UNKNOWN
            blockers.append(f"Dimension {table.physical_name} has unresolved SCD strategy.")
        unknown_plans.append(UnknownMemberPlan(enabled=config.unknown_member_enabled,
            reserved_key=config.unknown_member_reserved_key,
            business_key_value=config.unknown_member_business_key_value,
            description="Unknown member reserved for permitted unresolved optional lookups.",
            applicable_dimensions=[dimension.dimension_id] if config.unknown_member_enabled else [],
            reason="Preserve eligible fact rows without silently nulling foreign keys."))
        date_values = sorted(str(row.values.get(source_id)) for source_id in source_fields for row in dataset.rows
                             if row.values.get(source_id) is not None and
                             (fields.get(source_id) and fields[source_id].effective_semantic_role.value == "date"))
        dimensions.append(DimensionLoadPlan(dimension_id=dimension.dimension_id,
            target_table=table.physical_name, business_key=bk.fields,
            surrogate_key=sk.physical_name if sk else dimension.surrogate_key_plan.name,
            attributes=dimension.attributes, source_fields=source_fields,
            deduplication_strategy="DISTINCT_BY_VALIDATED_BUSINESS_KEY" if validated_bk else "BLOCK",
            scd_strategy=strategy.strategy.value,
            unknown_member_strategy="RESERVED_MEMBER" if config.unknown_member_enabled else "DISABLED",
            load_type=load_type, lookup_strategy="BUSINESS_KEY_TO_SURROGATE_KEY",
            quality_dependencies=[str(x) for x in dimension.quality_dependencies],
            preconditions=["business_key_validated", "source_types_compatible"],
            postconditions=["business_key_unique", "surrogate_key_not_null"],
            required_date_min=date_values[0] if date_values else None,
            required_date_max=date_values[-1] if date_values else None))

    dimension_by_id = {item.dimension_id: item for item in dimensions}
    for fact in sorted(star.fact_tables, key=lambda item: (item.logical_name, item.fact_id)):
        table = tables.get(fact.fact_id)
        if not table:
            blockers.append(f"Missing physical table for fact {fact.fact_id}."); continue
        measure_maps, degenerate_maps, attribute_maps = [], [], []
        for items, bucket in ((fact.measures, measure_maps), (fact.degenerate_identifiers, degenerate_maps),
                              (fact.fact_attributes, attribute_maps)):
            for item in items:
                source_id = item.source_field_id
                field, column = fields.get(source_id), physical_columns.get((fact.fact_id, source_id))
                if field and column:
                    mapping = _mapping(field, table, column, MappingRole.DIRECT,
                                       required=not column.nullable)
                    mappings.append(mapping); bucket.append(mapping)
                    mapped_sources.add(source_id); mapped_targets.add((table.table_id, column.physical_name))
                    match = re.fullmatch(r"NUMERIC\((\d+),(\d+)\)", column.postgres_type)
                    evidence = _precision_scale([row.values.get(source_id) for row in dataset.rows])
                    if match and evidence and evidence[1] > int(match.group(2)):
                        blockers.append(f"Precision loss: {table.physical_name}.{column.physical_name} source scale {evidence[1]} exceeds target scale {match.group(2)}.")
                    if "INT" in column.postgres_type and any(isinstance(row.values.get(source_id), str)
                            and re.match(r"^0\d+$", row.values.get(source_id)) for row in dataset.rows):
                        blockers.append(f"Leading-zero loss blocked for {source_id}; numeric cast is unsafe.")
        required_dims, optional_dims, fact_lookup_ids = [], [], []
        for fk in sorted(fact.foreign_keys, key=lambda item: (item.fact_fk_name, item.dimension_id)):
            column = next((c for c in table.columns if c.logical_name == fk.fact_fk_name), None)
            dim_table = tables.get(fk.dimension_id)
            if not column or not dim_table: continue
            optional = fk.optionality != Nullability.NOT_NULLABLE
            missing = (MissingLookupAction.USE_UNKNOWN_MEMBER if optional and config.unknown_member_enabled
                       else MissingLookupAction.REJECT_ROW)
            lookup_id = f"lookup:{fact.fact_id}:{fk.fact_fk_name}"
            resolution = SurrogateKeyResolutionPlan(resolution_id=lookup_id, fact_id=fact.fact_id,
                dimension_id=fk.dimension_id, target_fact_column=column.physical_name,
                dimension_table=dim_table.physical_name,
                dimension_surrogate_key=fk.dimension_surrogate_key_name,
                source_business_key_fields=fk.source_mapping_fields,
                normalization=[rule.value for source in fk.source_mapping_fields for rule in
                               (fields[source].transformation_rules if source in fields else [])],
                missing_action=missing, optional=optional)
            lookups.append(resolution); fact_lookup_ids.append(lookup_id)
            (optional_dims if optional else required_dims).append(fk.dimension_id)
            for source_id in fk.source_mapping_fields:
                field = fields.get(source_id)
                if field:
                    mapping = _mapping(field, table, column, MappingRole.SURROGATE_KEY_LOOKUP,
                                       lookup=dim_table.physical_name, required=not optional)
                    mappings.append(mapping); mapped_sources.add(source_id)
                    if field.effective_semantic_role.value == "date":
                        derived_rules.append(DerivedFieldRule(
                            rule_id=f"date-lookup:{fact.fact_id}:{fk.fact_fk_name}:{source_id}",
                            reason="Validated date role maps through the contracted role-playing/base date dimension.",
                            inputs=[source_id], output=column.physical_name))
            mapped_targets.add((table.table_id, column.physical_name))
        sk = next((c for c in table.columns if c.role == "SURROGATE_KEY"), None)
        if sk:
            mappings.append(_mapping(None, table, sk, MappingRole.DEFAULT_VALUE))
            mappings[-1].transformation = "SYSTEM_GENERATED_IDENTITY"
            mapped_targets.add((table.table_id, sk.physical_name))
        facts.append(FactLoadPlan(fact_id=fact.fact_id, target_table=table.physical_name,
            fact_type=fact.fact_type.value, grain=fact.grain_fields,
            source_fields=sorted({m.source_field_id for m in measure_maps + degenerate_maps + attribute_maps if m.source_field_id}
                                 | {s for fk in fact.foreign_keys for s in fk.source_mapping_fields}),
            measure_mappings=measure_maps, degenerate_dimension_mappings=degenerate_maps,
            fact_attribute_mappings=attribute_maps, surrogate_key_lookups=fact_lookup_ids,
            required_dimensions=required_dims, optional_dimensions=optional_dims,
            duplicate_policy=config.fact_duplicate_policy,
            rejection_policy="REJECT_REQUIRED_FAILURE; QUARANTINE_WITH_LINEAGE",
            aggregation_risks=[str(x) for x in fact.aggregation_risks],
            preconditions=["grain_compatible", "required_dimension_lookups_resolved"],
            postconditions=["no_silent_row_loss", "fk_resolution_rate_measured"]))
        if fact.fact_type.value == "PERIODIC_SNAPSHOT" and not any(
                fields.get(source) and fields[source].effective_semantic_role.value == "date"
                for source in fact.grain_fields):
            blockers.append(f"Periodic snapshot {table.physical_name} requires a temporal grain component.")

    for candidate in sorted((x for x in star.bridge_candidates if not x.requires_validation), key=lambda x: x.bridge_id):
        table = tables.get(candidate.bridge_id)
        if not table: blockers.append(f"Validated bridge {candidate.bridge_id} missing physically."); continue
        business_mappings, bridge_lookups = [], []
        star_dimensions = {item.dimension_id: item for item in star.dimension_tables}
        for side, dimension_id in (("left", candidate.left_entity), ("right", candidate.right_entity)):
            dimension = star_dimensions.get(dimension_id)
            dimension_table = tables.get(dimension_id)
            bridge_column = next((c for c in table.columns if c.logical_name == f"{side}_sk"), None)
            if not dimension or not dimension_table or not bridge_column:
                blockers.append(f"Bridge {table.physical_name} lacks a resolvable {side} dimension mapping.")
                continue
            lookup_id = f"lookup:{candidate.bridge_id}:{side}_sk"
            bridge_lookups.append(lookup_id)
            lookups.append(SurrogateKeyResolutionPlan(resolution_id=lookup_id,
                fact_id=candidate.bridge_id, dimension_id=dimension_id,
                target_fact_column=bridge_column.physical_name,
                dimension_table=dimension_table.physical_name,
                dimension_surrogate_key=dimension.surrogate_key_plan.name,
                source_business_key_fields=dimension.business_key_fields.fields,
                normalization=[rule.value for source in dimension.business_key_fields.fields for rule in
                               (fields[source].transformation_rules if source in fields else [])],
                missing_action=MissingLookupAction.REJECT_ROW, optional=False))
            for source_id in dimension.business_key_fields.fields:
                field = fields.get(source_id)
                if field:
                    mapping = _mapping(field, table, bridge_column, MappingRole.SURROGATE_KEY_LOOKUP,
                                       lookup=dimension_table.physical_name, required=True)
                    mappings.append(mapping); business_mappings.append(mapping); mapped_sources.add(source_id)
                    mapped_targets.add((table.table_id, bridge_column.physical_name))
        bridges.append(BridgeLoadPlan(bridge_id=candidate.bridge_id, bridge_table=table.physical_name,
            left_dimension=candidate.left_entity, right_dimension=candidate.right_entity,
            business_mappings=business_mappings, surrogate_lookups=bridge_lookups,
            deduplication_key=[c.physical_name for c in table.columns]))

    # Explicitly account for every prepared field not consumed by a target.
    for field in sorted(dataset.schema_fields, key=lambda item: item.source_field_id):
        if field.source_field_id not in mapped_sources:
            unresolved = field.source_field_id in star.unresolved_fields
            role = MappingRole.UNRESOLVED if unresolved else MappingRole.IGNORED
            mappings.append(_mapping(field, None, None, role, warning="No target by validated contract."))
            if unresolved: blockers.append(f"Prepared field {field.source_field_id} remains unresolved.")
    all_targets = {(t.table_id, c.physical_name) for t in physical.tables for c in t.columns}
    missing_targets = sorted(all_targets - mapped_targets)
    for table_id, column_name in missing_targets:
        blockers.append(f"Target column without mapping or system generation: {table_id}.{column_name}")

    for mapping in mappings:
        if mapping.target_table and mapping.target_column:
            transformations.append(ColumnTransformationPlan(target_table=mapping.target_table,
                target_column=mapping.target_column, source_field_id=mapping.source_field_id,
                effective_value="PREPARED_EFFECTIVE_VALUE" if mapping.source_field_id else "SYSTEM_VALUE",
                transformation=mapping.transformation, lookup=mapping.lookup_dimension,
                null_policy="REQUIRED_REJECT" if mapping.required_for_load else "ALLOW_CONTRACT_NULL",
                validations=["no_precision_loss", "no_leading_zero_loss", "no_date_reinterpretation"]))

    dependencies: dict[str, list[str]] = {item.target_table: [] for item in dimensions}
    dimension_table_by_id = {item.dimension_id: item.target_table for item in dimensions}
    for bridge in bridges:
        dependencies[bridge.bridge_table] = sorted(filter(None, [dimension_table_by_id.get(bridge.left_dimension),
                                                                 dimension_table_by_id.get(bridge.right_dimension)]))
    for fact in facts:
        logical = next(item for item in star.fact_tables if item.fact_id == fact.fact_id)
        deps = [dimension_table_by_id[fk.dimension_id] for fk in logical.foreign_keys
                if fk.dimension_id in dimension_table_by_id]
        dependencies[fact.target_table] = sorted(set(deps))
    try: order = topological_execution_order(dependencies)
    except ValueError as error: blockers.append(str(error)); order = []
    ranks = {name: index + 1 for index, name in enumerate(order)}
    for item in [*dimensions, *facts]: item.execution_rank = ranks.get(item.target_table, 0)
    for item in bridges: item.execution_rank = ranks.get(item.bridge_table, 0)

    reconciliations = []
    for fact in star.fact_tables:
        table = tables.get(fact.fact_id)
        for measure in fact.measures:
            column = physical_columns.get((fact.fact_id, measure.source_field_id))
            if not table or not column: continue
            if measure.aggregation_risk:
                capability, reason = ReconciliationCapability.REQUIRES_VALIDATION, "Aggregation risk unresolved."
            elif measure.additivity in {MeasureAggregationHint.ADDITIVE, MeasureAggregationHint.ADDITIVE_CANDIDATE}:
                capability, reason = ReconciliationCapability.RECONCILABLE, "Additive at validated grain."
            elif measure.additivity in {MeasureAggregationHint.NON_ADDITIVE, MeasureAggregationHint.NON_ADDITIVE_CANDIDATE}:
                capability, reason = ReconciliationCapability.NOT_RECONCILABLE, "SUM is invalid for non-additive measure."
            else: capability, reason = ReconciliationCapability.REQUIRES_VALIDATION, "Additivity needs context."
            reconciliations.append(MeasureReconciliation(source_field_id=measure.source_field_id,
                target_table=table.physical_name, target_column=column.physical_name, status=capability,
                comparison="SUM(source effective) = SUM(fact)" if capability == ReconciliationCapability.RECONCILABLE else None,
                reason=reason))
    reconciliation = ReconciliationPlan(source_row_count=dataset.row_count,
        prepared_row_count=dataset.row_count,
        expected_fact_rows={item.target_table: ("1:1_CANDIDATE" if len(facts) == 1 else "CONDITIONAL_MULTI_FACT") for item in facts},
        expected_dimension_member_counts={item.target_table: None for item in dimensions},
        measure_reconciliations=reconciliations, rejected_row_policy=config.rejection_action.value,
        tolerance_rules=["row_loss=0 unless represented by rejection", "exact comparison unless contract defines tolerance"],
        aggregation_risk_notes=[risk for fact in facts for risk in fact.aggregation_risks], status="PLANNED")
    rejection = RejectionPolicy(default_action=config.rejection_action,
                                required_key_action=config.required_key_action,
                                invalid_type_action=RejectionAction.QUARANTINE)
    validation_rules = [
        {"rule": "prepared_fingerprint_matches", "passed": dataset.fingerprint == star.lineage.prepared_dataset_fingerprint},
        {"rule": "ddl_fingerprint_matches", "passed": ddl_artifact.fingerprint == hashlib.sha256(ddl_artifact.sql.encode()).hexdigest()},
        {"rule": "star_version_matches", "passed": physical.star_schema_contract_version == star.version},
        {"rule": "business_keys_resolved", "passed": all(item.deduplication_strategy != "BLOCK" for item in dimensions)},
        {"rule": "required_mappings_complete", "passed": not missing_targets},
        {"rule": "quality_blockers_zero", "passed": not quality_report or quality_report.critical_count == 0},
        {"rule": "execution_order_acyclic", "passed": bool(order) or not dependencies},
        {"rule": "no_silent_data_loss", "passed": len({m.source_field_id for m in mappings if m.source_field_id}) == len(fields)},
    ]
    if any(not rule["passed"] for rule in validation_rules):
        blockers.extend(f"Validation failed: {rule['rule']}" for rule in validation_rules if not rule["passed"])
    target_coverage = 100.0 * len(mapped_targets) / len(all_targets) if all_targets else 100.0
    source_coverage = 100.0 * len({m.source_field_id for m in mappings if m.source_field_id}) / len(fields) if fields else 100.0
    if target_coverage < 100: blockers.append("Target field coverage is below 100%.")
    if source_coverage < 100: blockers.append("Source field coverage is below 100%.")
    status = ETLPlanStatus.BLOCKED if blockers else ETLPlanStatus.READY_WITH_WARNINGS if warnings else ETLPlanStatus.READY_FOR_DRY_RUN
    lineage = ETLLineage(source_document_id=dataset.source_document_id, analysis_id=dataset.analysis_id,
        prepared_dataset_id=dataset.prepared_dataset_id, prepared_dataset_version=dataset.version,
        star_schema_contract_id=star.contract_id, physical_schema_plan_id=physical.physical_schema_plan_id,
        ddl_artifact_id=ddl_artifact.ddl_artifact_id)
    source_contract = ETLSourceContract(prepared_dataset_id=dataset.prepared_dataset_id,
        fingerprint=dataset.fingerprint, row_count=dataset.row_count,
        schema_fields=[field.model_dump(mode="json") for field in dataset.schema_fields],
        effective_fields=sorted(fields), quality_gate=dataset.status.value,
        unresolved_issues=[issue.issue_id for issue in dataset.unresolved_quality_issues],
        readiness="READY" if dataset.status.value != "BLOCKED" else "BLOCKED")
    policy_payload = {"config": config.__dict__, "dataset": dataset.fingerprint,
                      "star": [star.contract_id, star.version], "physical": physical.fingerprint,
                      "ddl": ddl_artifact.fingerprint, "version": version}
    fingerprint = _hash(policy_payload)
    return DimensionalETLPlan(etl_plan_id="etl-plan:" + fingerprint[:24], analysis_id=dataset.analysis_id,
        source_document_id=dataset.source_document_id, prepared_dataset_id=dataset.prepared_dataset_id,
        prepared_dataset_version=dataset.version, physical_schema_plan_id=physical.physical_schema_plan_id,
        ddl_artifact_id=ddl_artifact.ddl_artifact_id, star_schema_contract_id=star.contract_id,
        version=version, status=status, source_contract=source_contract, field_mappings=mappings,
        column_transformation_plans=transformations, derived_field_rules=derived_rules,
        dimension_load_plans=dimensions,
        fact_load_plans=facts, bridge_load_plans=bridges,
        surrogate_key_resolution_plans=lookups, scd_plans=scd_plans,
        unknown_member_plans=unknown_plans, rejection_policy=rejection,
        reconciliation_plan=reconciliation,
        idempotency_plan=IdempotencyPlan(strategy=config.idempotency_strategy,
            duplicate_prevention="Record dataset fingerprint and load_batch_id before fact load."),
        restart_plan=RestartPlan(checkpoint_strategy="CHECKPOINT_AFTER_EACH_DEPENDENCY_ORDER_STEP",
            replay_policy="REPLAY_FROM_FIRST_INCOMPLETE_STEP_USING_SAME_PLAN_AND_BATCH",
            safe_restart_point="AFTER_COMPLETED_DIMENSIONS_BEFORE_FACTS"),
        incremental_strategy=config.incremental_strategy, load_audit_plan=ETLRunAuditPlan(),
        execution_order=order, dependencies=dependencies, validation_rules=validation_rules,
        warnings=sorted(set(warnings)), blockers=sorted(set(blockers)),
        target_coverage_percentage=target_coverage, source_coverage_percentage=source_coverage,
        lineage=lineage, fingerprint=fingerprint)
