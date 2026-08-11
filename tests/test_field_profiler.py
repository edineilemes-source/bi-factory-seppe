"""Tests for individual field profiling."""

from core.profiling.field_profiler import profile_field


def test_profile_field_detects_measure_and_nulls() -> None:
    profile = profile_field("Valor Total", "valor_total", [10, 20.5, None, 40])

    assert profile.detected_type == "number"
    assert profile.recommended_type == "number"
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
