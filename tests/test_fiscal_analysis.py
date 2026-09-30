import pytest

from core.business.fiscal_analysis import (
    FiscalPeriod,
    FiscalPeriodGrain,
    FiscalPeriodValues,
    analyze_fiscal_period,
)


def test_2025_fiscal_analysis_keeps_formal_and_liquidated_results_distinct():
    analysis = analyze_fiscal_period(
        FiscalPeriodValues(
            period=FiscalPeriod(year=2025, grain=FiscalPeriodGrain.ANNUAL),
            revenue_realized=6246785096.15,
            expenditure_committed=6393130012.43,
            expenditure_liquidated=6229584684.50,
            expenditure_paid=5924000000.00,
        )
    )

    assert analysis.formal_budget_result == pytest.approx(-146344916.28)
    assert analysis.revenue_liquidated_margin == pytest.approx(17200411.65)
    assert analysis.liquidated_revenue_commitment_pct == pytest.approx(99.724654, rel=1e-6)
    assert analysis.committed_not_liquidated == pytest.approx(163545327.93)
    assert analysis.liquidated_not_paid == pytest.approx(305584684.50)


def test_annual_period_rejects_month():
    with pytest.raises(ValueError, match="anual não pode conter mês"):
        FiscalPeriod(year=2025, month=12, grain=FiscalPeriodGrain.ANNUAL)


def test_monthly_period_requires_valid_month():
    with pytest.raises(ValueError, match="mês entre 1 e 12"):
        FiscalPeriod(year=2025, grain=FiscalPeriodGrain.MONTHLY)

    with pytest.raises(ValueError, match="mês entre 1 e 12"):
        FiscalPeriod(year=2025, month=13, grain=FiscalPeriodGrain.MONTHLY)


def test_monthly_period_is_explicit():
    period = FiscalPeriod(year=2025, month=7, grain=FiscalPeriodGrain.MONTHLY)
    assert period.month == 7
    assert period.grain == FiscalPeriodGrain.MONTHLY
