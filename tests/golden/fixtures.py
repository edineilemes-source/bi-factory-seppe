"""Deterministic, non-confidential data for the golden semantic pipeline."""

import pandas as pd

from core.ingestion.file_loader import LoadedSheet, LoadedWorkbook


def golden_expense_dataframe() -> pd.DataFrame:
    """Represent production-like shapes without reproducing business records."""
    return pd.DataFrame({
        "Ano Referência": ["2026", "2026", "-", "2026", None] * 2,
        "Data Lançamento": [
            "14/01/2026", "15/01/2026", "16/01/2026", "-", None,
        ] * 2,
        "Descrição Evento": [
            f"Descrição sintética detalhada do evento operacional número {index} para validação"
            for index in range(10)
        ],
        "Código Evento": [
            701001, 708001, 704001, 718001, 718003,
            701001, 708001, 704001, 718001, 718003,
        ],
        "Identificador Externo": [
            "00020351712020", "03409286000151", "00123456789012",
            "00020351712021", "03409286000152", "00123456789013",
            "00020351712022", "03409286000153", "00123456789014",
            "00020351712023",
        ],
        "Valor Total": [0, 3135.20, 978.48, -300.00, 12751.02] * 2,
        "Valor Movimento": [
            0, 0, 0, 12000, 3600, 5916, -60000000, 130000000, 0, 0,
        ],
        "Valor Estorno": [0, -6010.69, -12751.02, -382.32, -33.60] * 2,
        "Classificação Retenção I": ["-"] * 10,
        "Devolvido": [0] * 10,
        "Aux Sub Empenho": [
            2026360, 2026345, 2026351, 2026404, 2026269,
            2026412, 2026308, 2026397, 2026281, 2026376,
        ],
        "Campo Ambíguo": [
            "alfa", "beta", "gama", "delta", "epsilon",
            "zeta", "eta", "theta", "iota", "kappa",
        ],
    })


def golden_loaded_workbook() -> LoadedWorkbook:
    dataframe = golden_expense_dataframe()
    rows = [list(dataframe.columns), *dataframe.astype(object).values.tolist()]
    return LoadedWorkbook(
        original_name="golden_semantic.csv",
        source_type="browser_upload",
        size_bytes=1,
        file_type="csv",
        sheets=[LoadedSheet(
            name="Dados",
            rows=rows,
            approximate_row_count=len(rows),
            approximate_column_count=len(dataframe.columns),
        )],
    )
