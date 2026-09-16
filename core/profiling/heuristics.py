"""Deterministic heuristics used by tabular profiling."""

import re
import unicodedata
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any


EMPTY_VALUES = (None, "")
DEFAULT_PLACEHOLDER_VALUES = frozenset({
    "", "-", "--", "n/a", "na", "null", "sem informação",
})


def is_empty(value: Any) -> bool:
    """Return whether a cell should be treated as empty."""
    return value is None or (isinstance(value, str) and not value.strip())


def is_placeholder(
    value: Any, placeholder_values: frozenset[str] = DEFAULT_PLACEHOLDER_VALUES
) -> bool:
    """Return whether a source value represents absence during profiling only."""
    if not isinstance(value, str):
        return False
    normalized_placeholders = {
        str(placeholder).strip().casefold() for placeholder in placeholder_values
    }
    return value.strip().casefold() in normalized_placeholders


def normalize_name(value: Any, fallback: str = "campo") -> str:
    """Convert a field label to a stable snake_case technical name."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    if not text:
        return fallback
    if text[0].isdigit():
        return f"campo_{text}"
    return text


def make_unique_names(names: Sequence[str]) -> list[str]:
    """Suffix repeated technical names while preserving their order."""
    occurrences: dict[str, int] = {}
    result: list[str] = []
    for name in names:
        occurrences[name] = occurrences.get(name, 0) + 1
        suffix = occurrences[name]
        result.append(name if suffix == 1 else f"{name}_{suffix}")
    return result


def detect_header_row(rows: Sequence[Sequence[Any]], search_limit: int = 25) -> int | None:
    """Find a likely zero-based header row using density and label quality."""
    best_index: int | None = None
    best_score = 0.0
    for index, row in enumerate(rows[:search_limit]):
        non_empty = [value for value in row if not is_empty(value)]
        if not non_empty:
            continue
        density = len(non_empty) / max(len(row), 1)
        text_ratio = sum(isinstance(value, str) for value in non_empty) / len(non_empty)
        labels = [str(value).strip().casefold() for value in non_empty]
        uniqueness = len(set(labels)) / len(labels)
        next_row_has_data = index + 1 < len(rows) and any(
            not is_empty(value) for value in rows[index + 1]
        )
        score = density * 0.45 + text_ratio * 0.35 + uniqueness * 0.15
        score += 0.05 if next_row_has_data else 0.0
        if len(non_empty) >= 2 and text_ratio >= 0.5 and score > best_score:
            best_index, best_score = index, score
    return best_index if best_score >= 0.62 else None


def value_kind(value: Any) -> str:
    """Map a non-empty Python value to a compact profiling kind."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (datetime, date)):
        return "date"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    text = str(value).strip()
    if re.fullmatch(r"[-+]?\d+", text):
        return "integer"
    if re.fullmatch(r"[-+]?(?:\d+[.,]\d+|\d{1,3}(?:[.]\d{3})+[,]\d+)", text):
        return "number"
    date_formats = (
        "%Y-%m-%d", "%Y/%m/%d",
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%d/%m/%y", "%d-%m-%y", "%d.%m.%y",
    )
    for date_format in date_formats:
        try:
            datetime.strptime(text, date_format)
        except ValueError:
            continue
        return "date"
    return "text"


def classify_sheet(name: str, row_count: int, column_count: int) -> str:
    """Suggest, as a hypothesis, the role of a sheet."""
    normalized = normalize_name(name)
    keyword_roles = (
        (("leia", "readme", "indice", "menu", "capa", "instrucao"), "Documentação ou navegação"),
        (("meta", "planejamento", "plano", "orcamento"), "Metas ou planejamento"),
        (("indicador", "kpi", "resumo", "painel"), "Indicadores"),
        (("validacao", "evidencia", "checagem", "check"), "Validação ou evidências"),
        (("cadastro", "dimensao", "referencia", "lookup", "de_para"), "Cadastro ou referência"),
    )
    for keywords, role in keyword_roles:
        if any(keyword in normalized for keyword in keywords):
            return role
    if row_count >= 20 and column_count >= 3:
        return "Base principal candidata"
    if 1 <= row_count <= 200 and 1 <= column_count <= 8:
        return "Cadastro ou referência"
    return "A validar"
