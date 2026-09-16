"""Bounded-memory, atomic Prepared Dataset artifact generation."""

import csv
import gzip
import hashlib
import json
import os
import resource
import sys
import time
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.ingestion.file_loader import iter_tabular_chunks
from core.prepared.models import (
    PreparedDatasetArtifact, PreparedField, PreparedGenerationMetrics,
    PreparedGenerationStatus, PreparedGenerationStepMetric, PreparedProgressEvent,
    PreparedRow, TransformationRecord, TransformationType,
)
from core.prepared.service import (
    PreparationPolicy, _gate, _json_value, _normalize, _prepared_type, _rules,
)
from core.profiling.models import SemanticRole
from core.quality.models import (
    DataQualityReport, FieldApplicability, FieldQualityStatus, FieldRequirement,
)
from core.semantic.effective_role import effective_semantic_roles
from core.semantic.models import SemanticValidationReport


DEFAULT_PREPARED_CHUNK_SIZE = int(os.getenv("PREPARED_CHUNK_SIZE", "10000"))
DEFAULT_PREPARED_MEMORY_BUDGET_MB = int(os.getenv("PREPARED_MEMORY_BUDGET_MB", "512"))
DEFAULT_PREVIEW_ROWS = int(os.getenv("PREPARED_PREVIEW_ROWS", "100"))
DEFAULT_ARTIFACT_ROOT = Path("storage/working/prepared")
ProgressCallback = Callable[[PreparedProgressEvent], None]
StatusCallback = Callable[[PreparedGenerationStatus, str, str | None], None]


def _rss_mb() -> float:
    try:
        pages = int(Path("/proc/self/statm").read_text().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024)
    except (OSError, ValueError, IndexError):
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _peak_rss_mb() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / 1024 if sys.platform != "darwin" else value / (1024 * 1024)


def _schema(semantics: SemanticValidationReport,
            quality_report: DataQualityReport | None) -> tuple[list[PreparedField], dict[str, list[str]]]:
    roles = effective_semantic_roles(semantics)
    quality_by_field = {item.source_field_id: item for item in
                        (quality_report.field_summaries if quality_report else [])}
    schema: list[PreparedField] = []
    by_sheet: dict[str, list[str]] = {}
    for profile in semantics.observed_profile.sheets:
        ids = []
        for field in profile.fields:
            field_id = f"{profile.name}::{field.technical_name}"; ids.append(field_id)
            role = roles.get(field_id, field.semantic_role_candidate)
            quality = quality_by_field.get(field_id)
            schema.append(PreparedField(
                source_field_id=field_id, sheet_name=profile.name,
                source_name=field.original_name, technical_name=field.technical_name,
                effective_semantic_role=role, recommended_type=field.recommended_type,
                prepared_type=_prepared_type(role, field.recommended_type),
                nullable=(not quality or quality.requirement != FieldRequirement.REQUIRED),
                requirement=quality.requirement if quality else FieldRequirement.UNKNOWN,
                applicability=quality.applicability if quality else FieldApplicability.UNKNOWN,
                transformation_rules=_rules(role),
                quality_status=quality.quality_status if quality else FieldQualityStatus.NOT_EVALUATED,
            ))
        by_sheet[profile.name] = ids
    return schema, by_sheet


def _safe_csv_value(value: Any) -> Any:
    value = _json_value(value)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return value


def _logical_row_bytes(row: PreparedRow) -> bytes:
    return (json.dumps(row.model_dump(mode="json"), ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), default=_json_value) + "\n").encode("utf-8")


def _estimate_chunk_bytes(rows: list[list[Any]]) -> int:
    return sum(sys.getsizeof(row) + sum(sys.getsizeof(value) for value in row) for row in rows)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def generate_prepared_dataset_artifact(
    file_name: str, source_content: bytes, semantics: SemanticValidationReport,
    quality_report: DataQualityReport | None = None, *, version: int = 1,
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
    chunk_size: int = DEFAULT_PREPARED_CHUNK_SIZE,
    memory_budget_mb: int = DEFAULT_PREPARED_MEMORY_BUDGET_MB,
    preview_rows: int = DEFAULT_PREVIEW_ROWS,
    validated_values: Mapping[tuple[str, str], Any] | None = None,
    policy: PreparationPolicy | None = None,
    progress_callback: ProgressCallback | None = None,
    status_callback: StatusCallback | None = None,
    fail_after_chunks: int | None = None,
    prepared_dataset_id: str | None = None,
) -> PreparedDatasetArtifact:
    """Stream effective rows to an atomic CSV artifact with sparse JSONL lineage."""
    if not semantics.analysis_id or not semantics.source_document_id:
        raise ValueError("analysis_id e source_document_id são obrigatórios.")
    if chunk_size < 1 or preview_rows < 0:
        raise ValueError("Configuração de chunk/preview inválida.")
    policy = policy or PreparationPolicy(); validated_values = validated_values or {}
    artifact_root.mkdir(parents=True, exist_ok=True)
    prepared_id = prepared_dataset_id or str(uuid4())
    base = f"prepared-{semantics.analysis_id}-v{version}-{prepared_id[:8]}"
    final_path = artifact_root / f"{base}.csv"
    partial_path = artifact_root / f"{base}.csv.partial"
    transformations_path = artifact_root / f"{base}.transformations.jsonl.gz"
    transformations_partial = artifact_root / f"{base}.transformations.jsonl.gz.partial"
    started_at = datetime.now(timezone.utc); start_clock = time.monotonic()
    rss_start = _rss_mb()
    metrics = PreparedGenerationMetrics(
        started_at=started_at, rss_start_mb=rss_start, rss_peak_mb=_peak_rss_mb(),
        status=PreparedGenerationStatus.RUNNING,
    )
    if status_callback:
        status_callback(PreparedGenerationStatus.RUNNING, "STARTING", None)

    def progress(stage: str, rows: int, total: int | None, message: str) -> None:
        elapsed = time.monotonic() - start_clock
        rss = _rss_mb(); metrics.rss_peak_mb = max(metrics.rss_peak_mb, _peak_rss_mb(), rss)
        metrics.step_metrics.append(PreparedGenerationStepMetric(
            stage=stage, rows_processed=rows, rss_mb=rss, elapsed_seconds=elapsed))
        if progress_callback:
            progress_callback(PreparedProgressEvent(
                stage=stage, rows_processed=rows, total_rows=total,
                elapsed_seconds=elapsed, message=message))

    try:
        schema, fields_by_sheet = _schema(semantics, quality_report)
        profiles = {sheet.name: sheet for sheet in semantics.observed_profile.sheets}
        schema_by_id = {field.source_field_id: field for field in schema}
        names: list[str] = []; seen: Counter[str] = Counter()
        for field in schema:
            seen[field.source_name] += 1
            names.append(field.source_name if seen[field.source_name] == 1
                         else f"{field.source_name}__{seen[field.source_name]}")
        logical_hash = hashlib.sha256()
        logical_hash.update(json.dumps({
            "ruleset_version": policy.ruleset_version,
            "schema": [field.model_dump(mode="json") for field in schema],
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        transformations_by_type: Counter[str] = Counter()
        transformations_by_field: Counter[str] = Counter()
        preview: list[dict[str, Any]] = []
        processed = 0; chunk_number = 0; estimated_max = 0
        total_hint = semantics.observed_profile.summary.total_approximate_rows
        with partial_path.open("w", encoding="utf-8", newline="") as output, \
                gzip.open(transformations_partial, "wt", encoding="utf-8", compresslevel=6) as lineage:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(["source_row_id", "sheet_name", "source_row_number", *names])
            for chunk in iter_tabular_chunks(file_name, source_content, chunk_size=chunk_size):
                chunk_number += 1
                if chunk.sheet_name not in profiles:
                    raise ValueError(f"A aba {chunk.sheet_name!r} não pertence à análise semântica.")
                estimated_max = max(estimated_max, _estimate_chunk_bytes(chunk.rows))
                progress("READ_CHUNK", processed, total_hint, f"Lendo fonte: {processed:,} linhas")
                profile = profiles[chunk.sheet_name]
                header_index = profile.probable_header_row - 1 if profile.probable_header_row else -1
                field_ids = fields_by_sheet[chunk.sheet_name]
                roles = {field_id: schema_by_id[field_id].effective_semantic_role for field_id in field_ids}
                for offset, source in enumerate(chunk.rows):
                    source_index = chunk.start_row_index + offset
                    if source_index <= header_index:
                        continue
                    row_number = source_index + 1
                    identity_input = f"{semantics.analysis_id}|{chunk.sheet_name}|{row_number}"
                    source_row_id = "sr:" + hashlib.sha256(identity_input.encode()).hexdigest()[:20]
                    effective: dict[str, Any] = {}
                    for column, field_id in enumerate(field_ids):
                        source_value = source[column] if column < len(source) else None
                        result, changes = _normalize(source_value, roles[field_id])
                        validated_key = (source_row_id, field_id)
                        if validated_key in validated_values:
                            result = validated_values[validated_key]
                            changes.append((TransformationType.TYPE_CANONICALIZATION, result,
                                            "Valor explicitamente validado tem precedência.",
                                            "validated-value-v1"))
                        effective[field_id] = result
                        for sequence, (kind, resulting, reason, rule_id) in enumerate(changes):
                            event_key = f"{identity_input}|{field_id}|{kind.value}|{sequence}|{rule_id}"
                            # Serialize one sparse record directly; constructing millions of
                            # Pydantic objects adds CPU/RSS without strengthening the contract.
                            record = {
                                "transformation_id": "tr:" + hashlib.sha256(event_key.encode()).hexdigest()[:20],
                                "analysis_id": semantics.analysis_id,
                                "source_document_id": semantics.source_document_id,
                                "source_row_id": source_row_id, "row_id": source_row_id,
                                "source_field_id": field_id, "transformation_type": kind.value,
                                "source_value": _json_value(source_value),
                                "resulting_value": _json_value(resulting),
                                "reason": reason, "rule_id": rule_id,
                                "timestamp": started_at.isoformat(),
                            }
                            lineage.write(json.dumps(record, ensure_ascii=False,
                                                     separators=(",", ":"), default=_json_value) + "\n")
                            transformations_by_type[kind.value] += 1
                            transformations_by_field[field_id] += 1
                    row = PreparedRow(source_row_id=source_row_id, sheet_name=chunk.sheet_name,
                                      source_row_number=row_number, values=effective)
                    writer.writerow([source_row_id, chunk.sheet_name, row_number,
                                     *[_safe_csv_value(effective.get(field.source_field_id))
                                       for field in schema]])
                    logical_hash.update(_logical_row_bytes(row)); processed += 1
                    if len(preview) < preview_rows:
                        preview.append({"source_row_id": source_row_id, "sheet_name": chunk.sheet_name,
                                        "source_row_number": row_number,
                                        **{schema_by_id[key].source_name: value for key, value in effective.items()}})
                output.flush(); lineage.flush()
                progress("TRANSFORM_CHUNK", processed, total_hint,
                         f"Aplicando transformações: {processed:,} linhas")
                if fail_after_chunks is not None and chunk_number >= fail_after_chunks:
                    raise RuntimeError(f"Falha injetada após chunk {chunk_number}")
            os.fsync(output.fileno())
        progress("FINGERPRINT", processed, total_hint, "Calculando fingerprint")
        os.replace(partial_path, final_path)
        os.replace(transformations_partial, transformations_path)
        size = final_path.stat().st_size
        artifact_sha256 = _file_sha256(final_path)
        metrics.rows=processed; metrics.columns=len(schema)
        metrics.estimated_dataframe_memory_bytes=estimated_max
        metrics.artifact_size_bytes=size; metrics.status=PreparedGenerationStatus.COMPLETED
        metrics.finished_at=datetime.now(timezone.utc); metrics.rss_end_mb=_rss_mb()
        progress("PERSISTED", processed, total_hint, "Persistindo metadados: concluído")
        if status_callback:
            status_callback(PreparedGenerationStatus.COMPLETED, "COMPLETED", None)
        unresolved_count = len(quality_report.issues) if quality_report else 0
        return PreparedDatasetArtifact(
            prepared_dataset_id=prepared_id, source_document_id=semantics.source_document_id,
            analysis_id=semantics.analysis_id, version=version,
            ruleset_version=policy.ruleset_version, row_count=processed, field_count=len(schema),
            status=_gate(quality_report, policy), generation_status=PreparedGenerationStatus.COMPLETED,
            schema=schema, transformation_summary=dict(sorted(transformations_by_type.items())),
            transformations_by_field=dict(sorted(transformations_by_field.items())),
            total_transformations=sum(transformations_by_type.values()),
            statistics={"source_row_count": processed, "prepared_row_count": processed,
                        "source_field_count": len(schema), "prepared_field_count": len(schema),
                        "transformation_count": sum(transformations_by_type.values()),
                        "open_issue_count": unresolved_count,
                        "memory_budget_mb": memory_budget_mb, "chunk_size": chunk_size},
            fingerprint=logical_hash.hexdigest(), artifact_location=str(final_path),
            transformations_location=str(transformations_path), artifact_size_bytes=size,
            artifact_sha256=artifact_sha256,
            preview=preview, metrics=metrics,
        )
    except BaseException as error:
        metrics.status = PreparedGenerationStatus.FAILED
        metrics.finished_at=datetime.now(timezone.utc); metrics.rss_end_mb=_rss_mb()
        if status_callback:
            status_callback(PreparedGenerationStatus.FAILED, "FAILED", type(error).__name__)
        raise


def verify_prepared_artifact(artifact: PreparedDatasetArtifact) -> None:
    path = Path(artifact.artifact_location)
    if artifact.generation_status != PreparedGenerationStatus.COMPLETED:
        raise ValueError("Prepared Dataset não está concluído.")
    if path.name.endswith(".partial") or not path.is_file():
        raise ValueError("ANALYSIS_RECOVERY_WARNING: artefato Prepared ausente ou parcial")
    if path.stat().st_size != artifact.artifact_size_bytes:
        raise ValueError("ANALYSIS_RECOVERY_WARNING: tamanho do artefato Prepared diverge")
    if _file_sha256(path) != artifact.artifact_sha256:
        raise ValueError("ANALYSIS_RECOVERY_WARNING: fingerprint físico do artefato diverge")
