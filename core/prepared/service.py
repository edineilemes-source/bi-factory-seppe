"""Safe deterministic transformations over the complete loaded dataset."""

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping
from uuid import uuid4

from core.ingestion.file_loader import LoadedWorkbook
from core.profiling.heuristics import is_placeholder
from core.profiling.identifiers import canonicalize_identifier
from core.profiling.models import SemanticRole
from core.quality.models import (
    DataQualityReport, FieldApplicability, FieldQualityStatus, FieldRequirement,
    QualitySeverity,
)
from core.quality.gate import decide_quality_gate
from core.quality.models import QualityGateStatus
from core.semantic.effective_role import effective_semantic_roles
from core.semantic.models import SemanticValidationReport
from core.prepared.models import (
    PreparedDataset, PreparedDatasetStatus, PreparedField, PreparedRow,
    TransformationRecord, TransformationType,
)

RULESET_VERSION = "prepared-safe-v1"
_DATE_BR = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_TRUE = {"true", "verdadeiro", "sim", "yes"}
_FALSE = {"false", "falso", "não", "nao", "no"}


@dataclass(frozen=True)
class PreparationPolicy:
    block_errors: bool = True
    ruleset_version: str = RULESET_VERSION


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def _prepared_type(role: SemanticRole, recommended: str) -> str:
    if role in {SemanticRole.IDENTIFIER, SemanticRole.CODE}:
        return "text"
    if role == SemanticRole.DATE:
        return "date"
    if role == SemanticRole.BOOLEAN:
        return "boolean"
    if role == SemanticRole.MEASURE:
        return "number"
    return "text" if recommended in {"text", "string", "unknown"} else recommended


def _rules(role: SemanticRole) -> list[TransformationType]:
    rules = [TransformationType.TRIM_WHITESPACE, TransformationType.PLACEHOLDER_TO_NULL]
    if role == SemanticRole.IDENTIFIER:
        rules.append(TransformationType.IDENTIFIER_CANONICALIZATION)
    elif role == SemanticRole.DATE:
        rules.append(TransformationType.DATE_CANONICALIZATION)
    elif role == SemanticRole.BOOLEAN:
        rules.append(TransformationType.BOOLEAN_CANONICALIZATION)
    return rules


def _normalize(value: Any, role: SemanticRole) -> tuple[Any, list[tuple[TransformationType, Any, str, str]]]:
    current = value
    changes: list[tuple[TransformationType, Any, str, str]] = []
    if isinstance(current, str):
        trimmed = current.strip()
        if trimmed != current:
            current = trimmed
            changes.append((TransformationType.TRIM_WHITESPACE, current,
                            "Espaços externos removidos sem alterar o conteúdo.", "trim-v1"))
    if isinstance(current, str) and is_placeholder(current):
        current = None
        changes.append((TransformationType.PLACEHOLDER_TO_NULL, None,
                        "Placeholder conhecido representa ausência explícita.", "placeholder-v1"))
        return current, changes
    if current is None:
        return None, changes
    if role == SemanticRole.IDENTIFIER:
        canonical = canonicalize_identifier(current)
        if canonical != current or type(canonical) is not type(current):
            current = canonical
            changes.append((TransformationType.IDENTIFIER_CANONICALIZATION, current,
                            "Representação numérica integral convertida em identificador textual.",
                            "identifier-safe-v1"))
    elif role == SemanticRole.DATE:
        canonical: str | None = None
        if isinstance(current, datetime):
            canonical = current.date().isoformat()
        elif isinstance(current, date):
            canonical = current.isoformat()
        elif isinstance(current, str):
            match = _DATE_BR.fullmatch(current)
            if match:
                day, month, year = map(int, match.groups())
                try:
                    canonical = date(year, month, day).isoformat()
                except ValueError:
                    canonical = None
        if canonical is not None and (canonical != current or type(canonical) is not type(current)):
            current = canonical
            changes.append((TransformationType.DATE_CANONICALIZATION, current,
                            "Data inequivocamente reconhecida foi representada em ISO 8601.",
                            "date-iso-v1"))
    elif role == SemanticRole.BOOLEAN and isinstance(current, str):
        folded = current.casefold()
        boolean = True if folded in _TRUE else False if folded in _FALSE else None
        if boolean is not None:
            current = boolean
            changes.append((TransformationType.BOOLEAN_CANONICALIZATION, current,
                            "Valor textual inequívoco convertido em booleano.", "boolean-safe-v1"))
    return current, changes


def _gate(report: DataQualityReport | None, policy: PreparationPolicy) -> PreparedDatasetStatus:
    if report is None:
        return PreparedDatasetStatus.READY
    decision = report.gate_decision or decide_quality_gate(report.issues)
    if decision.status == QualityGateStatus.BLOCKED:
        return PreparedDatasetStatus.BLOCKED
    return (PreparedDatasetStatus.READY_WITH_WARNINGS if report.issues
            else PreparedDatasetStatus.READY)


def _fingerprint(schema: list[PreparedField], rows: list[PreparedRow], ruleset: str) -> str:
    content = {
        "ruleset_version": ruleset,
        "schema": [field.model_dump(mode="json") for field in schema],
        "rows": [row.model_dump(mode="json") for row in rows],
    }
    encoded = json.dumps(content, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), default=_json_value).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def prepare_dataset(
    workbook: LoadedWorkbook,
    semantics: SemanticValidationReport,
    quality_report: DataQualityReport | None = None,
    *,
    version: int = 1,
    validated_values: Mapping[tuple[str, str], Any] | None = None,
    policy: PreparationPolicy | None = None,
) -> PreparedDataset:
    """Build effective rows without mutating the source workbook.

    ``workbook`` must be loaded without profiling sampling. The dimensional check
    rejects accidental preparation from a sampled workbook.
    """
    if not semantics.analysis_id or not semantics.source_document_id:
        raise ValueError("analysis_id e source_document_id são obrigatórios.")
    policy = policy or PreparationPolicy()
    validated_values = validated_values or {}
    roles = effective_semantic_roles(semantics)
    quality_by_field = {item.source_field_id: item for item in
                        (quality_report.field_summaries if quality_report else [])}
    profiles = {sheet.name: sheet for sheet in semantics.observed_profile.sheets}
    schema: list[PreparedField] = []
    rows: list[PreparedRow] = []
    transformations: list[TransformationRecord] = []

    for loaded in workbook.sheets:
        profile = profiles.get(loaded.name)
        if profile is None:
            raise ValueError(f"A aba {loaded.name!r} não pertence à análise semântica.")
        if len(loaded.rows) < loaded.approximate_row_count:
            raise ValueError("Prepared Dataset exige o dataset completo, não a amostra de profiling.")
        header_index = profile.probable_header_row - 1 if profile.probable_header_row else None
        start = header_index + 1 if header_index is not None else 0
        field_ids: list[str] = []
        for field in profile.fields:
            field_id = f"{loaded.name}::{field.technical_name}"
            field_ids.append(field_id)
            role = roles.get(field_id, field.semantic_role_candidate)
            quality = quality_by_field.get(field_id)
            schema.append(PreparedField(
                source_field_id=field_id, sheet_name=loaded.name,
                source_name=field.original_name, technical_name=field.technical_name,
                effective_semantic_role=role, recommended_type=field.recommended_type,
                prepared_type=_prepared_type(role, field.recommended_type),
                nullable=(not quality or quality.requirement != FieldRequirement.REQUIRED),
                requirement=quality.requirement if quality else FieldRequirement.UNKNOWN,
                applicability=quality.applicability if quality else FieldApplicability.UNKNOWN,
                transformation_rules=_rules(role),
                quality_status=quality.quality_status if quality else FieldQualityStatus.NOT_EVALUATED,
            ))
        for source_index in range(start, len(loaded.rows)):
            source = loaded.rows[source_index]
            row_number = source_index + 1
            identity_input = f"{semantics.analysis_id}|{loaded.name}|{row_number}"
            source_row_id = "sr:" + hashlib.sha256(identity_input.encode()).hexdigest()[:20]
            effective: dict[str, Any] = {}
            for column, field_id in enumerate(field_ids):
                source_value = source[column] if column < len(source) else None
                role = roles.get(field_id, profile.fields[column].semantic_role_candidate)
                result, changes = _normalize(source_value, role)
                validated_key = (source_row_id, field_id)
                if validated_key in validated_values:
                    result = validated_values[validated_key]
                    changes.append((TransformationType.TYPE_CANONICALIZATION, result,
                                    "Valor explicitamente validado tem precedência.", "validated-value-v1"))
                effective[field_id] = result
                for sequence, (kind, resulting, reason, rule_id) in enumerate(changes):
                    event_key = f"{identity_input}|{field_id}|{kind.value}|{sequence}|{rule_id}"
                    transformations.append(TransformationRecord(
                        transformation_id="tr:" + hashlib.sha256(event_key.encode()).hexdigest()[:20],
                        analysis_id=semantics.analysis_id,
                        source_document_id=semantics.source_document_id,
                        source_row_id=source_row_id, row_id=source_row_id,
                        source_field_id=field_id, transformation_type=kind,
                        source_value=_json_value(source_value), resulting_value=_json_value(resulting),
                        reason=reason, rule_id=rule_id,
                    ))
            rows.append(PreparedRow(source_row_id=source_row_id, sheet_name=loaded.name,
                                    source_row_number=row_number, values=effective))

    summary = Counter(item.transformation_type.value for item in transformations)
    fingerprint = _fingerprint(schema, rows, policy.ruleset_version)
    unresolved = list(quality_report.issues) if quality_report else []
    return PreparedDataset(
        prepared_dataset_id=str(uuid4()), source_document_id=semantics.source_document_id,
        analysis_id=semantics.analysis_id, version=version,
        ruleset_version=policy.ruleset_version, row_count=len(rows), field_count=len(schema),
        status=_gate(quality_report, policy), schema=schema, rows=rows,
        transformations=transformations, transformation_summary=dict(sorted(summary.items())),
        unresolved_quality_issues=unresolved,
        statistics={"source_row_count": len(rows), "prepared_row_count": len(rows),
                    "source_field_count": len(schema), "prepared_field_count": len(schema),
                    "transformation_count": len(transformations),
                    "open_issue_count": len(unresolved)}, fingerprint=fingerprint,
    )
