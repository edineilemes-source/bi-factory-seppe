"""Synthetic regressions inspired by real identifier failures."""

from copy import deepcopy

from core.ingestion.file_loader import LoadedSheet, LoadedWorkbook
from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.profiling.field_profiler import profile_field
from core.profiling.identifiers import canonicalize_identifier, identifier_pattern
from core.profiling.models import SemanticRole
from core.profiling.workbook_profiler import profile_workbook
from core.quality.engine import analyze_data_quality
from core.quality.models import (
    FieldQualityStatus, IdentifierConstraint, QualityIssueType, QualitySeverity,
)
from core.semantic.decision_engine import DecisionLevel, decide_field
from core.semantic.models import ValidationStatus
from core.semantic.validation_service import create_validation_report


def _workbook(identifiers) -> LoadedWorkbook:
    rows = [["Aux Sub Empenho", "Evento"]]
    rows.extend([[value, f"evento-{index}"] for index, value in enumerate(identifiers)])
    return LoadedWorkbook(
        original_name="identificadores_sinteticos.csv", source_type="browser_upload",
        size_bytes=1, file_type="csv", sheets=[LoadedSheet(
            name="Dados", rows=rows, approximate_row_count=len(rows),
            approximate_column_count=2)],
    )


def _validated_identifier_pipeline(values):
    workbook = _workbook(values)
    semantic = create_validation_report(profile_workbook(workbook))
    semantic.analysis_id = "identifier-hardening"
    semantic.source_document_id = "sha256:identifier-hardening"
    validation = next(item for item in semantic.validated_semantics
                      if item.technical_name == "aux_sub_empenho")
    validation.validated_role = SemanticRole.IDENTIFIER
    validation.validation_status = ValidationStatus.USER_CONFIRMED
    return workbook, semantic, validation.source_field_id


def test_identifier_canonicalization_preserves_semantics_not_float_artifacts():
    assert canonicalize_identifier(833.0) == "833"
    assert canonicalize_identifier(835.0) == "835"
    assert canonicalize_identifier(727.0) == "727"
    assert identifier_pattern(833.0) == "999"
    assert identifier_pattern(12345.0) == "99999"
    assert canonicalize_identifier("00123") == "00123"
    assert identifier_pattern("00123") == "99999"
    assert canonicalize_identifier("12E45") == "12E45"
    assert identifier_pattern("12E45") == "99A99"
    assert canonicalize_identifier("12E45") != canonicalize_identifier("12345")


def test_float_operational_identifier_is_identifier_and_requires_confirmation():
    field = profile_field(
        "Aux Sub Empenho", "aux_sub_empenho",
        [2026360.0, 2026345.0, 2026351.0, 2026404.0, 2026269.0],
    )
    assert field.semantic_role_candidate == SemanticRole.IDENTIFIER
    assert decide_field(field).level == DecisionLevel.CONFIRM
    assert not (field.semantic_role_candidate == SemanticRole.MEASURE
                and decide_field(field).level == DecisionLevel.AUTO_ACCEPT)


def test_float_pattern_and_levenshtein_do_not_create_reconciliation_candidate():
    values = [833.0, 835.0, 727.0, 8330.0, "12E45"]
    workbook, semantic, _ = _validated_identifier_pipeline(values)
    before = deepcopy(workbook.sheets[0].rows)
    report = analyze_data_quality(workbook, semantic)
    issue = next(item for item in report.issues
                 if item.issue_type == QualityIssueType.IDENTIFIER_INCONSISTENCY)
    assert issue.evidence["dominant_pattern"] == "999"
    assert issue.evidence["dominant_pattern"] != "999.9"
    assert report.reconciliation_candidates == []
    assert workbook.sheets[0].rows == before


def test_repeated_identifier_without_uniqueness_is_neutral_diagnostic():
    workbook, semantic, field_id = _validated_identifier_pipeline([833.0, 833.0, 835.0])
    report = analyze_data_quality(workbook, semantic)
    field = next(item for item in report.field_summaries
                 if item.source_field_id == field_id)
    duplicate = next(item for item in report.issues
                     if item.issue_type == QualityIssueType.DUPLICATE_VALUE)
    assert duplicate.severity == QualitySeverity.INFO
    assert duplicate.evidence["quality_defect"] is False
    assert field.quality_status == FieldQualityStatus.NEEDS_BUSINESS_RULE
    assert field.quality_score == 100


def test_explicit_uniqueness_turns_repetition_into_quality_defect():
    workbook, semantic, field_id = _validated_identifier_pipeline([833.0, 833.0, 835.0])
    report = analyze_data_quality(
        workbook, semantic,
        identifier_constraints={field_id: IdentifierConstraint(unique=True)},
    )
    field = next(item for item in report.field_summaries
                 if item.source_field_id == field_id)
    duplicate = next(item for item in report.issues
                     if item.issue_type == QualityIssueType.DUPLICATE_VALUE)
    assert duplicate.severity == QualitySeverity.ERROR
    assert duplicate.evidence["quality_defect"] is True
    assert field.quality_score < 100


def test_aux_sub_empenho_survives_persistence_resume_and_quality_reanalysis(tmp_path):
    workbook = _workbook([2026360.0, 2026345.0, 2026351.0, 2026404.0, 2026269.0])
    profile = profile_workbook(workbook)
    field = next(item for item in profile.sheets[0].fields
                 if item.technical_name == "aux_sub_empenho")
    assert field.semantic_role_candidate == SemanticRole.IDENTIFIER
    assert decide_field(field).level == DecisionLevel.CONFIRM

    repository = SQLiteAnalysisRepository(tmp_path / "aux-regression.sqlite3")
    document = repository.register_document(b"aux-regression", "aux.csv")
    analysis = repository.create_analysis(document.source_document_id, profile)
    validation = next(item for item in analysis.report.validated_semantics
                      if item.technical_name == "aux_sub_empenho")
    validation.validated_role = SemanticRole.IDENTIFIER
    validation.validation_status = ValidationStatus.USER_CONFIRMED
    repository.save_report(analysis.report)

    resumed = repository.get_analysis(analysis.analysis_id)
    resumed_validation = next(item for item in resumed.report.validated_semantics
                              if item.technical_name == "aux_sub_empenho")
    assert resumed_validation.validated_role == SemanticRole.IDENTIFIER
    first = repository.save_quality_report(analyze_data_quality(workbook, resumed.report))
    second = repository.save_quality_report(analyze_data_quality(workbook, resumed.report))
    for quality in (first, second, repository.get_quality_report(analysis.analysis_id)):
        summary = next(item for item in quality.field_summaries
                       if item.source_field_id.endswith("::aux_sub_empenho"))
        assert summary.effective_semantic_role == SemanticRole.IDENTIFIER
        assert summary.effective_semantic_role != SemanticRole.MEASURE
