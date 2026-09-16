"""Bounded dimensional hypotheses based only on effective upstream contracts."""

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from core.dimensional.models import (
    CandidateStatus, ConformedDimensionCandidate, DimensionCandidate, DimensionRole,
    DimensionalDiscoveryReport, FactCandidate, FactType, FieldModelingDecision,
    MeasureCandidate, ModelingRole, ProposalStatus, RecommendedStructure,
)
from core.grain.models import (
    GrainClassification, GrainDefinition, GrainDiscoveryReport, GrainReadiness,
    MeasureAggregationHint, ObservedFunctionalDependency, QualityDependency,
)
from core.prepared.models import PreparedDataset, PreparedField
from core.profiling.models import SemanticRole
from core.quality.models import FieldApplicability, FieldQualityStatus, IdentifierConstraint


@dataclass(frozen=True)
class DimensionalDiscoveryConfig:
    max_dimension_candidates: int = 50
    max_fact_candidates: int = 10
    max_low_cardinality: int = 12
    min_fd_confidence: float = .95


_TECHNICAL = {"source_row_id", "row_id", "technical_key"}
_PERCENT_TOKENS = {"percent", "percentage", "percentual", "pct", "ratio", "taxa"}
_BALANCE_TOKENS = {"balance", "saldo", "stock", "estoque"}
_FLAG_TOKENS = {"flag", "status", "indicator", "indicador", "boolean", "bool"}
_DATE_ROLE_SUFFIXES = ("date", "data", "dt")


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", value.casefold()).strip("_")
    return text or "candidate"


def _cid(prefix: str, *parts: str) -> str:
    return prefix + ":" + hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _cardinality(dataset: PreparedDataset, field_ids: list[str]) -> int:
    values = {tuple((type(row.values.get(fid)).__name__, repr(row.values.get(fid)))
                    for fid in field_ids) for row in dataset.rows
              if all(row.values.get(fid) is not None for fid in field_ids)}
    return len(values)


def _quality_dependencies(dataset: PreparedDataset, fields: list[str]) -> list[QualityDependency]:
    return [QualityDependency(
        source_field_id=issue.source_field_id, issue_id=issue.issue_id,
        issue_type=issue.issue_type.value, severity=issue.severity.value,
        affected_count=issue.affected_count,
        description=f"{issue.reason} ({issue.affected_count} ocorrência(s)).",
    ) for issue in dataset.unresolved_quality_issues if issue.source_field_id in fields]


def _field_map(dataset: PreparedDataset) -> dict[str, PreparedField]:
    return {field.source_field_id: field for field in dataset.schema_fields}


def _is_technical(field: PreparedField, constraints: dict[str, IdentifierConstraint]) -> bool:
    return (field.source_field_id.casefold() in _TECHNICAL
            or field.technical_name.casefold() in _TECHNICAL
            or constraints.get(field.source_field_id, IdentifierConstraint()).technical_key)


def _is_unevaluated(field: PreparedField) -> bool:
    return field.quality_status == FieldQualityStatus.NOT_EVALUATED


def _additivity(field: PreparedField, risk: Any) -> tuple[MeasureAggregationHint, str | None]:
    if risk:
        return (MeasureAggregationHint.REQUIRES_VALIDATION,
                "O valor parece estar repetido em várias linhas do grão atual. "
                "Somá-lo diretamente pode gerar dupla contagem.")
    tokens = set(re.split(r"[^a-z0-9]+", field.technical_name.casefold()))
    if tokens & _PERCENT_TOKENS:
        return MeasureAggregationHint.NON_ADDITIVE, None
    if tokens & _BALANCE_TOKENS:
        return MeasureAggregationHint.SEMI_ADDITIVE, None
    return MeasureAggregationHint.ADDITIVE, None


def _dimension_name(identifier: PreparedField) -> str:
    stem = re.sub(r"(?:_?(?:id|key|code|codigo|number|numero))$", "",
                  identifier.technical_name, flags=re.I).strip("_")
    return stem or identifier.technical_name


def _dimension_for_identifier(dataset: PreparedDataset, identifier: PreparedField,
                              fds: list[ObservedFunctionalDependency],
                              fields: dict[str, PreparedField], grain_fields: set[str],
                              *, conformed: bool = False) -> DimensionCandidate | None:
    dependencies = [fd for fd in fds if fd.determinant == [identifier.source_field_id]
                    and fd.confidence >= .95 and fd.dependent in fields
                    and fd.dependent != identifier.source_field_id]
    attrs = [fd.dependent for fd in dependencies
             if fields[fd.dependent].effective_semantic_role in {
                 SemanticRole.DESCRIPTION, SemanticRole.CATEGORY, SemanticRole.CODE,
                 SemanticRole.DATE, SemanticRole.TIME_COMPONENT, SemanticRole.BOOLEAN}]
    # An event identifier in the grain without its own attributes is degenerate.
    if identifier.source_field_id in grain_fields and not attrs:
        return None
    name = _dimension_name(identifier)
    dim_id = _cid("dim", identifier.source_field_id)
    qdeps = _quality_dependencies(dataset, [identifier.source_field_id] + attrs)
    confidence = max(.35, .84 - .08 * bool(qdeps))
    evidence = ["Identificador semântico elegível como business key candidate."]
    evidence.extend(f"FD observada: {identifier.source_field_id} → {fd.dependent}; "
                    f"{fd.violations} violação(ões)." for fd in dependencies)
    if not attrs:
        evidence.append("Candidato conservador sem atributos associados; requer validação.")
    return DimensionCandidate(
        dimension_candidate_id=dim_id, name=name,
        human_readable_name=name.replace("_", " ").title(),
        source_fields=[identifier.source_field_id] + attrs,
        business_identifier_fields=[identifier.source_field_id],
        business_key_candidates=[identifier.source_field_id], descriptive_attributes=attrs,
        cardinality=_cardinality(dataset, [identifier.source_field_id]),
        dependency_evidence=evidence[1:], conformed_candidate=conformed,
        role=(DimensionRole.CONFORMED_DIMENSION_CANDIDATE if conformed
              else DimensionRole.REGULAR_DIMENSION),
        suggested_surrogate_key_name=f"{_slug(name)}_sk", confidence=confidence,
        evidence=evidence, quality_dependencies=qdeps,
        status=CandidateStatus.REQUIRES_VALIDATION)


def _date_dimension(dataset: PreparedDataset, date_fields: list[PreparedField]) -> DimensionCandidate | None:
    if not date_fields:
        return None
    roles = [field.technical_name for field in date_fields]
    role_playing = len(date_fields) > 1
    return DimensionCandidate(
        dimension_candidate_id=_cid("dim", "date", *sorted(f.source_field_id for f in date_fields)),
        name="date", human_readable_name="Date", source_fields=[f.source_field_id for f in date_fields],
        descriptive_attributes=[f.source_field_id for f in date_fields],
        cardinality=max((_cardinality(dataset, [f.source_field_id]) for f in date_fields), default=0),
        conformed_candidate=True,
        role=(DimensionRole.ROLE_PLAYING_DIMENSION_CANDIDATE if role_playing
              else DimensionRole.CONFORMED_DIMENSION_CANDIDATE),
        role_playing_roles=roles,
        suggested_surrogate_key_name="date_sk", confidence=.78 if role_playing else .68,
        evidence=["Campos DATE/TIME_COMPONENT formam um único conceito temporal potencial.",
                  "Papéis temporais distintos serão validados antes da criação de FKs."],
        quality_dependencies=_quality_dependencies(dataset, [f.source_field_id for f in date_fields]),
        status=CandidateStatus.REQUIRES_VALIDATION)


def _grain_groups(grain: GrainDefinition) -> list[list[str]]:
    if grain.grain_type != GrainClassification.MULTI_GRAIN:
        return [list(grain.grain_fields)]
    if grain.grain_groups:
        return [list(group) for group in grain.grain_groups]
    # A validated MULTI_GRAIN without explicit groups is kept separated instead
    # of being forced into one fact; each validated key is a conservative fact.
    return [[field] for field in grain.grain_fields]


def discover_dimensions(dataset: PreparedDataset, grain: GrainDefinition,
                        grain_report: GrainDiscoveryReport,
                        identifier_constraints: dict[str, IdentifierConstraint] | None = None,
                        *, config: DimensionalDiscoveryConfig | None = None,
                        version: int = 1) -> DimensionalDiscoveryReport:
    """Build an observed proposal; source rows are read but never mutated."""
    config = config or DimensionalDiscoveryConfig()
    constraints = identifier_constraints or {}
    if grain.status != GrainReadiness.READY_FOR_DIMENSIONAL_MODELING:
        raise ValueError("Effective Grain não está READY_FOR_DIMENSIONAL_MODELING.")
    if grain.grain_type in {GrainClassification.AMBIGUOUS_GRAIN,
                            GrainClassification.INSUFFICIENT_EVIDENCE}:
        raise ValueError("Grão ambíguo ou insuficiente não libera descoberta dimensional.")
    if (grain.prepared_dataset_id != dataset.prepared_dataset_id
            or grain.prepared_dataset_version != dataset.version
            or grain.prepared_dataset_fingerprint != dataset.fingerprint
            or grain.grain_discovery_report_id != grain_report.grain_discovery_report_id):
        raise ValueError("Dependências de linhagem incompatíveis; a proposta não pode ser reutilizada.")

    fields = _field_map(dataset)
    grain_field_set = set(grain.grain_fields)
    eligible = [f for f in dataset.schema_fields if not _is_technical(f, constraints)]
    evaluated = [f for f in eligible if not _is_unevaluated(f)]
    risks = {risk.measure_field_id: risk for risk in grain_report.aggregation_risks}
    measures: list[MeasureCandidate] = []
    for field in evaluated:
        if field.effective_semantic_role != SemanticRole.MEASURE:
            continue
        hint, warning = _additivity(field, risks.get(field.source_field_id))
        qdeps = _quality_dependencies(dataset, [field.source_field_id])
        measures.append(MeasureCandidate(
            source_field_id=field.source_field_id, name=field.source_name,
            effective_semantic_role=field.effective_semantic_role,
            prepared_type=field.prepared_type, aggregation_hint=hint, additivity=hint,
            grain_compatibility=True, confidence=max(.4, .9 - .08 * bool(qdeps) - .12 * bool(warning)),
            evidence=["Effective Semantic Role validado é MEASURE."],
            aggregation_risk=risks.get(field.source_field_id), measure_modeling_warning=warning,
            quality_dependencies=qdeps,
            status=CandidateStatus.REQUIRES_VALIDATION if warning else CandidateStatus.PROPOSED))

    identifiers = [f for f in evaluated if f.effective_semantic_role in
                   {SemanticRole.IDENTIFIER, SemanticRole.CODE}]
    multi = grain.grain_type == GrainClassification.MULTI_GRAIN
    dimensions: list[DimensionCandidate] = []
    for identifier in identifiers:
        dim = _dimension_for_identifier(dataset, identifier, grain_report.functional_dependencies,
                                        fields, grain_field_set, conformed=multi)
        if dim:
            dimensions.append(dim)
    date_dim = _date_dimension(dataset, [f for f in evaluated if f.effective_semantic_role in
                                         {SemanticRole.DATE, SemanticRole.TIME_COMPONENT}])
    if date_dim:
        dimensions.append(date_dim)

    # A junk candidate is only evidence, never an automatic physical grouping.
    low = [f for f in evaluated if f.effective_semantic_role in {SemanticRole.BOOLEAN, SemanticRole.CATEGORY}
           and (_cardinality(dataset, [f.source_field_id]) <= config.max_low_cardinality)
           and (f.effective_semantic_role == SemanticRole.BOOLEAN
                or set(re.split(r"[^a-z0-9]+", f.technical_name.casefold())) & _FLAG_TOKENS)]
    if len(low) >= 2:
        ids = [f.source_field_id for f in low]
        dimensions.append(DimensionCandidate(
            dimension_candidate_id=_cid("dim", "junk", *ids), name="junk_attributes",
            human_readable_name="Low-cardinality attributes", source_fields=ids,
            descriptive_attributes=ids, cardinality=_cardinality(dataset, ids),
            role=DimensionRole.JUNK_DIMENSION_CANDIDATE, confidence=.52,
            evidence=["Múltiplas flags/status de baixa cardinalidade; agrupamento não automático."],
            quality_dependencies=_quality_dependencies(dataset, ids),
            status=CandidateStatus.REQUIRES_VALIDATION))

    truncated = len(dimensions) > config.max_dimension_candidates
    dimensions = dimensions[:config.max_dimension_candidates]
    dimension_fields = {fid: d.dimension_candidate_id for d in dimensions for fid in d.source_fields}
    measure_ids = {m.source_field_id for m in measures}
    degenerate = {f.source_field_id for f in identifiers
                  if f.source_field_id in grain_field_set and f.source_field_id not in dimension_fields}
    decisions: list[FieldModelingDecision] = []
    for field in dataset.schema_fields:
        target = None
        if _is_technical(field, constraints):
            role, confidence, evidence = ModelingRole.IGNORED_FOR_ANALYTICS, 1.0, ["Chave técnica excluída da modelagem analítica."]
        elif _is_unevaluated(field):
            role, confidence, evidence = ModelingRole.UNRESOLVED, .2, ["Campo NOT_EVALUATED/sem evidência aplicável não sustenta hipótese forte."]
        elif field.source_field_id in measure_ids:
            role, confidence, evidence = ModelingRole.MEASURE, .9, ["Candidato a medida semanticamente validado."]
        elif field.source_field_id in degenerate:
            role, confidence, evidence = ModelingRole.DEGENERATE_IDENTIFIER, .72, ["Identifica o evento/grão e não possui atributos próprios suficientes."]
        elif field.source_field_id in dimension_fields:
            role, confidence, evidence = ModelingRole.DIMENSION_ATTRIBUTE, .78, ["Associado a candidato dimensional por semântica/FD/cardinalidade."]
            target = dimension_fields[field.source_field_id]
        elif field.effective_semantic_role in {SemanticRole.DESCRIPTION, SemanticRole.CATEGORY, SemanticRole.CODE}:
            role, confidence, evidence = ModelingRole.FACT_ATTRIBUTE, .48, ["Permanece na fato até haver evidência dimensional suficiente."]
        else:
            role, confidence, evidence = ModelingRole.UNRESOLVED, .3, ["Conhecimento efetivo insuficiente para classificação forte."]
        decisions.append(FieldModelingDecision(
            source_field_id=field.source_field_id, effective_semantic_role=field.effective_semantic_role,
            observed_modeling_role=role, effective_modeling_role=role, modeling_role=role,
            target_candidate_id=target, confidence=confidence, evidence=evidence,
            requires_validation=role in {ModelingRole.UNRESOLVED, ModelingRole.FACT_ATTRIBUTE}))

    groups = _grain_groups(grain)[:config.max_fact_candidates]
    facts: list[FactCandidate] = []
    for index, group in enumerate(groups, 1):
        fact_measures = [m.source_field_id for m in measures]
        fact_type = FactType.FACTLESS if not fact_measures else FactType.TRANSACTION
        fact_name = _slug(grain.effective_event or grain.effective_process or "event")
        if len(groups) > 1:
            fact_name += f"_{index}"
        facts.append(FactCandidate(
            fact_candidate_id=_cid("fact", grain.grain_id, *group),
            prepared_dataset_id=dataset.prepared_dataset_id, grain_definition_id=grain.grain_id,
            name=f"fact_{fact_name}", human_readable_name=f"Fact {fact_name.replace('_', ' ').title()}",
            process=grain.effective_process, event=grain.effective_event, fact_type=fact_type,
            grain_description=grain.effective_grain_description, grain_fields=group,
            measure_candidates=fact_measures,
            degenerate_dimensions=[fid for fid in group if fid in degenerate],
            foreign_dimension_candidates=[d.dimension_candidate_id for d in dimensions
                                          if d.role != DimensionRole.JUNK_DIMENSION_CANDIDATE],
            fact_attributes=[d.source_field_id for d in decisions
                             if d.effective_modeling_role == ModelingRole.FACT_ATTRIBUTE],
            confidence=max(.4, min(.9, grain.confidence - .05 * bool(risks))),
            evidence=["FactCandidate deriva diretamente do Effective Grain validado.",
                      "FACTLESS preserva eventos mesmo sem medida numérica." if fact_type == FactType.FACTLESS
                      else "Tipo TRANSACTION é proposta conservadora sujeita a validação."],
            aggregation_risks=list(grain_report.aggregation_risks),
            quality_dependencies=list({q.issue_id: q for q in
                [dep for m in measures for dep in m.quality_dependencies]}.values()),
            status=CandidateStatus.REQUIRES_VALIDATION))

    unresolved = [d.source_field_id for d in decisions
                  if d.effective_modeling_role == ModelingRole.UNRESOLVED]
    conformed = [ConformedDimensionCandidate(
        dimension_candidate_id=d.dimension_candidate_id, business_concept_id=d.business_concept_id,
        evidence=d.evidence) for d in dimensions if d.conformed_candidate]
    qdeps = list({q.issue_id: q for q in [dep for d in dimensions for dep in d.quality_dependencies]
                  + [dep for m in measures for dep in m.quality_dependencies]}.values())
    return DimensionalDiscoveryReport(
        report_id=str(uuid4()), source_document_id=dataset.source_document_id,
        prepared_dataset_id=dataset.prepared_dataset_id, prepared_dataset_version=dataset.version,
        prepared_dataset_fingerprint=dataset.fingerprint, grain_definition_id=grain.grain_id,
        grain_version=grain.version, analysis_id=dataset.analysis_id,
        status=ProposalStatus.NEEDS_VALIDATION, fact_candidates=facts,
        dimension_candidates=dimensions, measure_candidates=measures, field_decisions=decisions,
        conformed_candidates=conformed,
        role_playing_candidates=[d.dimension_candidate_id for d in dimensions
                                 if d.role == DimensionRole.ROLE_PLAYING_DIMENSION_CANDIDATE],
        junk_candidates=[d.dimension_candidate_id for d in dimensions
                         if d.role == DimensionRole.JUNK_DIMENSION_CANDIDATE],
        aggregation_risks=grain_report.aggregation_risks, quality_dependencies=qdeps,
        unresolved_fields=unresolved,
        recommended_structure=RecommendedStructure(
            possible_main_fact=facts[0].name if facts else None,
            grain=grain.effective_grain_description,
            measures=[m.name for m in measures], dimensions=[d.human_readable_name for d in dimensions],
            degenerate_dimensions=sorted(degenerate),
            conformed_candidates=[d.human_readable_name for d in dimensions if d.conformed_candidate],
            risks=[r.description for r in grain_report.aggregation_risks], unresolved_fields=unresolved),
        max_fact_candidates=config.max_fact_candidates,
        max_dimension_candidates=config.max_dimension_candidates,
        candidates_truncated=truncated or len(_grain_groups(grain)) > config.max_fact_candidates,
        version=version)
