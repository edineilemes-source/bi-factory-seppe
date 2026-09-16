"""Bounded, deterministic discovery over effective Prepared Dataset values."""

import hashlib
import itertools
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Mapping
from uuid import uuid4

from core.grain.models import (
    AggregationRisk, CandidateStatus, EventCandidate, GrainCandidate,
    GrainClassification, GrainDiscoveryReport, GrainDiscoveryStatus,
    IdentifierHierarchy, MeasureAggregationHint, ObservedFunctionalDependency,
    ProcessCandidate, QualityDependency,
)
from core.prepared.models import PreparedDataset, PreparedField
from core.profiling.models import SemanticRole
from core.quality.models import IdentifierConstraint, QualityIssueType


@dataclass(frozen=True)
class GrainDiscoveryConfig:
    max_candidate_fields: int = 3
    max_candidates: int = 50
    max_identifier_fields: int = 12
    min_confidence: float = .45
    min_uniqueness_for_strong_candidate: float = .95
    ambiguity_margin: float = .04
    max_functional_dependencies: int = 100
    min_global_coverage: float = .50
    min_complete_rows: int = 100


_GENERIC_TOKENS = {
    "id", "identifier", "identificador", "codigo", "code", "numero", "number",
    "data", "date", "valor", "value", "total", "quantidade", "quantity",
    "descricao", "description", "nome", "name", "status", "tipo", "type",
}


def _key(value: Any) -> tuple[str, str]:
    return type(value).__name__, repr(value)


def _field_values(dataset: PreparedDataset, field_id: str) -> list[Any]:
    return [row.values.get(field_id) for row in dataset.rows]


def _quality_dependencies(dataset: PreparedDataset, fields: list[str]) -> list[QualityDependency]:
    relevant = {
        QualityIssueType.IDENTIFIER_INCONSISTENCY.value,
        QualityIssueType.INVALID_TYPE.value,
        QualityIssueType.FORMAT_INCONSISTENCY.value,
        QualityIssueType.MISSING_VALUE.value,
        QualityIssueType.PLACEHOLDER_VALUE.value,
    }
    return [QualityDependency(
        source_field_id=issue.source_field_id, issue_id=issue.issue_id,
        issue_type=issue.issue_type.value, severity=issue.severity.value,
        affected_count=issue.affected_count,
        description=(f"A evidência de cardinalidade pode ser afetada por "
                     f"{issue.affected_count} ocorrência(s) de {issue.issue_type.value}."),
    ) for issue in dataset.unresolved_quality_issues
      if issue.source_field_id in fields and issue.issue_type.value in relevant]


def _candidate(dataset: PreparedDataset, fields: list[PreparedField],
               process: str | None, event: str | None,
               constraints: Mapping[str, IdentifierConstraint]) -> GrainCandidate:
    ids = [field.source_field_id for field in fields]
    tuples = [tuple(_key(row.values.get(field_id)) for field_id in ids)
              for row in dataset.rows]
    missing = [any(row.values.get(field_id) is None for field_id in ids)
               for row in dataset.rows]
    complete = [value for value, is_missing in zip(tuples, missing) if not is_missing]
    distinct = len(set(complete))
    row_count = len(tuples)
    duplicate_count = max(0, len(complete) - distinct)
    uniqueness = distinct / len(complete) if complete else 0
    coverage = len(complete) / row_count if row_count else 0
    null_ratio = sum(missing) / row_count if row_count else 1
    optional = all(field.requirement.value in {"optional", "conditional", "unknown"}
                   for field in fields)
    null_weight = .05 if optional else .2
    stability = coverage
    semantic_strength = sum(1 if field.effective_semantic_role == SemanticRole.IDENTIFIER
                            else .7 for field in fields) / len(fields)
    declared_support = any(constraints.get(field.source_field_id, IdentifierConstraint()).business_key
                           or constraints.get(field.source_field_id, IdentifierConstraint()).grain_declared
                           for field in fields)
    size_penalty = .025 * (len(fields) - 1)
    support = min(1.0, len(complete) / 100)
    confidence = (0 if not complete else max(0, min(1, .42 * uniqueness + .33 * coverage
                  + .10 * stability + .10 * semantic_strength + .05 * support
                  + (.02 if declared_support else 0) - size_penalty)))
    evidence = [
        f"{distinct} combinação(ões) distinta(s) em {len(complete)} linha(s) completas.",
        f"Unicidade condicional de {100 * uniqueness:.2f}% nas linhas completas.",
        f"Cobertura de {100 * coverage:.2f}% sobre o dataset total.",
    ]
    if len(fields) > 1:
        evidence.append("A combinação composta aumenta a especificidade observada.")
    if declared_support:
        evidence.append("Há IdentifierConstraint explícita apoiando campo(s) da combinação.")
    counter = []
    if duplicate_count:
        counter.append(f"{duplicate_count} linha(s) ainda repetem a combinação candidata.")
    if null_ratio:
        counter.append(f"{100 * null_ratio:.2f}% das linhas não possuem todos os campos; "
                       "campos opcionais/condicionais não foram descartados automaticamente.")
    compatibility = ("EVENT_SUBSET_ONLY" if coverage < .5 else
                     "GLOBAL_CANDIDATE_NOT_UNIQUE" if uniqueness < .95 else
                     "GLOBAL_SOURCE_GRAIN_COMPATIBLE")
    if coverage < .5:
        counter.append("Cobertura insuficiente para representar o grão global da fonte.")
    if not complete:
        counter.append("Não existem linhas completas; não há evidência estatística observada.")
    digest = hashlib.sha256("|".join(ids).encode()).hexdigest()[:16]
    names = " + ".join(field.source_name for field in fields)
    return GrainCandidate(
        candidate_id=f"gc:{digest}",
        human_readable_description=f"Uma linha pode representar uma ocorrência identificada por {names}.",
        candidate_fields=ids, inferred_process=process, inferred_event=event,
        row_count=row_count, complete_row_count=len(complete), distinct_count=distinct,
        duplicate_count=duplicate_count, uniqueness_ratio=round(uniqueness, 6),
        coverage_ratio=round(coverage, 6), null_ratio=round(null_ratio, 6),
        stability=round(stability, 6), confidence=round(confidence, 6),
        semantic_evidence_score=round(semantic_strength, 6),
        business_process_compatibility=compatibility,
        evidence=evidence, counter_evidence=counter,
        quality_dependencies=_quality_dependencies(dataset, ids),
    )


def _lexical_hypotheses(fields: list[PreparedField]) -> tuple[list[ProcessCandidate], list[EventCandidate]]:
    tokens: Counter[str] = Counter()
    token_fields: defaultdict[str, list[str]] = defaultdict(list)
    for field in fields:
        found = [part for part in re.split(r"[^a-zA-ZÀ-ÿ0-9]+", field.technical_name.casefold())
                 if len(part) > 2 and part not in _GENERIC_TOKENS and not part.isdigit()]
        for token in set(found):
            tokens[token] += 1
            token_fields[token].append(field.source_field_id)
    processes = [ProcessCandidate(
        name=token, confidence=round(min(.75, .3 + count / max(len(fields), 1)), 4),
        evidence=[f"Termo recorrente em {count} nome(s) de campo; hipótese lexical, não regra de domínio."],
    ) for token, count in tokens.most_common(3)]
    date_fields = [field for field in fields if field.effective_semantic_role == SemanticRole.DATE]
    events: list[EventCandidate] = []
    for field in date_fields[:5]:
        parts = [p for p in re.split(r"[^a-zA-ZÀ-ÿ0-9]+", field.technical_name.casefold())
                 if p not in _GENERIC_TOKENS and len(p) > 2]
        name = parts[0] if parts else field.source_name
        events.append(EventCandidate(
            name=name, confidence=.45, source_fields=[field.source_field_id],
            evidence=["Campo de data fornece sinal de evento, sujeito a validação humana."],
        ))
    return processes, events


def _functional_dependencies(dataset: PreparedDataset, fields: list[PreparedField],
                             limit: int) -> tuple[list[ObservedFunctionalDependency], list[IdentifierHierarchy]]:
    dependencies: list[ObservedFunctionalDependency] = []
    hierarchies: list[IdentifierHierarchy] = []
    for left, right in itertools.permutations(fields, 2):
        if len(dependencies) >= limit:
            break
        mapping: defaultdict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
        support = 0
        for row in dataset.rows:
            a, b = row.values.get(left.source_field_id), row.values.get(right.source_field_id)
            if a is not None and b is not None:
                mapping[_key(a)].add(_key(b)); support += 1
        if not support:
            continue
        violating_keys = {key for key, values in mapping.items() if len(values) > 1}
        violations = sum(1 for row in dataset.rows
                         if row.values.get(left.source_field_id) is not None
                         and _key(row.values.get(left.source_field_id)) in violating_keys)
        confidence = max(0, 1 - violations / support)
        if confidence >= .95:
            dependencies.append(ObservedFunctionalDependency(
                determinant=[left.source_field_id], dependent=right.source_field_id,
                support=support, violations=violations, confidence=round(confidence, 6)))
            left_distinct = len({_key(v) for v in _field_values(dataset, left.source_field_id) if v is not None})
            right_distinct = len({_key(v) for v in _field_values(dataset, right.source_field_id) if v is not None})
            if confidence == 1 and left_distinct > right_distinct:
                hierarchies.append(IdentifierHierarchy(
                    parent=right.source_field_id, child=left.source_field_id,
                    evidence="Dependência funcional observada e maior cardinalidade no campo filho.",
                    confidence=1))
    return dependencies, hierarchies


def _aggregation_risks(dataset: PreparedDataset, identifiers: list[PreparedField],
                       measures: list[PreparedField], candidate_fields: list[str]) -> list[AggregationRisk]:
    risks: list[AggregationRisk] = []
    for measure in measures:
        for identifier in identifiers:
            groups: defaultdict[tuple[str, str], list[Any]] = defaultdict(list)
            for row in dataset.rows:
                key, value = row.values.get(identifier.source_field_id), row.values.get(measure.source_field_id)
                if key is not None and value is not None:
                    groups[_key(key)].append(value)
            repeated = [values for values in groups.values()
                        if len(values) > 1 and len({_key(v) for v in values}) == 1]
            if repeated:
                identity = f"{measure.source_field_id}|{identifier.source_field_id}"
                risks.append(AggregationRisk(
                    risk_id="ar:" + hashlib.sha256(identity.encode()).hexdigest()[:16],
                    measure_field_id=measure.source_field_id,
                    repeated_at_fields=[identifier.source_field_id],
                    candidate_grain_fields=candidate_fields,
                    affected_groups=len(repeated), affected_rows=sum(map(len, repeated)),
                    aggregation_hint=MeasureAggregationHint.REQUIRES_GRAIN_VALIDATION,
                    description=(f"{measure.source_name} repete o mesmo valor em várias linhas de "
                                 f"{identifier.source_name}; somar diretamente poderá duplicar valores."),
                    evidence=["Constância observada dentro de grupos repetidos; nenhuma correção aplicada."],
                ))
    return risks


def _multi_grain_signal(dataset: PreparedDataset, identifiers: list[PreparedField],
                        measures: list[PreparedField]) -> bool:
    if len(dataset.rows) < 4 or len(identifiers) < 2:
        return False
    # Mutually exclusive identifier populations are a strong, generic signal of
    # mixed event structures. Null alone never decides: both groups need support.
    for left, right in itertools.combinations(identifiers, 2):
        if left.requirement.value in {"optional", "conditional"} or right.requirement.value in {"optional", "conditional"}:
            continue
        left_only = right_only = together = 0
        for row in dataset.rows:
            a = row.values.get(left.source_field_id) is not None
            b = row.values.get(right.source_field_id) is not None
            left_only += a and not b; right_only += b and not a; together += a and b
        threshold = max(2, len(dataset.rows) // 5)
        if left_only >= threshold and right_only >= threshold and together == 0:
            return True
    # Distinct measure populations tied to different identifier populations.
    if len(measures) >= 2:
        patterns = Counter(tuple(row.values.get(m.source_field_id) is not None for m in measures)
                           for row in dataset.rows)
        substantial = [pattern for pattern, count in patterns.items()
                       if count >= max(2, len(dataset.rows) // 5) and any(pattern)]
        if len(substantial) >= 2 and any(not any(a and b for a, b in zip(x, y))
                                         for x, y in itertools.combinations(substantial, 2)):
            return True
    return False


def discover_grain(dataset: PreparedDataset,
                   identifier_constraints: Mapping[str, IdentifierConstraint] | None = None,
                   *, config: GrainDiscoveryConfig | None = None,
                   version: int = 1) -> GrainDiscoveryReport:
    """Discover bounded hypotheses; never silently validates a grain."""
    config = config or GrainDiscoveryConfig()
    constraints = identifier_constraints or {}
    fields = dataset.schema_fields
    eligible = [field for field in fields
                if field.effective_semantic_role in {SemanticRole.IDENTIFIER, SemanticRole.CODE}
                and field.source_field_id != "source_row_id"
                and field.technical_name != "source_row_id"
                and not constraints.get(field.source_field_id, IdentifierConstraint()).technical_key]
    # IdentifierConstraint from Sprint 2.1 has no technical_key flag; technical
    # keys are also excluded through FieldIdentity conventions and reserved names.
    eligible = eligible[:config.max_identifier_fields]
    measures = [field for field in fields if field.effective_semantic_role == SemanticRole.MEASURE]
    processes, events = _lexical_hypotheses(fields)
    process = processes[0].name if processes else None
    event = events[0].name if events else None
    candidates: list[GrainCandidate] = []
    theoretical = 0
    if eligible:
        for size in range(1, min(config.max_candidate_fields, len(eligible)) + 1):
            if size >= 3 and any(item.uniqueness_ratio >= config.min_uniqueness_for_strong_candidate
                                 and item.confidence >= config.min_confidence
                                 for item in candidates):
                break
            for combination in itertools.combinations(eligible, size):
                theoretical += 1
                if len(candidates) >= config.max_candidates:
                    break
                candidates.append(_candidate(dataset, list(combination), process, event, constraints))
            if len(candidates) >= config.max_candidates:
                break
    candidates.sort(key=lambda item: (-item.confidence, len(item.candidate_fields), item.candidate_id))
    globally_eligible = [item for item in candidates
                         if (item.complete_row_count or 0) > 0
                         and (item.coverage_ratio or 0) >= config.min_global_coverage
                         and item.confidence >= config.min_confidence]
    strong = [item for item in globally_eligible
              if item.uniqueness_ratio >= config.min_uniqueness_for_strong_candidate
              and item.confidence >= config.min_confidence]
    recommended = globally_eligible[0] if globally_eligible else None
    multi = _multi_grain_signal(dataset, eligible, measures)
    if not candidates:
        classification = GrainClassification.INSUFFICIENT_EVIDENCE
        status = GrainDiscoveryStatus.INSUFFICIENT_EVIDENCE
    elif multi:
        classification = GrainClassification.MULTI_GRAIN
        status = GrainDiscoveryStatus.NEEDS_VALIDATION
    elif len(strong) >= 2 and abs(strong[0].confidence - strong[1].confidence) <= config.ambiguity_margin:
        # Nested supersets of the same unique candidate are not independent ambiguity.
        a, b = set(strong[0].candidate_fields), set(strong[1].candidate_fields)
        if a < b or b < a:
            classification = GrainClassification.SINGLE_GRAIN
        else:
            classification = GrainClassification.AMBIGUOUS_GRAIN
        status = GrainDiscoveryStatus.NEEDS_VALIDATION if classification == GrainClassification.SINGLE_GRAIN else GrainDiscoveryStatus.AMBIGUOUS
    elif recommended and recommended.confidence >= config.min_confidence:
        classification = GrainClassification.SINGLE_GRAIN
        status = GrainDiscoveryStatus.NEEDS_VALIDATION
    else:
        classification = GrainClassification.INSUFFICIENT_EVIDENCE
        status = GrainDiscoveryStatus.INSUFFICIENT_EVIDENCE
    if recommended:
        recommended.status = CandidateStatus.RECOMMENDED
    dependencies, hierarchies = _functional_dependencies(
        dataset, eligible, config.max_functional_dependencies)
    risks = _aggregation_risks(
        dataset, eligible, measures, recommended.candidate_fields if recommended else [])
    all_quality = _quality_dependencies(dataset, [field.source_field_id for field in eligible])
    return GrainDiscoveryReport(
        grain_discovery_report_id=str(uuid4()), source_document_id=dataset.source_document_id,
        prepared_dataset_id=dataset.prepared_dataset_id,
        prepared_dataset_version=dataset.version,
        prepared_dataset_fingerprint=dataset.fingerprint, analysis_id=dataset.analysis_id,
        status=status, dataset_row_count=dataset.row_count,
        candidate_count=len(candidates), grain_classification=classification,
        process_candidates=processes, event_candidates=events, grain_candidates=candidates,
        functional_dependencies=dependencies, identifier_hierarchies=hierarchies,
        aggregation_risks=risks, quality_dependencies=all_quality,
        recommended_candidate_id=recommended.candidate_id if recommended else None,
        confidence=recommended.confidence if recommended else 0,
        requires_user_validation=True, candidate_limit_configured=config.max_candidates,
        candidates_truncated=theoretical > len(candidates), version=version,
    )
