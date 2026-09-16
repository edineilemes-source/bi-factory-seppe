"""Focused regressions for Sprint 1.4.1 semantic corrections."""

import sqlite3

from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.profiling.field_profiler import profile_field
from core.profiling.models import ProjectContext, SemanticRole, SheetProfile, WorkbookProfile, WorkbookSummary
from core.semantic.decision_engine import DecisionLevel, decide_field, detect_conflicts
from core.semantic.validation_service import create_validation_report


def _workbook(*fields) -> WorkbookProfile:
    return WorkbookProfile(
        context=ProjectContext(), original_name="sprint.csv", source_type="browser_upload",
        size_bytes=10, file_type="csv",
        summary=WorkbookSummary(sheet_count=1, total_approximate_rows=10,
                                total_columns=len(fields), warning_count=0),
        sheets=[SheetProfile(name="Dados", role_hypothesis="A validar",
                             approximate_row_count=10, column_count=len(fields),
                             sampled_data_row_count=10, fields=list(fields))],
    )


def _warning_codes(field) -> set[str]:
    return {warning.code for warning in field.warnings}


def test_high_confidence_time_component_is_auto_accept_without_question() -> None:
    field = profile_field("Ano Referência", "ano_referencia", [2024, 2025, 2026])
    assert field.semantic_role_confidence == .92
    assert decide_field(field).level == DecisionLevel.AUTO_ACCEPT
    assert create_validation_report(_workbook(field)).questions == []


def test_brazilian_dates_are_dates_and_do_not_create_false_conflict() -> None:
    field = profile_field("Data Movimento", "data_movimento", [
        "14/01/2026", "15/01/2026", "31/12/2025",
    ])
    assert field.detected_type == "date"
    assert field.semantic_role_candidate == SemanticRole.DATE
    assert "date_name_non_date_content" not in {c.code for c in detect_conflicts(field)}
    assert any("DD/MM/YYYY" in evidence for evidence in field.semantic_evidence)


def test_pagamento_alone_is_not_date_and_long_text_wins_over_name() -> None:
    short = profile_field("Pagamento", "pagamento", ["PIX", "TED", "DINHEIRO"])
    long = profile_field("Pagamento", "pagamento", [
        "Pagamento relativo à prestação detalhada do serviço de manutenção preventiva",
        "Registro descritivo do pagamento associado ao atendimento técnico especializado",
        "Explicação completa sobre pagamento e demais condições pactuadas no documento",
    ])
    assert short.semantic_role_candidate != SemanticRole.DATE
    assert long.semantic_role_candidate == SemanticRole.DESCRIPTION
    assert long.semantic_role_candidate != SemanticRole.DATE


def test_repeated_stable_numeric_values_are_code_not_date_or_measure() -> None:
    field = profile_field("Classificação", "classificacao", [
        701001, 708001, 704001, 718001, 701001, 708001, 704001, 718001,
    ])
    assert field.semantic_role_candidate == SemanticRole.CODE
    assert field.semantic_role_candidate not in {SemanticRole.DATE, SemanticRole.MEASURE}
    assert any("comprimento estável" in evidence for evidence in field.semantic_evidence)


def test_real_ambiguity_and_low_confidence_unknown_are_asked() -> None:
    ambiguous = profile_field("Identificador", "identificador", [1, 1, 1, 2, 2, 2])
    unknown = profile_field("Campo X", "campo_x", ["abc", "def", "ghi"])
    assert decide_field(ambiguous).level == DecisionLevel.ASK
    assert unknown.semantic_role_candidate == SemanticRole.UNKNOWN
    assert decide_field(unknown).level == DecisionLevel.ASK


def test_near_constant_uses_modal_concentration_and_constant_is_preserved() -> None:
    distributed = profile_field("Mês", "mes", [
        "jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago"
    ] * 1250)
    concentrated = profile_field("Situação", "situacao", ["A"] * 990 + ["B"] * 10)
    constant = profile_field("Versão", "versao", [2026] * 20)
    assert "near_constant_field" not in _warning_codes(distributed)
    assert "near_constant_field" in _warning_codes(concentrated)
    assert "constant_field" in _warning_codes(constant)


def test_confirm_is_reported_but_not_a_mandatory_question() -> None:
    confirm = profile_field("Código", "codigo", [10, 20, 30, 40])
    ask = profile_field("Campo X", "campo_x", ["abc", "def", "ghi"])
    report = create_validation_report(_workbook(confirm, ask))
    assert decide_field(confirm).level == DecisionLevel.CONFIRM
    assert report.summary.need_confirmation == 1
    assert len(report.questions) == 1
    assert report.questions[0].technical_name == "campo_x"


def test_auto_accept_question_is_not_persisted(tmp_path) -> None:
    repository = SQLiteAnalysisRepository(tmp_path / "analysis.sqlite3")
    document = repository.register_document(b"content", "data.csv")
    field = profile_field("Ano", "ano", [2024, 2025, 2026])
    record = repository.create_analysis(document.source_document_id, _workbook(field))
    assert record.report.questions == []
    with sqlite3.connect(repository.database_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM semantic_questions WHERE analysis_id = ?",
            (record.analysis_id,),
        ).fetchone()[0]
    assert count == 0
