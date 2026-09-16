"""Tests for deterministic profiling heuristics."""

from datetime import date

import pytest

from core.profiling.heuristics import detect_header_row, normalize_name, value_kind


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Nome do Órgão", "nome_do_orgao"),
        ("  Valor Total (R$) ", "valor_total_r"),
        ("2025 Meta", "campo_2025_meta"),
        ("", "campo"),
        ("Nº Documento", "no_documento"),
        ("Taxa % / Mês-Ano", "taxa_mes_ano"),
        ("  múltiplos   espaços  ", "multiplos_espacos"),
    ],
)
def test_normalize_name(source: str, expected: str) -> None:
    assert normalize_name(source) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (10, "integer"),
        (10.5, "number"),
        (True, "boolean"),
        (date(2026, 1, 15), "date"),
        ("31/12/2025", "date"),
        ("SEPPE", "text"),
    ],
)
def test_value_kind(value: object, expected: str) -> None:
    assert value_kind(value) == expected


def test_detect_header_row_after_title() -> None:
    rows = [
        ["Relatório de execução", None, None],
        [None, None, None],
        ["Código", "Descrição", "Valor"],
        [1, "Item A", 10.5],
        [2, "Item B", 20.0],
    ]

    assert detect_header_row(rows) == 2


def test_detect_header_row_returns_none_without_labels() -> None:
    assert detect_header_row([[None, None], [1, 2], [3, 4]]) is None
