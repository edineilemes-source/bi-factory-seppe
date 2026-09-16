"""Permanent executable semantic specification for the BI Factory."""

from tests.golden.expected_semantics import (
    EXPECTED_ASKED_FIELDS,
    EXPECTED_REQUIRED_QUESTIONS,
    EXPECTED_SEMANTICS,
)
from tests.golden.pipeline import run_golden_pipeline


def test_golden_semantic_pipeline_and_question_budget() -> None:
    _, report, fields, decisions = run_golden_pipeline()
    asked_fields = {question.technical_name for question in report.questions}

    actual_snapshot = {
        name: {
            "role": field.semantic_role_candidate.value,
            "decision": decisions[name].level.value,
            "required_question": name in asked_fields,
        }
        for name, field in fields.items()
    }
    expected_snapshot = {
        name: {key: value for key, value in expected.items()
               if key in {"role", "decision", "required_question"}}
        for name, expected in EXPECTED_SEMANTICS.items()
    }
    assert actual_snapshot == expected_snapshot
    assert len(report.questions) == EXPECTED_REQUIRED_QUESTIONS
    assert asked_fields == EXPECTED_ASKED_FIELDS

    assert "date_name_non_date_content" not in {
        conflict.code for conflict in decisions["data_lancamento"].conflicts
    }
    assert fields["descricao_evento"].semantic_role_candidate.value != "date"
    assert fields["codigo_evento"].semantic_role_candidate.value not in {"date", "measure"}
    assert fields["valor_total"].semantic_role_candidate.value != "code"
    assert fields["valor_estorno"].semantic_role_candidate.value != "code"
    assert fields["identificador_externo"].recommended_type == "text"
    assert "leading_zero_risk" in {
        warning.code for warning in fields["identificador_externo"].warnings
    }
    assert fields["identificador_externo"].examples[0].startswith("0")
    assert fields["classificacao_retencao_i"].non_null_count == 0
    assert decisions["classificacao_retencao_i"].level.value == "deferred_no_evidence"
    assert fields["devolvido"].semantic_role_candidate.value == "measure"
    assert "constant_field" in {
        warning.code for warning in fields["devolvido"].warnings
    }
    assert not (
        fields["aux_sub_empenho"].semantic_role_candidate.value == "measure"
        and decisions["aux_sub_empenho"].level.value == "auto_accept"
    )
