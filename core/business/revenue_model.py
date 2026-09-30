"""Revenue-side semantic model for municipal budget BI.

This layer deliberately stays independent from the legacy expense MVP model.
It translates only human-confirmed fiscal concepts into a revenue model; it
never guesses source-field meaning and never invents monthly grain.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.business.fiscal_contract import (
    FiscalAnalyticalContract,
    FiscalConcept,
)


class RevenueMeasure(BaseModel):
    concept: FiscalConcept
    source_field: str
    business_name: str
    additive_confirmed: bool = False


class RevenueSemanticModel(BaseModel):
    fact_name: str = "fato_receita_orcamentaria"
    fiscal_year_field_id: str | None = None
    monthly_period_field_id: str | None = None
    annual_only: bool = False
    measures: list[RevenueMeasure] = Field(default_factory=list)


REVENUE_MEASURE_NAMES: dict[FiscalConcept, str] = {
    FiscalConcept.REVENUE_INITIAL_FORECAST: "Previsão Inicial",
    FiscalConcept.REVENUE_UPDATED_FORECAST: "Previsão Atualizada",
    FiscalConcept.REVENUE_REALIZED: "Receita Realizada",
    FiscalConcept.REVENUE_DEDUCTION: "Dedução da Receita",
}


def build_revenue_semantic_model(
    contract: FiscalAnalyticalContract,
    *,
    additive_concepts: set[FiscalConcept] | None = None,
) -> RevenueSemanticModel:
    """Build the revenue model exclusively from human-confirmed mappings."""
    additive_concepts = additive_concepts or set()
    measures: list[RevenueMeasure] = []

    for concept, business_name in REVENUE_MEASURE_NAMES.items():
        source_field = contract.confirmed_field(concept)
        if source_field is None:
            continue
        measures.append(
            RevenueMeasure(
                concept=concept,
                source_field=source_field,
                business_name=business_name,
                additive_confirmed=concept in additive_concepts,
            )
        )

    if not any(item.concept == FiscalConcept.REVENUE_REALIZED for item in measures):
        raise ValueError("Receita Realizada exige mapeamento fiscal confirmado pelo usuário.")

    return RevenueSemanticModel(
        fiscal_year_field_id=contract.fiscal_year_field_id,
        monthly_period_field_id=contract.monthly_period_field_id,
        annual_only=contract.annual_only,
        measures=measures,
    )
