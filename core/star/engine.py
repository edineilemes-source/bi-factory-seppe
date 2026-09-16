"""Deterministic transformation from Effective Dimensional Discovery to a logical contract."""

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from uuid import uuid4

from core.dimensional.models import ModelingRole, ProposalStatus, ValidatedDimensionalDiscovery
from core.grain.models import GrainDefinition, MeasureAggregationHint
from core.prepared.models import PreparedDataset, PreparedField
from core.quality.models import FieldApplicability, FieldRequirement, IdentifierConstraint
from core.star.models import (
    AggregationType, BridgeTableCandidate, BusinessKeyContract, Cardinality,
    ConformedDimensionContractCandidate, ContractItemStatus, ContractStatus,
    DegenerateDimensionContract, DimensionTableContract, FactAttributeContract,
    FactTableContract, FieldCoverage, ForeignKeyContract, HierarchyContract,
    LogicalDataType, MeasureContract, ModelingWarning, Nullability,
    ReadinessStatus, RelationshipContract, RolePlayingDimensionContract,
    SCDStrategyContract, SCDType, StarSchemaContract, StarSchemaContractReport,
    StarSchemaLineage, SurrogateKeyPlan, ValidationResult, WarningSeverity, WarningType,
)


@dataclass(frozen=True)
class StarSchemaConfig:
    max_relationships: int = 100
    max_bridge_candidates: int = 20
    max_warnings: int = 200


def _id(prefix: str, *parts: str) -> str:
    return prefix + ":" + hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_") or "contract"


def _logical_type(field: PreparedField | None) -> LogicalDataType:
    if field is None:
        return LogicalDataType.UNKNOWN
    value = field.prepared_type.casefold()
    if "uuid" in value: return LogicalDataType.UUID
    if "datetime" in value or "timestamp" in value: return LogicalDataType.DATETIME
    if "date" in value: return LogicalDataType.DATE
    if "bool" in value: return LogicalDataType.BOOLEAN
    if any(token in value for token in ("int", "integer")): return LogicalDataType.INTEGER
    if any(token in value for token in ("number", "decimal", "float", "numeric")): return LogicalDataType.DECIMAL
    if any(token in value for token in ("text", "str", "string")): return LogicalDataType.TEXT
    return LogicalDataType.UNKNOWN


def _nullable(field: PreparedField | None) -> Nullability:
    if field is None:
        return Nullability.UNKNOWN
    if field.requirement == FieldRequirement.REQUIRED and field.applicability == FieldApplicability.APPLICABLE:
        return Nullability.NOT_NULLABLE
    if field.requirement in {FieldRequirement.OPTIONAL, FieldRequirement.CONDITIONAL}:
        return Nullability.NULLABLE
    return Nullability.UNKNOWN


def _unique_names(items: list[tuple[str, str]], prefix: str) -> tuple[dict[str, str], list[ModelingWarning]]:
    result, counts, warnings = {}, Counter(), []
    for item_id, suggestion in items:
        base = f"{prefix}_{_slug(suggestion.removeprefix(prefix + '_'))}"
        counts[base] += 1
        name = base if counts[base] == 1 else f"{base}_{counts[base]}"
        result[item_id] = name
        if counts[base] > 1:
            warnings.append(ModelingWarning(
                warning_id=_id("warning", "collision", item_id), warning_type=WarningType.NAME_COLLISION,
                severity=WarningSeverity.WARNING,
                message=f"Colisão em {base}; resolvida deterministicamente como {name}.",
                related_ids=[item_id]))
    return result, warnings


def _many_to_many(dataset: PreparedDataset, left: list[str], right: list[str]) -> tuple[bool, list[str]]:
    if not left or not right:
        return False, []
    l2r, r2l = defaultdict(set), defaultdict(set)
    for row in dataset.rows:
        lv = tuple(repr(row.values.get(field)) for field in left)
        rv = tuple(repr(row.values.get(field)) for field in right)
        if all(row.values.get(field) is not None for field in left + right):
            l2r[lv].add(rv); r2l[rv].add(lv)
    many_left = sum(len(values) > 1 for values in l2r.values())
    many_right = sum(len(values) > 1 for values in r2l.values())
    return (many_left > 0 and many_right > 0,
            [f"{many_left} chave(s) à esquerda têm múltiplas chaves à direita.",
             f"{many_right} chave(s) à direita têm múltiplas chaves à esquerda."])


def build_star_schema_contract(
    dataset: PreparedDataset, grain: GrainDefinition,
    dimensional: ValidatedDimensionalDiscovery,
    identifier_constraints: dict[str, IdentifierConstraint] | None = None,
    *, config: StarSchemaConfig | None = None, version: int = 1,
) -> StarSchemaContractReport:
    """Formalize effective knowledge without changing source/prepared values."""
    config = config or StarSchemaConfig()
    constraints = identifier_constraints or {}
    if dimensional.status != ProposalStatus.READY_FOR_STAR_SCHEMA:
        raise ValueError("Effective Dimensional Discovery não está READY_FOR_STAR_SCHEMA.")
    if (dataset.prepared_dataset_id != dimensional.prepared_dataset_id
            or dataset.version != dimensional.prepared_dataset_version
            or dataset.fingerprint != dimensional.prepared_dataset_fingerprint
            or grain.grain_id != dimensional.grain_definition_id
            or grain.version != dimensional.grain_version
            or grain.prepared_dataset_id != dataset.prepared_dataset_id):
        raise ValueError("Dependências efetivas incompatíveis; contrato não pode ser reutilizado.")
    fields = {field.source_field_id: field for field in dataset.schema_fields}
    warnings: list[ModelingWarning] = []
    dim_names, collisions = _unique_names(
        [(d.dimension_candidate_id, d.name) for d in dimensional.dimension_candidates], "dim")
    fact_names, fact_collisions = _unique_names(
        [(f.fact_candidate_id, f.name) for f in dimensional.fact_candidates], "fact")
    warnings.extend(collisions + fact_collisions)

    dimensions: list[DimensionTableContract] = []
    for candidate in dimensional.dimension_candidates:
        dim_id = candidate.dimension_candidate_id
        business_fields = [field for field in candidate.business_identifier_fields
                           if field in fields and field.casefold() != "source_row_id"
                           and not constraints.get(field, IdentifierConstraint()).technical_key]
        if not business_fields and candidate.role.value in {
            "ROLE_PLAYING_DIMENSION_CANDIDATE", "CONFORMED_DIMENSION_CANDIDATE",
            "JUNK_DIMENSION_CANDIDATE"}:
            # Date/junk candidates have a deterministic logical natural key even
            # when Sprint 3.1 did not label one field as a business identifier.
            business_fields = [field for field in candidate.source_fields
                               if field in fields and field.casefold() != "source_row_id"]
        qdeps = candidate.quality_dependencies
        nullabilities = {_nullable(fields.get(field)) for field in business_fields}
        bk_nullability = (Nullability.NULLABLE if Nullability.NULLABLE in nullabilities
                          else next(iter(nullabilities), Nullability.UNKNOWN))
        declared_unique = bool(business_fields) and all(
            constraints.get(field, IdentifierConstraint()).unique
            or constraints.get(field, IdentifierConstraint()).business_key for field in business_fields)
        business_key = BusinessKeyContract(
            fields=business_fields, uniqueness_expected=declared_unique,
            uniqueness_validation_status="VALIDATED" if declared_unique else "REQUIRES_VALIDATION",
            nullability=bk_nullability, quality_dependencies=qdeps,
            source_confidence=candidate.confidence,
            requires_validation=not declared_unique or not business_fields)
        if not business_fields:
            warnings.append(ModelingWarning(
                warning_id=_id("warning", "bk", dim_id), warning_type=WarningType.UNRESOLVED_BUSINESS_KEY,
                severity=WarningSeverity.ERROR, message=f"{dim_names[dim_id]} não possui business key mínima resolvida.",
                related_ids=[dim_id], blocker=True))
        scd = SCDStrategyContract(
            dimension_id=dim_id, strategy=SCDType.UNKNOWN,
            reason="Não há estratégia temporal explicitamente validada; nenhuma SCD foi inferida.",
            requires_validation=True)
        warnings.append(ModelingWarning(
            warning_id=_id("warning", "scd", dim_id), warning_type=WarningType.UNKNOWN_SCD_STRATEGY,
            severity=WarningSeverity.WARNING, message=f"Estratégia SCD de {dim_names[dim_id]} requer validação.",
            related_ids=[dim_id]))
        hierarchies = [HierarchyContract(
            name=f"hierarchy_{index + 1}", levels=levels,
            observed_dependency_support=candidate.dependency_evidence)
            for index, levels in enumerate(candidate.hierarchy_candidates)]
        dimension_attributes = list(candidate.descriptive_attributes)
        if candidate.name.casefold() == "date" or candidate.role.value.startswith("ROLE_PLAYING"):
            # Gregorian components are deterministic derivations of a validated
            # date; no fiscal calendar or business-specific calendar is assumed.
            dimension_attributes = list(dict.fromkeys(
                dimension_attributes + ["date", "year", "month", "day", "quarter", "semester"]))
        dimensions.append(DimensionTableContract(
            dimension_id=dim_id, logical_name=dim_names[dim_id],
            human_readable_name=candidate.human_readable_name, role=candidate.role,
            business_concept_id=candidate.business_concept_id,
            surrogate_key_plan=SurrogateKeyPlan(
                name=candidate.suggested_surrogate_key_name or f"{_slug(candidate.name)}_sk"),
            business_key_fields=business_key, attributes=dimension_attributes,
            hierarchies=hierarchies, scd_strategy=scd,
            conformed_candidate=candidate.conformed_candidate,
            role_playing_base_dimension=dim_id if candidate.role.value.startswith("ROLE_PLAYING") else None,
            quality_dependencies=qdeps))
        if qdeps:
            warnings.append(ModelingWarning(
                warning_id=_id("warning", "quality", dim_id), warning_type=WarningType.QUALITY_DEPENDENCY,
                severity=WarningSeverity.WARNING, message=f"{dim_names[dim_id]} depende de issues de qualidade não resolvidas.",
                related_ids=[dim_id]))

    dimensions_by_id = {item.dimension_id: item for item in dimensions}
    measure_by_id = {item.source_field_id: item for item in dimensional.measure_candidates}
    facts: list[FactTableContract] = []
    relationships: list[RelationshipContract] = []
    role_playing: list[RolePlayingDimensionContract] = []
    for candidate in dimensional.fact_candidates:
        measures = []
        for source_id in candidate.measure_candidates:
            source = measure_by_id.get(source_id)
            if source is None:
                continue
            aggregation = (AggregationType.SUM if source.additivity == MeasureAggregationHint.ADDITIVE
                           and source.aggregation_risk is None else AggregationType.UNKNOWN)
            measures.append(MeasureContract(
                source_field_id=source_id, logical_name=_slug(source.name),
                prepared_type=_logical_type(fields.get(source_id)), aggregation_type=aggregation,
                additivity=source.additivity, grain_compatibility=source.grain_compatibility,
                aggregation_risk=source.aggregation_risk,
                quality_dependencies=source.quality_dependencies,
                nullable=_nullable(fields.get(source_id))))
            if source.aggregation_risk:
                warnings.append(ModelingWarning(
                    warning_id=_id("warning", "aggregation", candidate.fact_candidate_id, source_id),
                    warning_type=WarningType.AGGREGATION_RISK, severity=WarningSeverity.ERROR,
                    message=source.measure_modeling_warning or source.aggregation_risk.description,
                    related_ids=[candidate.fact_candidate_id, source_id]))
        degenerates = [DegenerateDimensionContract(
            source_field_id=source_id, logical_name=_slug(fields[source_id].technical_name if source_id in fields else source_id),
            reason="Identificador validado como degenerado; permanece logicamente na fato.",
            quality_dependencies=[q for q in candidate.quality_dependencies if q.source_field_id == source_id])
            for source_id in candidate.degenerate_dimensions]
        attributes = [FactAttributeContract(
            source_field_id=source_id,
            logical_name=_slug(fields[source_id].technical_name if source_id in fields else source_id),
            type=_logical_type(fields.get(source_id)), reason="Campo validado como FACT_ATTRIBUTE.",
            nullable=_nullable(fields.get(source_id))) for source_id in candidate.fact_attributes]
        foreign_keys: list[ForeignKeyContract] = []
        for dim_id in candidate.foreign_dimension_candidates:
            dimension = dimensions_by_id.get(dim_id)
            if dimension is None:
                continue
            role_sources = (next((d.role_playing_roles for d in dimensional.dimension_candidates
                                  if d.dimension_candidate_id == dim_id), []) or [None])
            source_fields = dimension.business_key_fields.fields or next(
                (d.source_fields for d in dimensional.dimension_candidates if d.dimension_candidate_id == dim_id), [])
            for role_name in role_sources:
                role_source = next((field for field in source_fields
                                    if role_name and fields.get(field) and fields[field].technical_name == role_name), None)
                mapping = [role_source] if role_source else source_fields
                fk_name = f"{_slug(role_name or dimension.logical_name.removeprefix('dim_'))}_sk"
                foreign = ForeignKeyContract(
                    logical_name=f"fk_{fact_names[candidate.fact_candidate_id]}_{_slug(role_name or dimension.logical_name)}",
                    fact_id=candidate.fact_candidate_id, dimension_id=dim_id, fact_fk_name=fk_name,
                    dimension_surrogate_key_name=dimension.surrogate_key_plan.name,
                    source_mapping_fields=mapping, cardinality=Cardinality.MANY_TO_ONE,
                    optionality=(_nullable(fields.get(mapping[0])) if mapping else Nullability.UNKNOWN),
                    role_name=role_name, conformed_reference=dimension.conformed_candidate)
                foreign_keys.append(foreign)
                relationship = RelationshipContract(
                    relationship_id=_id("rel", candidate.fact_candidate_id, dim_id, role_name or "base"),
                    source_table=candidate.fact_candidate_id, target_table=dim_id,
                    source_fields=mapping, target_fields=[dimension.surrogate_key_plan.name],
                    fact_fk=fk_name, dimension_key=dimension.surrogate_key_plan.name,
                    cardinality=Cardinality.MANY_TO_ONE, optionality=foreign.optionality,
                    role_name=role_name,
                    evidence=["Relação deriva das dimensões relacionadas validadas na Effective Dimensional Discovery."])
                if len(relationships) < config.max_relationships:
                    relationships.append(relationship)
                if role_name:
                    role_playing.append(RolePlayingDimensionContract(
                        base_dimension_id=dim_id, role_name=role_name,
                        source_field_id=mapping[0] if mapping else role_name, fact_fk_name=fk_name,
                        relationship_name=relationship.relationship_id))
        if candidate.fact_type.value.endswith("SNAPSHOT"):
            temporal = any(fields.get(field) and fields[field].effective_semantic_role.value in
                           {"date", "time_component"} for field in candidate.grain_fields)
            if not temporal:
                warnings.append(ModelingWarning(
                    warning_id=_id("warning", "grain", candidate.fact_candidate_id),
                    warning_type=WarningType.GRAIN_MISMATCH, severity=WarningSeverity.BLOCKER,
                    message="Snapshot exige componente temporal explícito no grão validado.",
                    related_ids=[candidate.fact_candidate_id], blocker=True))
        facts.append(FactTableContract(
            fact_id=candidate.fact_candidate_id, logical_name=fact_names[candidate.fact_candidate_id],
            human_readable_name=candidate.human_readable_name, fact_type=candidate.fact_type,
            process=candidate.process, event=candidate.event,
            grain_description=candidate.grain_description, grain_fields=candidate.grain_fields,
            surrogate_key_plan=SurrogateKeyPlan(name=f"{fact_names[candidate.fact_candidate_id].removeprefix('fact_')}_fact_sk"),
            degenerate_identifiers=degenerates, measures=measures, foreign_keys=foreign_keys,
            fact_attributes=attributes, quality_dependencies=candidate.quality_dependencies,
            aggregation_risks=candidate.aggregation_risks))

    bridges: list[BridgeTableCandidate] = []
    for index, left in enumerate(dimensions):
        for right in dimensions[index + 1:]:
            many, evidence = _many_to_many(dataset, left.business_key_fields.fields,
                                           right.business_key_fields.fields)
            if many and len(bridges) < config.max_bridge_candidates:
                bridge = BridgeTableCandidate(
                    bridge_id=_id("bridge", left.dimension_id, right.dimension_id),
                    left_entity=left.dimension_id, right_entity=right.dimension_id,
                    reason="Cardinalidade many-to-many observada entre business keys dimensionais.",
                    cardinality_evidence=evidence)
                bridges.append(bridge)
                warnings.append(ModelingWarning(
                    warning_id=_id("warning", "m2m", bridge.bridge_id),
                    warning_type=WarningType.MANY_TO_MANY_RELATIONSHIP,
                    severity=WarningSeverity.ERROR, message=bridge.reason,
                    related_ids=[left.dimension_id, right.dimension_id]))

    ignored = [d.source_field_id for d in dimensional.field_decisions
               if d.effective_modeling_role == ModelingRole.IGNORED_FOR_ANALYTICS]
    unresolved = [d.source_field_id for d in dimensional.field_decisions
                  if d.effective_modeling_role == ModelingRole.UNRESOLVED]
    warnings.extend(ModelingWarning(
        warning_id=_id("warning", "unresolved", field), warning_type=WarningType.UNRESOLVED_FIELD,
        severity=WarningSeverity.WARNING, message=f"Campo {field} permanece UNRESOLVED.", related_ids=[field])
        for field in unresolved)
    warnings = warnings[:config.max_warnings]
    lineage = StarSchemaLineage(
        source_document_id=dataset.source_document_id, analysis_id=dataset.analysis_id,
        prepared_dataset_id=dataset.prepared_dataset_id, prepared_dataset_version=dataset.version,
        prepared_dataset_fingerprint=dataset.fingerprint, grain_definition_id=grain.grain_id,
        grain_version=grain.version, dimensional_discovery_id=dimensional.validation_id,
        dimensional_discovery_version=dimensional.version)
    contract = StarSchemaContract(
        contract_id=str(uuid4()), analysis_id=dataset.analysis_id,
        source_document_id=dataset.source_document_id, prepared_dataset_id=dataset.prepared_dataset_id,
        prepared_dataset_version=dataset.version, grain_definition_id=grain.grain_id,
        grain_version=grain.version, dimensional_discovery_id=dimensional.validation_id,
        dimensional_discovery_version=dimensional.version, version=version,
        status=ContractStatus.NEEDS_VALIDATION,
        schema_name_suggestion=f"star_{_slug(grain.effective_process or grain.effective_event or 'analytics')}",
        fact_tables=facts, dimension_tables=dimensions, relationships=relationships,
        role_playing_relationships=role_playing,
        conformed_dimension_candidates=[ConformedDimensionContractCandidate(
            dimension_id=d.dimension_id, business_concept_id=d.business_concept_id,
            business_key=d.business_key_fields,
            compatibility_requirements=["Business key e semântica devem ser compatíveis antes da reutilização."])
            for d in dimensions if d.conformed_candidate], bridge_candidates=bridges,
        warnings=warnings, unresolved_items=list(unresolved), ignored_fields=ignored,
        unresolved_fields=unresolved, lineage=lineage)
    tracked = {decision.source_field_id for decision in dimensional.field_decisions}
    validations = [
        ValidationResult(rule="FACT_GRAIN", passed=all(f.grain_fields or f.grain_description for f in facts), message="Toda fato possui grão."),
        ValidationResult(rule="DIMENSION_SURROGATE_KEY", passed=all(d.surrogate_key_plan for d in dimensions), message="Toda dimensão possui surrogate key plan."),
        ValidationResult(rule="FOREIGN_KEY_REFERENCES", passed=all(r.target_table in dimensions_by_id for r in relationships), message="FKs lógicas referenciam dimensões existentes."),
        ValidationResult(rule="TECHNICAL_KEY_EXCLUSION", passed=all("source_row_id" not in d.business_key_fields.fields for d in dimensions), message="Chaves técnicas não são business keys."),
        ValidationResult(rule="FIELD_COVERAGE", passed=len(tracked) == dataset.field_count, message="Todos os campos permanecem rastreáveis."),
    ]
    coverage = FieldCoverage(
        total_fields=dataset.field_count, tracked_fields=len(tracked),
        percentage=round(100 * len(tracked) / dataset.field_count, 2) if dataset.field_count else 100,
        classifications=dict(Counter(d.effective_modeling_role.value for d in dimensional.field_decisions)))
    return StarSchemaContractReport(
        report_id=str(uuid4()), contract=contract, validation_results=validations,
        warnings=warnings, field_coverage=coverage, lineage=lineage,
        readiness=ReadinessStatus.NOT_READY, version=version,
        max_relationships=config.max_relationships,
        max_bridge_candidates=config.max_bridge_candidates, max_warnings=config.max_warnings)
