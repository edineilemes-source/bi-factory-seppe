"""Acceptance of a realistic profile through the complete business pipeline."""

from tests.golden.expected_semantics import EXPECTED_ASKED_FIELDS, EXPECTED_SEMANTICS
from tests.golden.pipeline import run_golden_pipeline


EXPECTED_MAX_REQUIRED_QUESTIONS = 1


def test_realistic_profile_reaches_expected_validation_report() -> None:
    profile, report, fields, decisions = run_golden_pipeline()
    asked_fields = {question.technical_name for question in report.questions}

    assert profile.summary.total_columns == len(EXPECTED_SEMANTICS)
    assert asked_fields == EXPECTED_ASKED_FIELDS
    assert len(report.questions) <= EXPECTED_MAX_REQUIRED_QUESTIONS
    assert {"ano_referencia", "data_lancamento", "valor_total"}.isdisjoint(asked_fields)
    assert decisions["ano_referencia"].level.value == "auto_accept"
    assert decisions["data_lancamento"].level.value == "auto_accept"
    assert decisions["valor_total"].level.value == "auto_accept"
    assert fields["valor_movimento"].semantic_role_candidate.value != "code"
