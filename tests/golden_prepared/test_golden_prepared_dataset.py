import csv
import io
import json
from pathlib import Path

from core.prepared.export import export_prepared_csv, export_transformations_json
from core.prepared.models import PreparedDatasetStatus, TransformationType
from core.prepared.service import prepare_dataset
from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.profiling.models import SemanticRole
from core.quality.models import ValueLayer
from tests.golden_prepared.pipeline import golden_prepared_inputs


def _field(dataset, technical_name):
    return next(item for item in dataset.schema_fields if item.technical_name == technical_name)


def test_value_layer_precedence_supports_explicit_normalized_null():
    assert ValueLayer(source_value="-").effective_value == "-"
    assert ValueLayer(source_value="-", normalized_value=None).effective_value is None
    assert ValueLayer(source_value="  ABC  ", normalized_value="ABC").effective_value == "ABC"
    assert ValueLayer(source_value="x", normalized_value="X",
                      validated_value="VALIDATED").effective_value == "VALIDATED"


def test_golden_prepared_values_invariance_and_source_immutability():
    workbook, semantic, quality = golden_prepared_inputs()
    before = [list(row) for row in workbook.sheets[0].rows]
    dataset = prepare_dataset(workbook, semantic, quality)
    fields = {item.technical_name: item.source_field_id for item in dataset.schema_fields}
    values = [row.values for row in dataset.rows]

    assert dataset.row_count == len(workbook.sheets[0].rows) - 1 == 4
    assert dataset.field_count == len(workbook.sheets[0].rows[0]) == 8
    assert values[0][fields["identifier"]] == "833"
    assert values[1][fields["identifier"]] == "00123"
    assert values[0][fields["malformed_identifier"]] == "12E45"
    assert values[0][fields["label"]] == "ABC"
    assert values[0][fields["placeholder"]] is None
    assert values[0][fields["date_br"]] == "2026-01-14"
    assert values[0][fields["negative_measure"]] == -100.50
    assert values[3][fields["outlier_measure"]] == 999999
    assert _field(dataset, "empty_deferred").quality_status.value == "not_evaluated"
    assert len({row.source_row_id for row in dataset.rows}) == dataset.row_count
    assert dataset.status == PreparedDatasetStatus.READY_WITH_WARNINGS
    assert dataset.unresolved_quality_issues == quality.issues
    assert workbook.sheets[0].rows == before


def test_audit_fingerprint_and_exports_match_effective_values():
    workbook, semantic, quality = golden_prepared_inputs()
    first = prepare_dataset(workbook, semantic, quality, version=1)
    second = prepare_dataset(workbook, semantic, quality, version=2)
    assert first.prepared_dataset_id != second.prepared_dataset_id
    assert first.version == 1 and second.version == 2
    assert first.fingerprint == second.fingerprint

    kinds = {item.transformation_type for item in first.transformations}
    assert {TransformationType.TRIM_WHITESPACE,
            TransformationType.PLACEHOLDER_TO_NULL,
            TransformationType.IDENTIFIER_CANONICALIZATION,
            TransformationType.DATE_CANONICALIZATION} <= kinds
    placeholder = next(item for item in first.transformations
                       if item.transformation_type == TransformationType.PLACEHOLDER_TO_NULL)
    assert placeholder.source_value in {"-", "N/A", "NULL"}
    assert placeholder.resulting_value is None

    exported = list(csv.DictReader(io.StringIO(
        export_prepared_csv(first).decode("utf-8-sig"))))
    assert len(exported) == first.row_count
    assert exported[0]["identifier"] == "833"
    assert exported[0]["placeholder"] == ""
    audit = json.loads(export_transformations_json(first))
    assert audit["fingerprint"] == first.fingerprint
    assert audit["transformation_count"] == len(first.transformations)
    assert sum(audit["summary"].values()) == len(first.transformations)


def test_repository_assigns_new_version_without_overwriting(tmp_path: Path):
    workbook, semantic, _ = golden_prepared_inputs()
    repository = SQLiteAnalysisRepository(tmp_path / "prepared.sqlite3")
    document = repository.register_document(b"golden prepared", "golden-prepared.xlsx")
    record = repository.create_analysis(document.source_document_id, semantic.observed_profile)
    roles = {item.technical_name: item.validated_role for item in semantic.validated_semantics}
    for item in record.report.validated_semantics:
        item.validated_role = roles.get(item.technical_name) or SemanticRole.UNKNOWN

    first = prepare_dataset(
        workbook, record.report, version=repository.next_prepared_version(record.analysis_id))
    repository.save_prepared_dataset(first)
    second = prepare_dataset(
        workbook, record.report, version=repository.next_prepared_version(record.analysis_id))
    repository.save_prepared_dataset(second)

    restored = repository.list_prepared_datasets(record.analysis_id)
    assert [item.version for item in restored] == [2, 1]
    assert restored[0].prepared_dataset_id != restored[1].prepared_dataset_id
    assert restored[0].fingerprint == restored[1].fingerprint
