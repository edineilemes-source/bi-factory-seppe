import pytest

from core.profiling.identifiers import canonicalize_identifier, identifier_pattern
from core.quality.models import QualityIssueType, QualitySeverity
from tests.golden_quality.pipeline import expectations, golden_quality_result


def test_golden_quality_declarative_contract():
    report, expected = golden_quality_result(), expectations()
    kinds = {issue.issue_type.value for issue in report.issues}
    assert set(expected["required_issue_types"]) <= kinds
    assert report.total_rows == expected["expected_rows"]
    assert report.total_fields == expected["expected_fields"]
    duplicate = next(i for i in report.issues if i.issue_type == QualityIssueType.DUPLICATE_RECORD)
    assert duplicate.affected_count == expected["expected_duplicate_records"]


def test_golden_protected_false_positives():
    report = golden_quality_result()
    duplicate = next(i for i in report.issues if i.issue_type == QualityIssueType.DUPLICATE_RECORD)
    assert duplicate.affected_count == 1  # repeated 12345 rows differ and are not records duplicated
    invalid_measure = [i for i in report.issues if (i.source_field_id or "").endswith("::medida")
                       and i.issue_type == QualityIssueType.INVALID_TYPE]
    assert all(-1 not in i.examples for i in invalid_measure)
    outlier = next(i for i in report.issues if i.issue_type == QualityIssueType.OUTLIER)
    assert outlier.severity == QualitySeverity.WARNING
    missing = next(i for i in report.issues if i.issue_type == QualityIssueType.MISSING_VALUE)
    placeholder = next(i for i in report.issues if i.issue_type == QualityIssueType.PLACEHOLDER_VALUE)
    assert missing.row_numbers != placeholder.row_numbers


def test_source_values_are_immutable_and_issues_are_grouped():
    from pathlib import Path
    from core.ingestion.file_loader import load_tabular_file
    raw = Path(__file__).with_name("dataset.csv").read_bytes()
    workbook = load_tabular_file("dataset.csv", raw)
    before = [[list(row) for row in sheet.rows] for sheet in workbook.sheets]
    golden_quality_result()
    assert [[list(row) for row in sheet.rows] for sheet in workbook.sheets] == before
    report = golden_quality_result()
    assert len([i for i in report.issues if i.issue_type == QualityIssueType.DUPLICATE_VALUE]) == 1
    assert 0 <= report.score <= 100


@pytest.mark.parametrize(("source", "canonical", "pattern"), [
    (833.0, "833", "999"),
    ("00123", "00123", "99999"),
    ("12E45", "12E45", "99A99"),
])
def test_golden_identifier_canonical_forms(source, canonical, pattern):
    assert canonicalize_identifier(source) == canonical
    assert identifier_pattern(source) == pattern


def test_golden_repeated_identifier_is_neutral_and_reconciliation_is_conservative():
    report = golden_quality_result()
    duplicate = next(item for item in report.issues
                     if item.issue_type == QualityIssueType.DUPLICATE_VALUE)
    assert duplicate.evidence["quality_defect"] is False
    assert report.reconciliation_candidates == []
