"""Municipal fiscal analytical contract for Revenue x Expenditure BI.

This module contains domain semantics only.  It does not perform ETL, database
writes or field-name guessing.  Source fields must be explicitly mapped and
validated before these concepts are used downstream.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class FiscalDomain(str, Enum):
    REVENUE = "REVENUE"
    EXPENDITURE = "EXPENDITURE"


class FiscalConcept(str, Enum):
    REVENUE_INITIAL_FORECAST = "REVENUE_INITIAL_FORECAST"
    REVENUE_UPDATED_FORECAST = "REVENUE_UPDATED_FORECAST"
    REVENUE_REALIZED = "REVENUE_REALIZED"
    REVENUE_DEDUCTION = "REVENUE_DEDUCTION"
    EXPENDITURE_INITIAL_APPROPRIATION = "EXPENDITURE_INITIAL_APPROPRIATION"
    EXPENDITURE_UPDATED_APPROPRIATION = "EXPENDITURE_UPDATED_APPROPRIATION"
    EXPENDITURE_COMMITTED = "EXPENDITURE_COMMITTED"
    EXPENDITURE_LIQUIDATED = "EXPENDITURE_LIQUIDATED"
    EXPENDITURE_PAID = "EXPENDITURE_PAID"


class FiscalMetric(str, Enum):
    FORMAL_BUDGET_RESULT = "FORMAL_BUDGET_RESULT"
    REVENUE_LIQUIDATED_MARGIN = "REVENUE_LIQUIDATED_MARGIN"
    LIQUIDATED_REVENUE_COMMITMENT_PCT = "LIQUIDATED_REVENUE_COMMITMENT_PCT"
    COMMITTED_NOT_LIQUIDATED = "COMMITTED_NOT_LIQUIDATED"
    LIQUIDATED_NOT_PAID = "LIQUIDATED_NOT_PAID"


class FiscalFieldMapping(BaseModel):
    concept: FiscalConcept
    field_id: str
    user_confirmed: bool = False


class FiscalAnalyticalContract(BaseModel):
    """Human-validated semantics required for municipal fiscal BI."""

    fiscal_contract_version: int = 1
    objective: str = "Analisar a execução orçamentária municipal e sua evolução histórica."
    mappings: list[FiscalFieldMapping] = Field(default_factory=list)
    annual_only: bool = False
    monthly_period_field_id: str | None = None
    fiscal_year_field_id: str | None = None

    @model_validator(mode="after")
    def validate_time_grain(self) -> "FiscalAnalyticalContract":
        if self.annual_only and self.monthly_period_field_id:
            raise ValueError(
                "Fonte anual não pode receber granularidade mensal artificial."
            )
        return self

    def mapping_for(self, concept: FiscalConcept) -> FiscalFieldMapping | None:
        return next((item for item in self.mappings if item.concept == concept), None)

    def confirmed_field(self, concept: FiscalConcept) -> str | None:
        mapping = self.mapping_for(concept)
        if mapping is None or not mapping.user_confirmed:
            return None
        return mapping.field_id

    def require_confirmed(self, *concepts: FiscalConcept) -> None:
        missing = [concept.value for concept in concepts if self.confirmed_field(concept) is None]
        if missing:
            raise ValueError(
                "Mapeamentos fiscais exigem confirmação humana: " + ", ".join(missing)
            )


FISCAL_METRIC_REQUIREMENTS: dict[FiscalMetric, tuple[FiscalConcept, ...]] = {
    FiscalMetric.FORMAL_BUDGET_RESULT: (
        FiscalConcept.REVENUE_REALIZED,
        FiscalConcept.EXPENDITURE_COMMITTED,
    ),
    FiscalMetric.REVENUE_LIQUIDATED_MARGIN: (
        FiscalConcept.REVENUE_REALIZED,
        FiscalConcept.EXPENDITURE_LIQUIDATED,
    ),
    FiscalMetric.LIQUIDATED_REVENUE_COMMITMENT_PCT: (
        FiscalConcept.REVENUE_REALIZED,
        FiscalConcept.EXPENDITURE_LIQUIDATED,
    ),
    FiscalMetric.COMMITTED_NOT_LIQUIDATED: (
        FiscalConcept.EXPENDITURE_COMMITTED,
        FiscalConcept.EXPENDITURE_LIQUIDATED,
    ),
    FiscalMetric.LIQUIDATED_NOT_PAID: (
        FiscalConcept.EXPENDITURE_LIQUIDATED,
        FiscalConcept.EXPENDITURE_PAID,
    ),
}


def validate_metric_ready(contract: FiscalAnalyticalContract, metric: FiscalMetric) -> None:
    """Refuse metric generation until every source concept is human-confirmed."""
    contract.require_confirmed(*FISCAL_METRIC_REQUIREMENTS[metric])


def calculate_fiscal_metric(metric: FiscalMetric, values: dict[FiscalConcept, float]) -> float | None:
    """Calculate deterministic metrics after semantic validation by the caller."""
    if metric == FiscalMetric.FORMAL_BUDGET_RESULT:
        return values[FiscalConcept.REVENUE_REALIZED] - values[FiscalConcept.EXPENDITURE_COMMITTED]
    if metric == FiscalMetric.REVENUE_LIQUIDATED_MARGIN:
        return values[FiscalConcept.REVENUE_REALIZED] - values[FiscalConcept.EXPENDITURE_LIQUIDATED]
    if metric == FiscalMetric.LIQUIDATED_REVENUE_COMMITMENT_PCT:
        revenue = values[FiscalConcept.REVENUE_REALIZED]
        if revenue == 0:
            return None
        return values[FiscalConcept.EXPENDITURE_LIQUIDATED] / revenue * 100.0
    if metric == FiscalMetric.COMMITTED_NOT_LIQUIDATED:
        return values[FiscalConcept.EXPENDITURE_COMMITTED] - values[FiscalConcept.EXPENDITURE_LIQUIDATED]
    if metric == FiscalMetric.LIQUIDATED_NOT_PAID:
        return values[FiscalConcept.EXPENDITURE_LIQUIDATED] - values[FiscalConcept.EXPENDITURE_PAID]
    raise ValueError(f"Métrica fiscal não suportada: {metric}")
