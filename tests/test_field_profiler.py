"""Tests for individual field profiling."""

from core.profiling.field_profiler import profile_field


def test_profile_field_detects_measure_and_nulls() -> None:
    profile = profile_field("Valor Total", "valor_total", [10, 20.5, None, 40])

    assert profile.detected_type == "number"
    assert profile.recommended_type == "decimal"
    assert profile.null_count == 1
    assert profile.null_percentage == 25.0
    assert profile.distinct_count == 3
    assert profile.is_possible_measure is True


def test_profile_field_detects_candidate_key() -> None:
    profile = profile_field("Código", "codigo", ["A", "B", "C"])

    assert profile.is_candidate_key is True


def test_profile_field_warns_about_mixed_types_and_high_null_rate() -> None:
    profile = profile_field("Valor", "valor", [1, "inválido", None, None])

    assert profile.detected_type == "mixed"
    assert {warning.code for warning in profile.warnings} == {
        "high_null_rate",
        "mixed_types",
    }


def test_time_components_are_not_measures() -> None:
    year = profile_field("Ano", "ano", [2024, 2025, 2026])
    month = profile_field("Mês", "mes", [1, 2, 3, 4])
    assert year.semantic_role_candidate.value == "time_component"
    assert month.semantic_role_candidate.value == "time_component"
    assert not year.is_possible_measure


def test_document_number_and_numeric_code_are_not_measures() -> None:
    document = profile_field("Número Documento", "numero_documento", [1001, 1002, 1003])
    code = profile_field("Código Tipo", "codigo_tipo", [10, 20, 10, 30])
    assert document.semantic_role_candidate.value == "identifier"
    assert code.semantic_role_candidate.value == "code"
    assert not document.is_possible_measure and not code.is_possible_measure


def test_long_identifier_with_leading_zero_is_text() -> None:
    profile = profile_field("Identificador", "identificador", ["00123456789012", "00123456789013"])
    assert profile.semantic_role_candidate.value == "identifier"
    assert profile.recommended_type == "text"
    assert "leading_zero_risk" in {warning.code for warning in profile.warnings}


def test_positive_measure_evidence() -> None:
    money = profile_field("Valor Total", "valor_total", [10.5, 20.25, 31.75])
    percentage = profile_field("Percentual", "percentual", [5.0, 12.5, 80.0])
    assert money.semantic_role_candidate.value == "measure"
    assert percentage.semantic_role_candidate.value == "measure"


def test_description_and_category() -> None:
    description = profile_field("Descrição", "descricao", [
        "Texto livre suficientemente longo para descrever o primeiro registro",
        "Outro conteúdo textual detalhado e distinto para o segundo registro",
    ])
    category = profile_field("Status", "status", ["A", "A", "B", "A", "B", "A"])
    assert description.semantic_role_candidate.value == "description"
    assert category.semantic_role_candidate.value == "category"


def test_empty_and_constant_sample_warnings() -> None:
    empty = profile_field("Data Final", "data_final", [None, "", None])
    constant = profile_field("Versão", "versao", [2026, 2026, 2026])
    assert empty.sample_status.value == "empty_in_sample"
    assert empty.semantic_role_candidate.value == "unknown"
    assert empty.semantic_role_confidence < .5
    assert "empty_in_sample" in {warning.code for warning in empty.warnings}
    assert "semantic_inference_deferred_no_evidence" in {
        warning.code for warning in empty.warnings
    }
    assert constant.distinct_count == 1 and constant.constant_value == 2026
    assert "constant_field" in {warning.code for warning in constant.warnings}


def test_date_can_be_inferred_from_parseable_values() -> None:
    profile = profile_field(
        "Ocorrência", "ocorrencia",
        ["01/01/2026", "02/01/2026", "03/01/2026", "04/01/2026", "inválida"],
    )
    assert profile.semantic_role_candidate.value == "date"
    assert profile.semantic_role_confidence >= .8
