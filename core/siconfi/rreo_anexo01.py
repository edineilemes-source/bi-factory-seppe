"""Semantic normalization for official Siconfi RREO Annex 01.

The source is already an official STN analytical publication.  This module maps
only explicit STN account/column pairs; it does not infer spreadsheet meaning.
The canonical comparison uses total revenue and total expenditure, including
intra-budget transactions, while preserving except-intra values separately.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from core.business.fiscal_analysis import (
    FiscalPeriod,
    FiscalPeriodAnalysis,
    FiscalPeriodGrain,
    FiscalPeriodValues,
    analyze_fiscal_period,
)

REVENUE_TOTAL = "TotalReceitas"
REVENUE_EXCEPT_INTRA = "ReceitasExcetoIntraOrcamentarias"
EXPENDITURE_TOTAL = "TotalDespesas"
EXPENDITURE_EXCEPT_INTRA = "DespesasExcetoIntraOrcamentarias"

COL_REVENUE_INITIAL = "PREVISÃO INICIAL"
COL_REVENUE_UPDATED = "PREVISÃO ATUALIZADA (a)"
COL_REVENUE_BIMESTER = "No Bimestre (b)"
COL_REVENUE_YTD = "Até o Bimestre (c)"
COL_EXP_INITIAL = "DOTAÇÃO INICIAL (d)"
COL_EXP_UPDATED = "DOTAÇÃO ATUALIZADA (e)"
COL_COMMITTED_BIMESTER = "DESPESAS EMPENHADAS NO BIMESTRE"
COL_COMMITTED_YTD = "DESPESAS EMPENHADAS ATÉ O BIMESTRE (f)"
COL_LIQUIDATED_BIMESTER = "DESPESAS LIQUIDADAS NO BIMESTRE"
COL_LIQUIDATED_YTD = "DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)"
COL_PAID_YTD = "DESPESAS PAGAS ATÉ O BIMESTRE (j)"
COL_RPNP = "INSCRITAS EM RESTOS A PAGAR NÃO PROCESSADOS (k)"


class RreoBimester(BaseModel):
    year: int
    period: int
    institution: str | None = None
    revenue_initial: float
    revenue_updated: float
    revenue_bimester: float
    revenue_ytd: float
    expenditure_initial: float
    expenditure_updated: float
    committed_bimester: float
    committed_ytd: float
    liquidated_bimester: float
    liquidated_ytd: float
    paid_ytd: float
    rpnp_registered: float | None = None
    revenue_except_intra_ytd: float | None = None
    expenditure_except_intra_liquidated_ytd: float | None = None

    @property
    def month_end(self) -> int:
        return self.period * 2

    def analysis(self) -> FiscalPeriodAnalysis:
        # RREO is bimonthly. FiscalPeriod currently has annual/monthly grains, so
        # month_end is used as the explicit observation point, never as monthly data.
        return analyze_fiscal_period(FiscalPeriodValues(
            period=FiscalPeriod(year=self.year, month=self.month_end, grain=FiscalPeriodGrain.MONTHLY),
            revenue_realized=self.revenue_ytd,
            expenditure_committed=self.committed_ytd,
            expenditure_liquidated=self.liquidated_ytd,
            expenditure_paid=self.paid_ytd,
        ))


def _index(items: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items:
        key = (str(item.get("cod_conta") or ""), str(item.get("coluna") or ""))
        if key in result:
            raise ValueError(f"RREO ambíguo: par conta/coluna duplicado: {key}")
        result[key] = item
    return result


def _value(index: dict[tuple[str, str], dict[str, Any]], account: str, column: str,
           *, required: bool = True) -> float | None:
    row = index.get((account, column))
    if row is None or row.get("valor") is None:
        if required:
            raise ValueError(f"RREO sem valor obrigatório: {account} / {column}")
        return None
    return float(row["valor"])


def normalize_rreo_anexo01(items: list[dict[str, Any]]) -> RreoBimester:
    if not items:
        raise ValueError("RREO Anexo 01 vazio.")
    periods = {int(item["periodo"]) for item in items if item.get("periodo") is not None}
    years = {int(item["exercicio"]) for item in items if item.get("exercicio") is not None}
    if len(periods) != 1 or len(years) != 1:
        raise ValueError("Um snapshot RREO deve conter exatamente um exercício e um período.")
    period = next(iter(periods))
    if not 1 <= period <= 6:
        raise ValueError("RREO bimestral exige período entre 1 e 6.")
    index = _index(items)
    first = items[0]
    return RreoBimester(
        year=next(iter(years)), period=period, institution=first.get("instituicao"),
        revenue_initial=_value(index, REVENUE_TOTAL, COL_REVENUE_INITIAL),
        revenue_updated=_value(index, REVENUE_TOTAL, COL_REVENUE_UPDATED),
        revenue_bimester=_value(index, REVENUE_TOTAL, COL_REVENUE_BIMESTER),
        revenue_ytd=_value(index, REVENUE_TOTAL, COL_REVENUE_YTD),
        expenditure_initial=_value(index, EXPENDITURE_TOTAL, COL_EXP_INITIAL),
        expenditure_updated=_value(index, EXPENDITURE_TOTAL, COL_EXP_UPDATED),
        committed_bimester=_value(index, EXPENDITURE_TOTAL, COL_COMMITTED_BIMESTER),
        committed_ytd=_value(index, EXPENDITURE_TOTAL, COL_COMMITTED_YTD),
        liquidated_bimester=_value(index, EXPENDITURE_TOTAL, COL_LIQUIDATED_BIMESTER),
        liquidated_ytd=_value(index, EXPENDITURE_TOTAL, COL_LIQUIDATED_YTD),
        paid_ytd=_value(index, EXPENDITURE_TOTAL, COL_PAID_YTD),
        rpnp_registered=_value(index, EXPENDITURE_TOTAL, COL_RPNP, required=False),
        revenue_except_intra_ytd=_value(index, REVENUE_EXCEPT_INTRA, COL_REVENUE_YTD, required=False),
        expenditure_except_intra_liquidated_ytd=_value(
            index, EXPENDITURE_EXCEPT_INTRA, COL_LIQUIDATED_YTD, required=False
        ),
    )


def load_rreo_snapshot(path: str | Path) -> RreoBimester:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    items = payload.get("items", []) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("Snapshot RREO inválido: items deve ser lista.")
    return normalize_rreo_anexo01(items)


def load_rreo_year(directory: str | Path) -> list[RreoBimester]:
    root = Path(directory)
    files = sorted(p for p in root.glob("rreo-*-p*-anexo01.json") if "manifest" not in p.name)
    series = [load_rreo_snapshot(path) for path in files]
    series.sort(key=lambda item: item.period)
    periods = [item.period for item in series]
    if periods != list(range(1, 7)):
        raise ValueError(f"Série anual RREO incompleta: períodos encontrados {periods}")
    return series
