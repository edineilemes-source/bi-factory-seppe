from core.ingestion.file_loader import LoadedSheet, LoadedWorkbook
from core.profiling.field_profiler import profile_field
from core.profiling.models import ProjectContext, SemanticRole, SheetProfile, WorkbookProfile, WorkbookSummary
from core.quality.engine import analyze_data_quality
from core.quality.gate import is_blocking_issue
from core.quality.models import (
    FieldApplicability, FieldRequirement, IdentifierConstraint,
    QualityDefectStatus, QualityGateStatus, QualityIssueType,
)
from core.semantic.validation_service import create_validation_report


def _analyze(values, role, *, requirement=None, applicability=None, constraint=None):
    field = profile_field("Campo", "campo", values)
    field.semantic_role_candidate = role
    profile = WorkbookProfile(
        context=ProjectContext(), original_name="gate.csv", source_type="browser_upload",
        size_bytes=10, file_type="csv",
        summary=WorkbookSummary(sheet_count=1, total_approximate_rows=len(values),
                                total_columns=1, warning_count=0),
        sheets=[SheetProfile(name="Dados", role_hypothesis="A validar",
            approximate_row_count=len(values)+1, column_count=1, probable_header_row=1,
            sampled_data_row_count=len(values), fields=[field])])
    semantics = create_validation_report(profile)
    semantics.analysis_id = "quality-gate"
    semantics.source_document_id = "sha256:gate"
    workbook = LoadedWorkbook("gate.csv", "browser_upload", 10, "csv",
        [LoadedSheet("Dados", [["Campo"], *[[value] for value in values]],
                     len(values)+1, 1)])
    field_id = "Dados::campo"
    return analyze_data_quality(
        workbook, semantics,
        requirements={field_id: requirement} if requirement else None,
        applicabilities={field_id: applicability} if applicability else None,
        identifier_constraints={field_id: constraint} if constraint else None,
    )


def _issue(report, kind):
    return next(item for item in report.issues if item.issue_type == kind)


def test_identifier_length_variation_without_rule_is_non_blocking():
    report = _analyze([1000, 1000, 1000, 727, 833], SemanticRole.IDENTIFIER)
    issue = _issue(report, QualityIssueType.IDENTIFIER_INCONSISTENCY)
    assert issue.evidence["observation_class"] == "IDENTIFIER_LENGTH_VARIATION"
    assert issue.quality_defect_status == QualityDefectStatus.NEEDS_BUSINESS_RULE
    assert not is_blocking_issue(issue)
    assert report.gate_decision.status == QualityGateStatus.READY_WITH_WARNINGS


def test_validated_four_digit_mask_violation_is_confirmed_and_blocking():
    report = _analyze([1000, 1001, 833], SemanticRole.IDENTIFIER,
        constraint=IdentifierConstraint(pattern=r"^\d{4}$", exact_length=4, validated=True))
    issue = _issue(report, QualityIssueType.INVALID_IDENTIFIER_FORMAT)
    assert issue.quality_defect_status == QualityDefectStatus.CONFIRMED_DEFECT
    assert is_blocking_issue(issue)
    assert report.gate_decision.status == QualityGateStatus.BLOCKED


def test_levenshtein_code_creates_candidate_only():
    report = _analyze(["160", "160", "1600"], SemanticRole.CODE)
    issue = _issue(report, QualityIssueType.DOMAIN_INCONSISTENCY)
    assert issue.quality_defect_status == QualityDefectStatus.SUSPECTED
    assert not is_blocking_issue(issue)
    assert report.reconciliation_candidates[0].requires_validation


def test_text_category_similarity_keeps_finisa_values_distinct():
    report = _analyze(["FINISA 3 - ANOS ANTERIORES"] * 2 +
                      ["FINISA 5 - ANOS ANTERIORES"], SemanticRole.CATEGORY)
    issue = _issue(report, QualityIssueType.DOMAIN_INCONSISTENCY)
    assert issue.evidence["candidate_only"] is True
    assert issue.quality_defect_status == QualityDefectStatus.SUSPECTED
    assert not is_blocking_issue(issue)


def test_iqr_outlier_is_observation_and_non_blocking():
    report = _analyze([0, 0, 0, 0, 1, 2, 100], SemanticRole.MEASURE)
    issue = _issue(report, QualityIssueType.OUTLIER)
    assert issue.quality_defect_status == QualityDefectStatus.OBSERVED_ANOMALY
    assert not is_blocking_issue(issue)


def test_required_applicable_missing_is_blocking():
    report = _analyze([1, None, 2], SemanticRole.MEASURE,
        requirement=FieldRequirement.REQUIRED,
        applicability=FieldApplicability.APPLICABLE)
    issue = _issue(report, QualityIssueType.MISSING_VALUE)
    assert issue.quality_defect_status == QualityDefectStatus.CONFIRMED_DEFECT
    assert is_blocking_issue(issue)


def test_unknown_requirement_missing_needs_rule_and_does_not_block():
    report = _analyze(["x", None], SemanticRole.DESCRIPTION)
    issue = _issue(report, QualityIssueType.MISSING_VALUE)
    assert issue.quality_defect_status == QualityDefectStatus.NEEDS_BUSINESS_RULE
    assert not is_blocking_issue(issue)


def test_optional_missing_is_not_a_defect():
    report = _analyze(["x", None], SemanticRole.DESCRIPTION,
        requirement=FieldRequirement.OPTIONAL,
        applicability=FieldApplicability.APPLICABLE)
    issue = _issue(report, QualityIssueType.MISSING_VALUE)
    assert issue.quality_defect_status == QualityDefectStatus.NOT_A_DEFECT
    assert not is_blocking_issue(issue)


def test_duplicate_identifier_without_unique_rule_is_non_blocking():
    report = _analyze([1, 1, 2], SemanticRole.IDENTIFIER)
    issue = _issue(report, QualityIssueType.DUPLICATE_VALUE)
    assert issue.quality_defect_status == QualityDefectStatus.NEEDS_BUSINESS_RULE
    assert not is_blocking_issue(issue)


def test_unique_constraint_violation_is_blocking():
    report = _analyze([1, 1, 2], SemanticRole.IDENTIFIER,
                      constraint=IdentifierConstraint(unique=True, validated=True))
    issue = _issue(report, QualityIssueType.DUPLICATE_VALUE)
    assert issue.quality_defect_status == QualityDefectStatus.CONFIRMED_DEFECT
    assert is_blocking_issue(issue)
