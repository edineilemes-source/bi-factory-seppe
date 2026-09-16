"""Real-world semantic regressions required by Sprint 1.4.2."""

from core.profiling.field_profiler import profile_field
from core.profiling.models import SemanticRole
from core.semantic.decision_engine import DecisionLevel, decide_field, detect_conflicts


def _conflict_codes(field) -> set[str]:
    return {conflict.code for conflict in detect_conflicts(field)}


def test_year_with_placeholder_is_auto_accepted() -> None:
    field = profile_field("Ano Referência", "ano_referencia", ["2026", "-", "2026", None])
    assert field.placeholder_count == 1
    assert field.placeholder_percentage == 25.0
    assert field.null_count == 1
    assert field.detected_type == "integer"
    assert field.semantic_role_candidate == SemanticRole.TIME_COMPONENT
    assert decide_field(field).level == DecisionLevel.AUTO_ACCEPT


def test_brazilian_dates_ignore_placeholder_and_null() -> None:
    field = profile_field("Data Lançamento", "data_lancamento", [
        "14/01/2026", "15/01/2026", "-", None,
    ])
    assert field.detected_type == "date"
    assert field.semantic_role_candidate == SemanticRole.DATE
    assert field.semantic_role_confidence >= .85
    assert "date_name_non_date_content" not in _conflict_codes(field)
    assert decide_field(field).level == DecisionLevel.AUTO_ACCEPT


def test_named_measure_with_zero_decimals_and_negative_is_not_code() -> None:
    field = profile_field("Valor Total", "valor_total", [0, 3135.20, 978.48, -300, 12751.02])
    assert field.semantic_role_candidate == SemanticRole.MEASURE
    assert field.semantic_role_candidate != SemanticRole.CODE
    assert decide_field(field).level in {DecisionLevel.AUTO_ACCEPT, DecisionLevel.CONFIRM}


def test_neutral_quantitative_distribution_is_never_code_from_cardinality() -> None:
    field = profile_field("Campo", "campo", [0, 12000, 3600, 5916, -60000000, 130000000])
    assert field.semantic_role_candidate in {SemanticRole.MEASURE, SemanticRole.UNKNOWN}
    assert field.semantic_role_candidate != SemanticRole.CODE


def test_negative_decimal_values_are_measure_not_code() -> None:
    field = profile_field("Campo", "campo", [0, -6010.69, -12751.02, -382.32, -33.60])
    assert field.semantic_role_candidate == SemanticRole.MEASURE
    assert field.semantic_role_candidate != SemanticRole.CODE


def test_repeated_stable_integer_values_remain_plausible_code() -> None:
    field = profile_field("Campo", "campo", [
        701001, 708001, 704001, 718001, 718003,
        701001, 708001, 704001, 718001, 718003,
    ])
    assert field.semantic_role_candidate == SemanticRole.CODE


def test_placeholder_vocabulary_is_configurable_without_changing_source_examples() -> None:
    field = profile_field(
        "Ano", "ano", ["2026", "desconhecido"],
        placeholder_values=frozenset({"DESCONHECIDO"}),
    )
    assert field.placeholder_count == 1
    assert field.examples == ["2026"]
    assert field.semantic_role_candidate == SemanticRole.TIME_COMPONENT


def test_blank_string_is_counted_as_configured_placeholder() -> None:
    field = profile_field("Ano", "ano", ["2026", "", None])
    assert field.placeholder_count == 1
    assert field.null_count == 2
    assert field.semantic_role_candidate == SemanticRole.TIME_COMPONENT


def test_low_cardinality_is_informational_for_strong_measure() -> None:
    field = profile_field(
        "Total Pago", "total_pago",
        [0] * 100 + [12000, 3600, 5916, -60000000, 130000000],
    )
    conflicts = detect_conflicts(field)
    low_cardinality = next(
        conflict for conflict in conflicts
        if conflict.code == "numeric_low_cardinality"
    )
    assert field.semantic_role_candidate == SemanticRole.MEASURE
    assert low_cardinality.severity.value == "low"
    assert decide_field(field).level == DecisionLevel.AUTO_ACCEPT


def test_mixed_physical_types_do_not_alone_force_ask() -> None:
    field = profile_field("Ano", "ano", [2026, 2025]).model_copy(
        update={"detected_type": "mixed"}
    )
    # A technical warning, in isolation, is not a semantic contradiction.
    assert decide_field(field).level == DecisionLevel.AUTO_ACCEPT
