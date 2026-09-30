import pytest

from core.business.fiscal_contract import (
    FiscalAnalyticalContract,
    FiscalConcept,
    FiscalFieldMapping,
    FiscalMetric,
    calculate_fiscal_metric,
    validate_metric_ready,
)


def _confirmed_contract() -> FiscalAnalyticalContract:
    return FiscalAnalyticalContract(
        fiscal_year_field_id="ano",
        mappings=[
            FiscalFieldMapping(concept=FiscalConcept.REVENUE_REALIZED, field_id="receita_realizada", user_confirmed=True),
            FiscalFieldMapping(concept=FiscalConcept.EXPENDITURE_COMMITTED, field_id="empenhado", user_confirmed=True),
            FiscalFieldMapping(concept=FiscalConcept.EXPENDITURE_LIQUIDATED, field_id="liquidado", user_confirmed=True),
            FiscalFieldMapping(concept=FiscalConcept.EXPENDITURE_PAID, field_id="pago", user_confirmed=True),
        ],
    )


def test_metric_requires_human_confirmed_mapping():
    contract = FiscalAnalyticalContract(
        mappings=[
            FiscalFieldMapping(
                concept=FiscalConcept.REVENUE_REALIZED,
                field_id="receita_realizada",
                user_confirmed=False,
            )
        ]
    )
    with pytest.raises(ValueError, match="confirmação humana"):
        validate_metric_ready(contract, FiscalMetric.REVENUE_LIQUIDATED_MARGIN)


def test_annual_source_rejects_fake_monthly_grain():
    with pytest.raises(ValueError, match="granularidade mensal artificial"):
        FiscalAnalyticalContract(annual_only=True, monthly_period_field_id="mes")


def test_formal_budget_result_uses_committed_expenditure():
    contract = _confirmed_contract()
    validate_metric_ready(contract, FiscalMetric.FORMAL_BUDGET_RESULT)
    result = calculate_fiscal_metric(
        FiscalMetric.FORMAL_BUDGET_RESULT,
        {
            FiscalConcept.REVENUE_REALIZED: 6246785096.15,
            FiscalConcept.EXPENDITURE_COMMITTED: 6393130012.43,
        },
    )
    assert result == pytest.approx(-146344916.28)


def test_revenue_liquidated_margin_is_distinct_from_formal_result():
    contract = _confirmed_contract()
    validate_metric_ready(contract, FiscalMetric.REVENUE_LIQUIDATED_MARGIN)
    result = calculate_fiscal_metric(
        FiscalMetric.REVENUE_LIQUIDATED_MARGIN,
        {
            FiscalConcept.REVENUE_REALIZED: 6246785096.15,
            FiscalConcept.EXPENDITURE_LIQUIDATED: 6229584684.50,
        },
    )
    assert result == pytest.approx(17200411.65)


def test_liquidated_revenue_commitment_percentage():
    result = calculate_fiscal_metric(
        FiscalMetric.LIQUIDATED_REVENUE_COMMITMENT_PCT,
        {
            FiscalConcept.REVENUE_REALIZED: 6246785096.15,
            FiscalConcept.EXPENDITURE_LIQUIDATED: 6229584684.50,
        },
    )
    assert result == pytest.approx(99.724654, rel=1e-6)


def test_zero_revenue_percentage_is_none():
    result = calculate_fiscal_metric(
        FiscalMetric.LIQUIDATED_REVENUE_COMMITMENT_PCT,
        {
            FiscalConcept.REVENUE_REALIZED: 0.0,
            FiscalConcept.EXPENDITURE_LIQUIDATED: 10.0,
        },
    )
    assert result is None
