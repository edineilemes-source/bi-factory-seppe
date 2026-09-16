"""Synthetic ambiguity cases for Sprint 1.3."""

from datetime import date

from core.profiling.field_profiler import profile_field
from core.profiling.models import ProjectContext, SheetProfile, WorkbookProfile, WorkbookSummary
from core.semantic.decision_engine import DecisionLevel, DecisionSettings, decide_field, detect_conflicts
from core.semantic.models import QuestionStatus, ValidationStatus
from core.semantic.question_generator import OTHER_OPTION, ROLE_LABELS, UNKNOWN_OPTION
from core.semantic.validation_service import answer_question, create_validation_report


def _workbook(*fields):
    sheet = SheetProfile(
        name="Dados", role_hypothesis="A validar", approximate_row_count=10,
        column_count=len(fields), sampled_data_row_count=10, fields=list(fields),
    )
    return WorkbookProfile(
        context=ProjectContext(), original_name="sintetico.csv", source_type="browser_upload",
        size_bytes=100, file_type="csv", summary=WorkbookSummary(
            sheet_count=1, total_approximate_rows=10, total_columns=len(fields), warning_count=0,
        ), sheets=[sheet],
    )


def test_clear_money_is_auto_accepted() -> None:
    field = profile_field("Valor Total", "valor_total", [10.5, 20.25, 31.75])
    assert decide_field(field).level == DecisionLevel.AUTO_ACCEPT


def test_clear_date_is_auto_accepted() -> None:
    field = profile_field("Ocorrência", "ocorrencia", [date(2026, 1, 1), date(2026, 1, 2)])
    assert decide_field(field).level == DecisionLevel.AUTO_ACCEPT


def test_ambiguous_numeric_code_needs_confirmation() -> None:
    field = profile_field("Código", "codigo", [10, 20, 30, 40])
    assert decide_field(field).level == DecisionLevel.CONFIRM


def test_ambiguous_identifier_is_asked_due_to_distribution_conflict() -> None:
    field = profile_field("Identificador", "identificador", [1, 1, 1, 2, 2, 2])
    decision = decide_field(field)
    assert decision.level == DecisionLevel.ASK
    assert "identifier_name_category_distribution" in {item.code for item in decision.conflicts}


def test_name_content_conflict_is_asked_and_recorded() -> None:
    field = profile_field("Data Pagamento", "data_pagamento", [100, 200, 300])
    assert decide_field(field).level == DecisionLevel.ASK
    assert "date_name_non_date_content" in {item.code for item in detect_conflicts(field)}


def test_strong_date_content_suppresses_isolated_lexical_measure_hint() -> None:
    field = profile_field("Data Valor", "data_valor", [date(2026, 1, 1), date(2026, 1, 2)])
    decision = decide_field(field)
    assert decision.level == DecisionLevel.AUTO_ACCEPT
    assert "competing_name_roles" not in {item.code for item in decision.conflicts}


def test_unknown_is_asked() -> None:
    field = profile_field("Campo X", "campo_x", ["abc", "def", "ghi"])
    assert field.semantic_role_candidate.value == "unknown"
    assert decide_field(field).level == DecisionLevel.ASK


def test_thresholds_are_centralized_and_configurable() -> None:
    field = profile_field("Código", "codigo", [10, 20, 30, 40])
    settings = DecisionSettings(auto_accept_confidence=.80, confirm_confidence=.50)
    assert decide_field(field, settings).level == DecisionLevel.AUTO_ACCEPT


def test_report_only_creates_relevant_questions_with_context() -> None:
    money = profile_field("Valor Total", "valor_total", [10.5, 20.25, 31.75])
    unknown = profile_field("Campo X", "campo_x", ["abc", "def", "ghi"])
    report = create_validation_report(_workbook(money, unknown))
    assert len(report.questions) == 1
    question = report.questions[0]
    assert question.field_name == "Campo X"
    assert question.reason and question.question_text
    assert question.examples == ["abc", "def", "ghi"]
    assert UNKNOWN_OPTION in question.options and OTHER_OPTION in question.options


def test_user_confirms_hypothesis() -> None:
    field = profile_field("Identificador", "identificador", [1, 1, 1, 2, 2, 2])
    report = create_validation_report(_workbook(field))
    validation = answer_question(report, report.questions[0].question_id, ROLE_LABELS[field.semantic_role_candidate])
    assert validation.validation_status == ValidationStatus.USER_CONFIRMED
    assert validation.validated_role == field.semantic_role_candidate


def test_user_corrects_hypothesis() -> None:
    field = profile_field("Identificador", "identificador", [1, 1, 1, 2, 2, 2])
    report = create_validation_report(_workbook(field))
    validation = answer_question(report, report.questions[0].question_id, "Categoria ou situação")
    assert validation.validation_status == ValidationStatus.USER_CORRECTED
    assert validation.validated_role.value == "category"


def test_user_does_not_know_preserves_uncertainty() -> None:
    field = profile_field("Campo X", "campo_x", ["abc", "def"])
    report = create_validation_report(_workbook(field))
    validation = answer_question(report, report.questions[0].question_id, UNKNOWN_OPTION)
    assert validation.validation_status == ValidationStatus.UNRESOLVED
    assert validation.validated_role is None
    assert report.questions[0].status == QuestionStatus.SKIPPED


def test_custom_answer_is_preserved() -> None:
    field = profile_field("Campo X", "campo_x", ["abc", "def"])
    report = create_validation_report(_workbook(field))
    validation = answer_question(report, report.questions[0].question_id, OTHER_OPTION, "Número interno do processo")
    assert validation.user_answer == "Número interno do processo"
    assert validation.validation_status == ValidationStatus.USER_CORRECTED


def test_original_profiling_remains_unchanged_and_export_has_two_layers() -> None:
    field = profile_field("Identificador", "identificador", [1, 1, 1, 2, 2, 2])
    profile = _workbook(field)
    original = profile.model_dump(mode="json")
    report = create_validation_report(profile)
    answer_question(report, report.questions[0].question_id, "Categoria ou situação")
    exported = report.model_dump(mode="json")
    assert profile.model_dump(mode="json") == original
    assert set(("observed_profile", "validated_semantics")) <= exported.keys()
    assert exported["observed_profile"] == original
