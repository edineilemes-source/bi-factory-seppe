"""Golden contracts for contextual completeness introduced in Sprint 2.1.1."""

from core.ingestion.file_loader import LoadedSheet, LoadedWorkbook
from core.profiling.models import ProjectContext, SemanticRole
from core.profiling.workbook_profiler import profile_workbook
from core.quality.engine import analyze_data_quality
from core.quality.models import (
    FieldApplicability, FieldQualityStatus, FieldRequirement,
    QualityIssueType, QualitySeverity,
)
from core.semantic.models import DecisionLevel, ValidationStatus
from core.semantic.validation_service import create_validation_report


def _pipeline(values, *, name="Campo Contextual"):
    rows = [[name], *[[value] for value in values]]
    workbook = LoadedWorkbook(
        original_name="contextual.csv", source_type="browser_upload", size_bytes=1,
        file_type="csv", sheets=[LoadedSheet(
            name="Dados", rows=rows, approximate_row_count=len(rows),
            approximate_column_count=1)],
    )
    profile = profile_workbook(workbook, ProjectContext())
    # The tiny one-column synthetic fixture is intentionally explicit about its header.
    profile.sheets[0].probable_header_row = 1
    semantic = create_validation_report(profile)
    semantic.analysis_id = "golden-contextual"
    semantic.source_document_id = "sha256:golden-contextual"
    field_id = semantic.validated_semantics[0].source_field_id
    return workbook, semantic, field_id


def _missing_issues(report):
    return [issue for issue in report.issues
            if issue.issue_type in {QualityIssueType.MISSING_VALUE,
                                    QualityIssueType.PLACEHOLDER_VALUE}]


def test_empty_deferred_field_is_not_evaluated_and_excluded_from_score():
    workbook, semantic, field_id = _pipeline([None] * 10)
    semantic.decision_by_source_field[field_id] = DecisionLevel.DEFERRED_NO_EVIDENCE
    assert semantic.decision_by_source_field[field_id] == DecisionLevel.DEFERRED_NO_EVIDENCE
    report = analyze_data_quality(workbook, semantic)
    field = report.field_summaries[0]
    assert field.quality_status == FieldQualityStatus.NOT_EVALUATED
    assert field.quality_score is None and field.score is None
    assert report.eligible_cells == 0
    assert report.not_evaluated_fields == 1
    assert not _missing_issues(report)
    assert report.error_count == 0


def test_unknown_requirement_observes_missing_without_automatic_error():
    workbook, semantic, _ = _pipeline([None] * 9 + ["presente"])
    report = analyze_data_quality(workbook, semantic)
    field = report.field_summaries[0]
    assert field.requirement == FieldRequirement.UNKNOWN
    assert field.missing_percentage == 90
    assert field.observed_completeness == 10
    assert field.quality_status == FieldQualityStatus.NEEDS_BUSINESS_RULE
    assert report.error_count == 0
    assert all(issue.severity == QualitySeverity.INFO for issue in _missing_issues(report))


def test_required_applicable_missing_is_error():
    workbook, semantic, field_id = _pipeline([None] * 9 + ["presente"])
    report = analyze_data_quality(
        workbook, semantic,
        {field_id: FieldRequirement.REQUIRED},
        {field_id: FieldApplicability.APPLICABLE},
    )
    field = report.field_summaries[0]
    assert field.quality_status == FieldQualityStatus.EVALUATED
    assert field.quality_score == 10
    assert report.error_count == 1
    assert _missing_issues(report)[0].severity == QualitySeverity.ERROR


def test_optional_missing_is_not_error():
    workbook, semantic, field_id = _pipeline([None] * 9 + ["presente"])
    report = analyze_data_quality(
        workbook, semantic, {field_id: FieldRequirement.OPTIONAL})
    assert report.field_summaries[0].quality_score == 100
    assert report.error_count == 0


def test_conditional_missing_waits_for_business_condition():
    workbook, semantic, field_id = _pipeline([None] * 9 + ["presente"])
    report = analyze_data_quality(
        workbook, semantic,
        {field_id: FieldRequirement.CONDITIONAL},
        {field_id: FieldApplicability.CONDITIONAL},
    )
    assert report.field_summaries[0].quality_status == FieldQualityStatus.NEEDS_BUSINESS_RULE
    assert report.error_count == 0


def test_validated_role_wins_over_observed_role_in_quality():
    workbook, semantic, _ = _pipeline([10, 11, 12, 13, 14], name="Valor Ambíguo")
    validation = semantic.validated_semantics[0]
    validation.original_hypothesis = SemanticRole.MEASURE
    assert validation.original_hypothesis == SemanticRole.MEASURE
    validation.validated_role = SemanticRole.IDENTIFIER
    validation.validation_status = ValidationStatus.USER_CORRECTED
    report = analyze_data_quality(workbook, semantic)
    assert report.field_summaries[0].effective_semantic_role == SemanticRole.IDENTIFIER
