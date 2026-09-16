"""Real-world semantic regressions required by Sprint 1.4.3."""

from core.profiling.field_profiler import profile_field
from core.profiling.models import SemanticRole
from core.semantic.decision_engine import DecisionLevel, decide_field
from tests.golden.pipeline import run_golden_pipeline


def test_field_without_significant_values_is_deferred_and_never_asked() -> None:
    _, report, fields, decisions = run_golden_pipeline()
    field = fields["classificacao_retencao_i"]

    assert field.semantic_role_candidate == SemanticRole.UNKNOWN
    assert decisions[field.technical_name].level == DecisionLevel.DEFERRED_NO_EVIDENCE
    assert field.technical_name not in {question.technical_name for question in report.questions}


def test_constant_zero_devolvido_remains_measure() -> None:
    field = profile_field("Devolvido", "devolvido", [0] * 9_999)

    assert field.semantic_role_candidate == SemanticRole.MEASURE
    assert field.semantic_role_candidate != SemanticRole.CATEGORY
    assert decide_field(field).level == DecisionLevel.AUTO_ACCEPT
    assert "constant_field" in {warning.code for warning in field.warnings}


def test_aux_sub_empenho_is_not_auto_accepted_as_measure() -> None:
    field = profile_field(
        "Aux Sub Empenho", "aux_sub_empenho",
        [2026360, 2026345, 2026351, 2026404, 2026269],
    )

    assert field.semantic_role_candidate in {SemanticRole.IDENTIFIER, SemanticRole.CODE}
    assert decide_field(field).level == DecisionLevel.CONFIRM
    assert not (
        field.semantic_role_candidate == SemanticRole.MEASURE
        and decide_field(field).level == DecisionLevel.AUTO_ACCEPT
    )
