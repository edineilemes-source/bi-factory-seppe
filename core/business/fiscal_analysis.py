"""Fiscal analysis layer joining revenue and expenditure only at a common grain.

The layer receives already aggregated values. It deliberately does not join raw
revenue and expenditure facts, avoiding many-to-many multiplication.  Annual
and monthly grains are explicit and cannot be mixed silently.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, model_validator

from core.business.fiscal_contract import FiscalConcept, FiscalMetric, calculate_fiscal_metric


class FiscalPeriodGrain(str, Enum):
    ANNUAL = "ANNUAL"
    MONTHLY = "MONTHLY"


class FiscalPeriod(BaseModel):
    year: int
    month: int | None = None
    grain: FiscalPeriodGrain

    @model_validator(mode="after")
    def validate_period(self) -> "FiscalPeriod":
        if self.grain == FiscalPeriodGrain.ANNUAL and self.month is not None:
            raise ValueError("Período anual não pode conter mês.")
        if self.grain == FiscalPeriodGrain.MONTHLY and not (1 <= (self.month or 0) <= 12):
            raise ValueError("Período mensal exige mês entre 1 e 12.")
        return self


class FiscalPeriodValues(BaseModel):
    period: FiscalPeriod
    revenue_realized: float
    expenditure_committed: float
    expenditure_liquidated: float
    expenditure_paid: float


class FiscalPeriodAnalysis(BaseModel):
    period: FiscalPeriod
    revenue_realized: float
    expenditure_committed: float
    expenditure_liquidated: float
    expenditure_paid: float
    formal_budget_result: float
    revenue_liquidated_margin: float
    liquidated_revenue_commitment_pct: float | None
    committed_not_liquidated: float
    liquidated_not_paid: float


def analyze_fiscal_period(values: FiscalPeriodValues) -> FiscalPeriodAnalysis:
    source = {
        FiscalConcept.REVENUE_REALIZED: values.revenue_realized,
        FiscalConcept.EXPENDITURE_COMMITTED: values.expenditure_committed,
        FiscalConcept.EXPENDITURE_LIQUIDATED: values.expenditure_liquidated,
        FiscalConcept.EXPENDITURE_PAID: values.expenditure_paid,
    }
    return FiscalPeriodAnalysis(
        period=values.period,
        revenue_realized=values.revenue_realized,
        expenditure_committed=values.expenditure_committed,
        expenditure_liquidated=values.expenditure_liquidated,
        expenditure_paid=values.expenditure_paid,
        formal_budget_result=calculate_fiscal_metric(FiscalMetric.FORMAL_BUDGET_RESULT, source),
        revenue_liquidated_margin=calculate_fiscal_metric(FiscalMetric.REVENUE_LIQUIDATED_MARGIN, source),
        liquidated_revenue_commitment_pct=calculate_fiscal_metric(
            FiscalMetric.LIQUIDATED_REVENUE_COMMITMENT_PCT, source
        ),
        committed_not_liquidated=calculate_fiscal_metric(FiscalMetric.COMMITTED_NOT_LIQUIDATED, source),
        liquidated_not_paid=calculate_fiscal_metric(FiscalMetric.LIQUIDATED_NOT_PAID, source),
    )
