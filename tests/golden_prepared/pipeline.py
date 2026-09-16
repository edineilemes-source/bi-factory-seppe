"""Deterministic synthetic fixture for Sprint 2.2."""

from core.ingestion.file_loader import LoadedSheet, LoadedWorkbook
from core.profiling.models import ProjectContext, SemanticRole
from core.profiling.workbook_profiler import profile_workbook
from core.quality.models import (
    DataQualityReport, QualityIssue, QualityIssueType, QualitySeverity, QualityStatus,
)
from core.semantic.validation_service import create_validation_report


def golden_prepared_inputs():
    source_rows = [
        ["identifier", "malformed_identifier", "label", "placeholder", "date_br",
         "negative_measure", "outlier_measure", "empty_deferred"],
        [833.0, "12E45", " ABC ", "-", "14/01/2026", -100.50, 1, None],
        ["00123", "12E45", "ABC", "ok", "15/01/2026", 10, 2, None],
        ["00123", "ZX9", " ABC ", "N/A", "16/01/2026", 20, 3, None],
        [833.0, "12E45", "ABC", "NULL", "17/01/2026", 30, 999999, None],
    ]
    workbook = LoadedWorkbook(
        original_name="golden-prepared.xlsx", source_type="browser_upload",
        size_bytes=1, file_type="xlsx",
        sheets=[LoadedSheet("Dados", source_rows, len(source_rows), len(source_rows[0]))],
    )
    semantic = create_validation_report(profile_workbook(workbook, ProjectContext()))
    semantic.analysis_id = "golden-prepared"
    semantic.source_document_id = "sha256:golden-prepared"
    roles = {
        "identifier": SemanticRole.IDENTIFIER,
        "malformed_identifier": SemanticRole.IDENTIFIER,
        "label": SemanticRole.CATEGORY,
        "placeholder": SemanticRole.CATEGORY,
        "date_br": SemanticRole.DATE,
        "negative_measure": SemanticRole.MEASURE,
        "outlier_measure": SemanticRole.MEASURE,
        "empty_deferred": SemanticRole.UNKNOWN,
    }
    for validation in semantic.validated_semantics:
        validation.validated_role = roles[validation.technical_name]
    warning = QualityIssue(
        issue_id="golden-warning", analysis_id=semantic.analysis_id,
        source_field_id="Dados::outlier_measure", sheet_name="Dados",
        field_name="outlier_measure", issue_type=QualityIssueType.OUTLIER,
        severity=QualitySeverity.WARNING, affected_count=1, affected_percentage=25,
        examples=[999999], row_numbers=[5], reason="Outlier informativo permanece na fonte.",
    )
    quality = DataQualityReport(
        analysis_id=semantic.analysis_id, status=QualityStatus.COMPLETED_WITH_ISSUES,
        total_rows=4, total_fields=8, issues_count=1, affected_rows=1,
        warning_count=1, issues=[warning], field_summaries=[],
    )
    return workbook, semantic, quality
