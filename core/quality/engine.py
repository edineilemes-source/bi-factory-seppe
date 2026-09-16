"""Generic, deterministic and non-mutating data-quality engine."""

import hashlib
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from statistics import median
from typing import Any, Mapping

from core.ingestion.file_loader import LoadedWorkbook
from core.profiling.heuristics import is_empty, is_placeholder, value_kind
from core.profiling.identifiers import canonicalize_identifier, identifier_pattern
from core.profiling.models import SemanticRole
from core.quality.models import (
    BlockingScope,
    DataQualityReport, FieldApplicability, FieldQualityStatus, FieldQualitySummary,
    FieldRequirement, IdentifierConstraint, QualityIssue, QualityIssueType,
    QualityDefectStatus, QualitySeverity, QualityStatus, ReconciliationCandidate,
)
from core.quality.gate import decide_quality_gate
from core.semantic.effective_role import effective_semantic_roles
from core.semantic.models import DecisionLevel, SemanticValidationReport

MAX_EXAMPLES = 5
QUALITY_RULESET_VERSION = "quality-contextual-v2"
WEIGHTS = {QualitySeverity.INFO: .25, QualitySeverity.WARNING: .5,
           QualitySeverity.ERROR: 1.0, QualitySeverity.CRITICAL: 2.0}
SEVERITY_ORDER = {QualitySeverity.INFO: 0, QualitySeverity.WARNING: 1,
                  QualitySeverity.ERROR: 2, QualitySeverity.CRITICAL: 3}


def _display(value: Any) -> Any:
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def _key(value: Any) -> tuple[str, str]:
    return type(value).__name__, repr(value)


def _canonical(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).strip()).casefold()


def _distance(left: str, right: str) -> int:
    if abs(len(left) - len(right)) > 1:
        return 2
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    text = str(value).strip()
    if re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", text):
        try:
            return float(text.replace(",", "."))
        except ValueError:
            pass
    return None


def _issue(analysis_id: str, sheet: str, field_id: str | None, field_name: str | None,
           kind: QualityIssueType, severity: QualitySeverity, affected: list[tuple[int, Any]],
           total: int, reason: str, *, evidence: dict[str, Any] | None = None,
           action: str = "Inspecionar os valores na fonte; nenhuma correção foi aplicada.",
           defect_status: QualityDefectStatus = QualityDefectStatus.OBSERVED_ANOMALY,
           blocking: bool = False, blocking_reason: str | None = None,
           blocking_scope: tuple[BlockingScope, ...] = ()) -> QualityIssue:
    identity = f"{analysis_id}|{sheet}|{field_id}|{kind.value}|{reason}"
    return QualityIssue(
        issue_id="qi:" + hashlib.sha256(identity.encode()).hexdigest()[:16],
        analysis_id=analysis_id, source_field_id=field_id, sheet_name=sheet,
        field_name=field_name, issue_type=kind, severity=severity,
        affected_count=len(affected),
        affected_percentage=round(100 * len(affected) / total, 2) if total else 0,
        examples=[_display(value) for _, value in affected[:MAX_EXAMPLES]],
        row_numbers=[row for row, _ in affected[:MAX_EXAMPLES]], reason=reason,
        evidence=evidence or {}, suggested_action=action,
        quality_defect_status=defect_status, blocking_eligible=blocking,
        blocking_reason=blocking_reason, blocking_scope=list(blocking_scope),
    )


def analyze_data_quality(workbook: LoadedWorkbook,
                         semantics: SemanticValidationReport,
                         requirements: Mapping[str, FieldRequirement] | None = None,
                         applicabilities: Mapping[str, FieldApplicability] | None = None,
                         identifier_constraints: Mapping[str, IdentifierConstraint] | None = None,
                         version: int = 1,
                         ) -> DataQualityReport:
    """Analyze sampled source rows without changing any source object or value."""
    if not semantics.analysis_id:
        raise ValueError("analysis_id é obrigatório para analisar qualidade.")
    roles = effective_semantic_roles(semantics)
    requirements = requirements or {}
    applicabilities = applicabilities or {}
    identifier_constraints = identifier_constraints or {}
    issues: list[QualityIssue] = []
    candidates: list[ReconciliationCandidate] = []
    affected_rows: set[tuple[str, int]] = set()
    field_totals: dict[str, int] = {}
    field_meta: dict[str, tuple[str, str, SemanticRole, FieldRequirement,
                                FieldApplicability, int, int, FieldQualityStatus]] = {}
    total_rows = 0

    profiles = {sheet.name: sheet for sheet in semantics.observed_profile.sheets}
    for loaded in workbook.sheets:
        profile = profiles.get(loaded.name)
        if not profile:
            continue
        header_index = (profile.probable_header_row - 1
                        if profile.probable_header_row is not None else None)
        data = loaded.rows[header_index + 1:] if header_index is not None else loaded.rows
        total_rows += len(data)
        width = len(profile.fields)

        # Exact full-row duplicates only: deliberately conservative.
        row_groups: dict[tuple[tuple[str, str], ...], list[tuple[int, list[Any]]]] = defaultdict(list)
        for offset, row in enumerate(data, start=(header_index or 0) + 2):
            padded = [row[i] if i < len(row) else None for i in range(width)]
            if any(not is_empty(v) for v in padded):
                row_groups[tuple(_key(v) for v in padded)].append((offset, padded))
        duplicate_rows = [(row_no, row) for group in row_groups.values() if len(group) > 1
                          for row_no, row in group[1:]]
        if duplicate_rows:
            duplicate_issue = _issue(
                semantics.analysis_id, loaded.name, None, None,
                QualityIssueType.DUPLICATE_RECORD, QualitySeverity.ERROR,
                [(number, [_display(v) for v in row]) for number, row in duplicate_rows],
                len(data), "Registros integralmente idênticos repetem todos os atributos observados.",
                evidence={"matching_attributes": width, "strategy": "exact_full_record"},
                action="Revisar os registros completos antes de decidir por eventual remoção.",
                defect_status=QualityDefectStatus.SUSPECTED)
            issues.append(duplicate_issue)
            affected_rows.update((loaded.name, number) for number, _ in duplicate_rows)

        for index, field in enumerate(profile.fields):
            field_id = f"{loaded.name}::{field.technical_name}"
            role = roles.get(field_id, field.semantic_role_candidate)
            values = [(row_no, row[index] if index < len(row) else None)
                      for row_no, row in enumerate(data, start=(header_index or 0) + 2)]
            field_totals[field_id] = len(values)
            nulls = [(n, v) for n, v in values if v is None or
                     (isinstance(v, str) and not v.strip())]
            placeholders = [(n, v) for n, v in values if not is_empty(v) and is_placeholder(v)]
            significant = [(n, v) for n, v in values if not is_empty(v) and not is_placeholder(v)]
            requirement = requirements.get(field_id, FieldRequirement.UNKNOWN)
            applicability = applicabilities.get(field_id, FieldApplicability.UNKNOWN)
            deferred = (semantics.decision_by_source_field.get(field_id)
                        == DecisionLevel.DEFERRED_NO_EVIDENCE)
            no_evidence = not significant and len(nulls) + len(placeholders) == len(values)
            quality_status = (FieldQualityStatus.NOT_EVALUATED if deferred and no_evidence
                              else FieldQualityStatus.NEEDS_BUSINESS_RULE
                              if (nulls or placeholders) and (
                                  requirement in {FieldRequirement.UNKNOWN, FieldRequirement.CONDITIONAL}
                                  or applicability in {FieldApplicability.UNKNOWN, FieldApplicability.CONDITIONAL})
                              else FieldQualityStatus.EVALUATED)
            field_meta[field_id] = (loaded.name, field.original_name, role, requirement,
                                    applicability, len(nulls), len(placeholders), quality_status)
            absence_is_error = (requirement == FieldRequirement.REQUIRED
                                and applicability == FieldApplicability.APPLICABLE)
            if nulls and quality_status != FieldQualityStatus.NOT_EVALUATED:
                issues.append(_issue(semantics.analysis_id, loaded.name, field_id,
                    field.original_name, QualityIssueType.MISSING_VALUE,
                    QualitySeverity.ERROR if absence_is_error else QualitySeverity.INFO,
                    nulls, len(values), "Valores fisicamente nulos ou vazios foram encontrados.",
                    evidence={"requirement": requirement.value,
                              "applicability": applicability.value,
                              "quality_defect": absence_is_error},
                    defect_status=(QualityDefectStatus.CONFIRMED_DEFECT if absence_is_error
                                   else QualityDefectStatus.NOT_A_DEFECT
                                   if requirement == FieldRequirement.OPTIONAL
                                   else QualityDefectStatus.NEEDS_BUSINESS_RULE),
                    blocking=absence_is_error,
                    blocking_reason=("Campo explicitamente REQUIRED e APPLICABLE."
                                     if absence_is_error else None),
                    blocking_scope=((BlockingScope.PREPARED_DATASET,) if absence_is_error else ())))
            if placeholders and quality_status != FieldQualityStatus.NOT_EVALUATED:
                issues.append(_issue(semantics.analysis_id, loaded.name, field_id,
                    field.original_name, QualityIssueType.PLACEHOLDER_VALUE,
                    QualitySeverity.ERROR if absence_is_error else QualitySeverity.INFO,
                    placeholders, len(values), "Valores textuais representam ausência, mas não são NULL reais.",
                    evidence={"requirement": requirement.value,
                              "applicability": applicability.value,
                              "quality_defect": absence_is_error},
                    defect_status=(QualityDefectStatus.CONFIRMED_DEFECT if absence_is_error
                                   else QualityDefectStatus.NOT_A_DEFECT
                                   if requirement == FieldRequirement.OPTIONAL
                                   else QualityDefectStatus.NEEDS_BUSINESS_RULE),
                    blocking=absence_is_error,
                    blocking_reason=("Campo explicitamente REQUIRED e APPLICABLE."
                                     if absence_is_error else None),
                    blocking_scope=((BlockingScope.PREPARED_DATASET,) if absence_is_error else ())))

            if role == SemanticRole.DATE:
                invalid = [(n, v) for n, v in significant if value_kind(v) != "date"]
                if invalid:
                    issues.append(_issue(semantics.analysis_id, loaded.name, field_id,
                        field.original_name, QualityIssueType.INVALID_TYPE, QualitySeverity.ERROR,
                        invalid, len(values), "Valores não puderam ser interpretados como datas válidas.",
                        evidence={"expected_type": "date", "quality_defect": True},
                        defect_status=QualityDefectStatus.CONFIRMED_DEFECT, blocking=True,
                        blocking_reason="Tipo semântico DATE validado não pôde ser interpretado.",
                        blocking_scope=(BlockingScope.PREPARED_DATASET,)))
            if role == SemanticRole.MEASURE:
                invalid = [(n, v) for n, v in significant if _numeric(v) is None]
                if invalid:
                    issues.append(_issue(semantics.analysis_id, loaded.name, field_id,
                        field.original_name, QualityIssueType.INVALID_TYPE, QualitySeverity.ERROR,
                        invalid, len(values), "Valores não numéricos aparecem em um campo de medida.",
                        evidence={"quality_defect": True},
                        defect_status=QualityDefectStatus.CONFIRMED_DEFECT, blocking=True,
                        blocking_reason="Tipo semântico MEASURE validado contém valor não numérico.",
                        blocking_scope=(BlockingScope.PREPARED_DATASET,)))
                numeric = [(n, v, _numeric(v)) for n, v in significant if _numeric(v) is not None]
                nums = [number for _, _, number in numeric if number is not None]
                if len(nums) >= 4:
                    ordered = sorted(nums)
                    lower = median(ordered[:len(ordered)//2])
                    upper = median(ordered[(len(ordered)+1)//2:])
                    iqr = upper - lower
                    if iqr > 0:
                        low, high = lower - 1.5 * iqr, upper + 1.5 * iqr
                        outliers = [(n, v) for n, v, number in numeric
                                    if number is not None and (number < low or number > high)]
                        if outliers:
                            issues.append(_issue(semantics.analysis_id, loaded.name, field_id,
                                field.original_name, QualityIssueType.OUTLIER, QualitySeverity.WARNING,
                                outliers, len(values), "Valores estão fora dos limites robustos de IQR e merecem inspeção.",
                                evidence={"method": "IQR", "q1": lower, "q3": upper,
                                          "lower_bound": low, "upper_bound": high,
                                          "quality_defect": False},
                                action="Inspecionar o contexto; outlier não implica erro nem correção.",
                                defect_status=QualityDefectStatus.OBSERVED_ANOMALY))

            if role == SemanticRole.IDENTIFIER and significant:
                texts = [(n, v, canonicalize_identifier(v)) for n, v in significant]
                constraint = identifier_constraints.get(field_id, IdentifierConstraint())
                pattern_counts = Counter(identifier_pattern(text) for _, _, text in texts)
                dominant, dominant_count = pattern_counts.most_common(1)[0]
                inconsistent = [(n, v) for n, v, text in texts
                                if identifier_pattern(text) != dominant]
                if dominant_count >= 3 and inconsistent and dominant_count / len(texts) >= .6:
                    issues.append(_issue(semantics.analysis_id, loaded.name, field_id,
                        field.original_name, QualityIssueType.IDENTIFIER_INCONSISTENCY,
                        QualitySeverity.WARNING, inconsistent, len(values),
                        "Identificadores variam em relação ao formato predominante; não há regra contratual.",
                        evidence={"dominant_pattern": dominant,
                                  "dominant_percentage": round(100*dominant_count/len(texts), 2),
                                  "quality_defect": False,
                                  "observation_class": "IDENTIFIER_LENGTH_VARIATION"},
                        defect_status=QualityDefectStatus.NEEDS_BUSINESS_RULE,
                        action="Declarar máscara/comprimento validado antes de classificar como defeito."))
                if constraint.validated and (constraint.pattern or constraint.exact_length):
                    invalid_format = [(n, v) for n, v, text in texts
                        if ((constraint.pattern is not None and
                             re.fullmatch(constraint.pattern, str(text)) is None)
                            or (constraint.exact_length is not None and
                                len(str(text)) != constraint.exact_length))]
                    if invalid_format:
                        issues.append(_issue(semantics.analysis_id, loaded.name, field_id,
                            field.original_name, QualityIssueType.INVALID_IDENTIFIER_FORMAT,
                            QualitySeverity.ERROR, invalid_format, len(values),
                            "Identificadores violam máscara ou comprimento explicitamente validado.",
                            evidence={"pattern": constraint.pattern,
                                      "exact_length": constraint.exact_length,
                                      "constraint_validated": True, "quality_defect": True},
                            defect_status=QualityDefectStatus.CONFIRMED_DEFECT, blocking=True,
                            blocking_reason="Constraint de identificador validada foi violada.",
                            blocking_scope=(BlockingScope.PREPARED_DATASET,)))
                counts = Counter(text for _, _, text in texts)
                repeated = [(n, v) for n, v, text in texts if counts[text] > 1]
                if repeated:
                    duplicate_is_defect = constraint.unique
                    if not duplicate_is_defect:
                        meta = field_meta[field_id]
                        field_meta[field_id] = (*meta[:-1], FieldQualityStatus.NEEDS_BUSINESS_RULE)
                    issues.append(_issue(semantics.analysis_id, loaded.name, field_id,
                        field.original_name, QualityIssueType.DUPLICATE_VALUE,
                        QualitySeverity.ERROR if duplicate_is_defect else QualitySeverity.INFO,
                        repeated, len(values),
                        ("Valores violam a regra explícita de unicidade do identificador."
                         if duplicate_is_defect else
                         "Valores de identificador se repetem; sem grão ou unicidade declarada, isso é diagnóstico."),
                        evidence={"distinct_repeated_values": sum(c > 1 for c in counts.values()),
                                  "unique": constraint.unique,
                                  "business_key": constraint.business_key,
                                  "grain_declared": constraint.grain_declared,
                                  "quality_defect": duplicate_is_defect},
                        action=("Revisar a violação da regra explícita de unicidade."
                                if duplicate_is_defect else
                                "Definir grão/chave de negócio antes de avaliar a repetição."),
                        defect_status=(QualityDefectStatus.CONFIRMED_DEFECT if duplicate_is_defect
                                       else QualityDefectStatus.NEEDS_BUSINESS_RULE),
                        blocking=duplicate_is_defect,
                        blocking_reason=("Constraint unique=true foi violada."
                                         if duplicate_is_defect else None),
                        blocking_scope=((BlockingScope.PREPARED_DATASET,)
                                        if duplicate_is_defect else ())))

            if role in {SemanticRole.CATEGORY, SemanticRole.CODE} and significant:
                groups: dict[str, list[tuple[int, Any]]] = defaultdict(list)
                for n, value in significant:
                    groups[_canonical(value)].append((n, value))
                variants = [item for group in groups.values()
                            if len({_key(v) for _, v in group}) > 1 for item in group]
                if variants:
                    issues.append(_issue(semantics.analysis_id, loaded.name, field_id,
                        field.original_name, QualityIssueType.FORMAT_INCONSISTENCY,
                        QualitySeverity.INFO, variants, len(values),
                        "Variações apenas de caixa ou espaços compartilham a mesma forma normalizada.",
                        evidence={"normalization": "trim + collapse_spaces + casefold"},
                        action="Normalização segura pode ser proposta futuramente; a fonte foi preservada."))
                frequencies = Counter(_canonical(v) for _, v in significant)
                common = [value for value, count in frequencies.items() if count >= 2]
                suspicious: list[tuple[int, Any]] = []
                matches: dict[str, str] = {}
                for n, value in significant:
                    canon = _canonical(value)
                    if frequencies[canon] == 1:
                        near = next((candidate for candidate in common
                                     if len(candidate) >= 2 and _distance(canon, candidate) == 1), None)
                        if near:
                            suspicious.append((n, value)); matches[canon] = near
                if suspicious:
                    if role == SemanticRole.CODE:
                        for n, value in suspicious[:50]:
                            canon = _canonical(value); candidate = matches[canon]
                            candidate_id = hashlib.sha256(
                                f"{semantics.analysis_id}|{field_id}|{canon}|{candidate}".encode()).hexdigest()[:20]
                            candidates.append(ReconciliationCandidate(
                                candidate_id=f"reconciliation:{candidate_id}",
                                analysis_id=semantics.analysis_id, source_field_id=field_id,
                                source_value=_display(value), candidate_value=candidate,
                                reason="Similaridade lexical isolada; requer validação humana.",
                                confidence=None, evidence=["frequency", "levenshtein_distance_1"],
                                requires_validation=True))
                    issues.append(_issue(semantics.analysis_id, loaded.name, field_id,
                        field.original_name, QualityIssueType.DOMAIN_INCONSISTENCY,
                        QualitySeverity.WARNING, suspicious, len(values),
                        "Valores raros são muito semelhantes a categorias recorrentes.",
                        evidence={"method": "frequency + Levenshtein distance 1", "matches": matches,
                                  "quality_defect": False, "candidate_only": True},
                        action="Validar a categoria suspeita; nenhuma substituição foi realizada.",
                        defect_status=QualityDefectStatus.SUSPECTED))

    for issue in issues:
        affected_rows.update((issue.sheet_name or "", row) for row in issue.row_numbers)
    by_field: dict[str, list[QualityIssue]] = defaultdict(list)
    for issue in issues:
        if issue.source_field_id:
            by_field[issue.source_field_id].append(issue)
    summaries: list[FieldQualitySummary] = []
    for field_id, total in field_totals.items():
        findings = by_field[field_id]
        affected = min(total, sum(item.affected_count for item in findings))
        quality_findings = [item for item in findings
                            if item.quality_defect_status == QualityDefectStatus.CONFIRMED_DEFECT]
        penalty = sum(WEIGHTS[item.severity] * item.affected_count for item in quality_findings)
        sheet, name, role, requirement, applicability, missing_count, placeholder_count, status = field_meta[field_id]
        quality_score = (None if status == FieldQualityStatus.NOT_EVALUATED else
                         round(max(0, 100 - 100 * penalty / max(total, 1)), 2))
        summaries.append(FieldQualitySummary(
            source_field_id=field_id, sheet_name=sheet, field_name=name, semantic_role=role,
            effective_semantic_role=role, requirement=requirement,
            applicability=applicability, quality_status=status,
            score=quality_score, quality_score=quality_score,
            missing_count=missing_count,
            missing_percentage=round(100 * missing_count / total, 2) if total else 0,
            placeholder_count=placeholder_count,
            placeholder_percentage=round(100 * placeholder_count / total, 2) if total else 0,
            observed_completeness=round(100 * max(0, total-missing_count-placeholder_count) / total, 2) if total else 0,
            issues_count=len(findings), affected_count=affected,
            affected_percentage=round(100 * affected / total, 2) if total else 0,
            maximum_severity=max((item.severity for item in findings),
                                 key=lambda s: SEVERITY_ORDER[s], default=None)))
    not_evaluated_ids = {item.source_field_id for item in summaries
                         if item.quality_status == FieldQualityStatus.NOT_EVALUATED}
    eligible_cells = sum(total for field_id, total in field_totals.items()
                         if field_id not in not_evaluated_ids)
    penalty = sum(WEIGHTS[item.severity] * item.affected_count for item in issues
                  if item.source_field_id not in not_evaluated_ids
                  and item.quality_defect_status == QualityDefectStatus.CONFIRMED_DEFECT)
    all_cells = sum(field_totals.values())
    absent_cells = sum(meta[5] + meta[6] for meta in field_meta.values())
    counts = Counter(item.severity for item in issues)
    gate_decision = decide_quality_gate(issues)
    report = DataQualityReport(
        analysis_id=semantics.analysis_id, status=(QualityStatus.COMPLETED_WITH_ISSUES
            if issues else QualityStatus.COMPLETED), total_rows=total_rows,
        total_fields=len(field_totals),
        score=round(max(0, 100 - 100*penalty/max(eligible_cells, 1)), 2),
        observed_completeness=round(100 * max(0, all_cells-absent_cells) / all_cells, 2) if all_cells else 0,
        eligible_cells=eligible_cells,
        evaluated_fields=len(field_totals) - len(not_evaluated_ids),
        not_evaluated_fields=len(not_evaluated_ids),
        issues_count=len(issues), affected_rows=len(affected_rows),
        critical_count=counts[QualitySeverity.CRITICAL], error_count=counts[QualitySeverity.ERROR],
        warning_count=counts[QualitySeverity.WARNING], info_count=counts[QualitySeverity.INFO],
        issues=issues, field_summaries=summaries, reconciliation_candidates=candidates,
        version=version, ruleset_version=QUALITY_RULESET_VERSION,
        gate_decision=gate_decision)
    fingerprint_payload = {
        "analysis_id": report.analysis_id,
        "ruleset_version": report.ruleset_version,
        "issues": [issue.model_dump(mode="json") for issue in report.issues],
        "gate": report.gate_decision.model_dump(mode="json", exclude={"calculated_at"}),
    }
    import json
    report.fingerprint = hashlib.sha256(json.dumps(
        fingerprint_payload, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    return report
