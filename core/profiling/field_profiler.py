"""Column-level profiling functions."""

from collections import Counter
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from core.profiling.heuristics import is_empty, value_kind
from core.profiling.models import FieldProfile, StructuralWarning


def _serializable_example(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value if isinstance(value, (str, int, float, bool)) else str(value)


def profile_field(
    original_name: str,
    technical_name: str,
    values: Sequence[Any],
    *,
    sheet_name: str | None = None,
) -> FieldProfile:
    """Create a deterministic profile from sampled column values."""
    total = len(values)
    non_null = [value for value in values if not is_empty(value)]
    null_count = total - len(non_null)
    kinds = Counter(value_kind(value) for value in non_null)

    if not kinds:
        detected_type = recommended_type = "empty"
    elif len(kinds) == 1:
        detected_type = next(iter(kinds))
        recommended_type = detected_type
    elif set(kinds) <= {"integer", "number"}:
        detected_type = "number"
        recommended_type = "number"
    else:
        detected_type = "mixed"
        recommended_type = "text"

    distinct_values: dict[str, Any] = {}
    for value in non_null:
        distinct_values.setdefault(repr(value), value)
    distinct_count = len(distinct_values)
    examples = [_serializable_example(value) for value in list(distinct_values.values())[:5]]
    null_percentage = round((null_count / total * 100) if total else 0.0, 2)
    unique_ratio = distinct_count / len(non_null) if non_null else 0.0
    technical_lower = technical_name.casefold()
    possible_date = detected_type == "date" or any(
        token in technical_lower for token in ("data", "date", "dt_")
    )
    possible_measure = detected_type in {"integer", "number"} and not any(
        token in technical_lower for token in ("id", "codigo", "cod", "cep")
    )
    possible_category = (
        detected_type in {"text", "boolean"}
        and bool(non_null)
        and distinct_count <= min(50, max(2, int(len(non_null) * 0.5)))
    )
    candidate_key = bool(non_null) and null_count == 0 and unique_ratio == 1.0

    warnings: list[StructuralWarning] = []
    if null_percentage >= 50:
        warnings.append(
            StructuralWarning(
                code="high_null_rate",
                message=f"Campo com {null_percentage:.2f}% de valores nulos na amostra.",
                sheet_name=sheet_name,
                field_name=original_name,
            )
        )
    if detected_type == "mixed":
        warnings.append(
            StructuralWarning(
                code="mixed_types",
                message="Possível mistura de tipos detectada na amostra.",
                sheet_name=sheet_name,
                field_name=original_name,
            )
        )

    return FieldProfile(
        original_name=original_name,
        technical_name=technical_name,
        detected_type=detected_type,
        recommended_type=recommended_type,
        null_count=null_count,
        null_percentage=null_percentage,
        distinct_count=distinct_count,
        examples=examples,
        is_candidate_key=candidate_key,
        is_possible_date=possible_date,
        is_possible_measure=possible_measure,
        is_possible_category=possible_category,
        warnings=warnings,
    )
