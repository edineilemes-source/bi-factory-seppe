import pytest

from core.business.fiscal_contract import (
    FiscalAnalyticalContract,
    FiscalConcept,
    FiscalFieldMapping,
)
from core.business.revenue_model import build_revenue_semantic_model


def test_revenue_model_uses_only_confirmed_mappings():
    contract = FiscalAnalyticalContract(
        fiscal_year_field_id="ano",
        mappings=[
            FiscalFieldMapping(
                concept=FiscalConcept.REVENUE_REALIZED,
                field_id="receita_realizada",
                user_confirmed=True,
            ),
            FiscalFieldMapping(
                concept=FiscalConcept.REVENUE_UPDATED_FORECAST,
                field_id="previsao_atualizada",
                user_confirmed=False,
            ),
        ],
    )

    model = build_revenue_semantic_model(contract)

    assert model.fact_name == "fato_receita_orcamentaria"
    assert model.fiscal_year_field_id == "ano"
    assert [measure.source_field for measure in model.measures] == ["receita_realizada"]


def test_revenue_realized_is_mandatory_and_human_confirmed():
    contract = FiscalAnalyticalContract(
        mappings=[
            FiscalFieldMapping(
                concept=FiscalConcept.REVENUE_REALIZED,
                field_id="receita_realizada",
                user_confirmed=False,
            )
        ]
    )

    with pytest.raises(ValueError, match="Receita Realizada"):
        build_revenue_semantic_model(contract)


def test_revenue_model_preserves_annual_source_without_fake_month():
    contract = FiscalAnalyticalContract(
        annual_only=True,
        fiscal_year_field_id="ano",
        mappings=[
            FiscalFieldMapping(
                concept=FiscalConcept.REVENUE_REALIZED,
                field_id="receita_realizada",
                user_confirmed=True,
            )
        ],
    )

    model = build_revenue_semantic_model(contract)

    assert model.annual_only is True
    assert model.monthly_period_field_id is None


def test_additivity_requires_explicit_confirmation():
    contract = FiscalAnalyticalContract(
        mappings=[
            FiscalFieldMapping(
                concept=FiscalConcept.REVENUE_REALIZED,
                field_id="receita_realizada",
                user_confirmed=True,
            ),
            FiscalFieldMapping(
                concept=FiscalConcept.REVENUE_DEDUCTION,
                field_id="deducao_receita",
                user_confirmed=True,
            ),
        ]
    )

    model = build_revenue_semantic_model(
        contract,
        additive_concepts={FiscalConcept.REVENUE_REALIZED},
    )

    measures = {item.concept: item for item in model.measures}
    assert measures[FiscalConcept.REVENUE_REALIZED].additive_confirmed is True
    assert measures[FiscalConcept.REVENUE_DEDUCTION].additive_confirmed is False
