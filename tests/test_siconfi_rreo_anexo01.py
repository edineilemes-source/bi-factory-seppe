import pytest

from core.siconfi.rreo_anexo01 import normalize_rreo_anexo01


def row(account, column, value, *, period=6):
    return {
        "exercicio": 2025, "periodo": period,
        "instituicao": "Prefeitura Municipal de Campo Grande - MS",
        "cod_conta": account, "coluna": column, "valor": value,
    }


def official_p6_rows():
    return [
        row("TotalReceitas", "PREVISÃO INICIAL", 6871493844),
        row("TotalReceitas", "PREVISÃO ATUALIZADA (a)", 6871493844),
        row("TotalReceitas", "No Bimestre (b)", 1214588746.82),
        row("TotalReceitas", "Até o Bimestre (c)", 6246785096.15),
        row("TotalDespesas", "DOTAÇÃO INICIAL (d)", 6871493844),
        row("TotalDespesas", "DOTAÇÃO ATUALIZADA (e)", 7449710958.36),
        row("TotalDespesas", "DESPESAS EMPENHADAS NO BIMESTRE", 279111927.47),
        row("TotalDespesas", "DESPESAS EMPENHADAS ATÉ O BIMESTRE (f)", 6393130012.43),
        row("TotalDespesas", "DESPESAS LIQUIDADAS NO BIMESTRE", 1249265383.65),
        row("TotalDespesas", "DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)", 6229584684.50),
        row("TotalDespesas", "DESPESAS PAGAS ATÉ O BIMESTRE (j)", 5924478187.12),
        row("TotalDespesas", "INSCRITAS EM RESTOS A PAGAR NÃO PROCESSADOS (k)", 163545327.93),
        row("ReceitasExcetoIntraOrcamentarias", "Até o Bimestre (c)", 5838073948.78),
        row("DespesasExcetoIntraOrcamentarias", "DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)", 5817246414.36),
        # This balancing line must never be mistaken for realized revenue.
        row("TotalReceitasComDeficit", "Até o Bimestre (c)", 6393130012.43),
    ]


def test_p6_uses_real_revenue_total_not_deficit_balancing_line():
    result = normalize_rreo_anexo01(official_p6_rows())
    assert result.revenue_ytd == pytest.approx(6246785096.15)
    assert result.committed_ytd == pytest.approx(6393130012.43)
    assert result.liquidated_ytd == pytest.approx(6229584684.50)
    assert result.paid_ytd == pytest.approx(5924478187.12)
    assert result.rpnp_registered == pytest.approx(163545327.93)


def test_p6_analysis_matches_official_2025_fiscal_relationships():
    analysis = normalize_rreo_anexo01(official_p6_rows()).analysis()
    assert analysis.formal_budget_result == pytest.approx(-146344916.28)
    assert analysis.revenue_liquidated_margin == pytest.approx(17200411.65)
    assert analysis.committed_not_liquidated == pytest.approx(163545327.93)
    assert analysis.liquidated_not_paid == pytest.approx(305106497.38)
    assert analysis.liquidated_revenue_commitment_pct == pytest.approx(99.724654, rel=1e-6)


def test_preserves_except_intra_totals_for_reconciliation():
    result = normalize_rreo_anexo01(official_p6_rows())
    assert result.revenue_except_intra_ytd == pytest.approx(5838073948.78)
    assert result.expenditure_except_intra_liquidated_ytd == pytest.approx(5817246414.36)


def test_missing_required_official_pair_fails_closed():
    rows = [r for r in official_p6_rows() if not (
        r["cod_conta"] == "TotalReceitas" and r["coluna"] == "Até o Bimestre (c)"
    )]
    with pytest.raises(ValueError, match="sem valor obrigatório"):
        normalize_rreo_anexo01(rows)
