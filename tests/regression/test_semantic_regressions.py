"""Focused pipeline regressions discovered during real exploratory validation."""

from tests.golden.pipeline import run_golden_pipeline


def test_placeholders_do_not_create_mixed_semantic_content() -> None:
    _, report, fields, _ = run_golden_pipeline()
    assert fields["ano_referencia"].placeholder_count == 2
    assert fields["ano_referencia"].detected_type == "integer"
    assert "ano_referencia" not in {q.technical_name for q in report.questions}


def test_valid_brazilian_dates_do_not_create_false_conflict() -> None:
    _, _, fields, decisions = run_golden_pipeline()
    assert fields["data_lancamento"].semantic_role_candidate.value == "date"
    assert "date_name_non_date_content" not in {
        conflict.code for conflict in decisions["data_lancamento"].conflicts
    }


def test_quantitative_fields_do_not_regress_to_numeric_codes() -> None:
    _, _, fields, _ = run_golden_pipeline()
    for name in ("valor_total", "valor_movimento", "valor_estorno"):
        assert fields[name].semantic_role_candidate.value == "measure"


def test_real_numeric_code_remains_plausible() -> None:
    _, _, fields, _ = run_golden_pipeline()
    assert fields["codigo_evento"].semantic_role_candidate.value == "code"
