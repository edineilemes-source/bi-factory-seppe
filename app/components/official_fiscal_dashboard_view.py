"""Official fiscal dashboard backed by normalized SICONFI RREO data."""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = PROJECT_ROOT / "storage/reports/official_fiscal/rreo-2025-dashboard.csv"


def _brl(value: float) -> str:
    text = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {text}"


def _pct(value: float) -> str:
    return f"{value:.2f}%".replace(".", ",")


def _load_dataset(path: Path = DEFAULT_DATASET) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path)
    if frame.empty:
        raise ValueError("Dataset fiscal oficial está vazio.")
    return frame.sort_values(["ano", "bimestre"]).reset_index(drop=True)


def render_official_fiscal_dashboard() -> None:
    st.subheader("BI Fiscal Oficial — Campo Grande/MS")
    st.caption("Fonte: STN/SICONFI · RREO Anexo 01 · dados oficiais bimestrais")

    try:
        frame = _load_dataset()
    except (FileNotFoundError, ValueError) as error:
        st.warning(
            "O dataset oficial ainda não foi materializado neste ambiente. "
            "Execute `python scripts/siconfi_rreo_snapshot.py` e depois "
            "`python scripts/siconfi_rreo_dashboard_data.py`."
        )
        st.caption(str(error))
        return

    years = sorted(frame["ano"].dropna().astype(int).unique(), reverse=True)
    year = st.selectbox("Exercício", years, index=0, key="official_fiscal_year")
    year_frame = frame[frame["ano"] == year].copy()
    final = year_frame.iloc[-1]

    st.markdown(f"### Execução Orçamentária — {year}")
    cols = st.columns(4)
    cols[0].metric("Receita Realizada", _brl(final["receita_realizada_acumulada"]))
    cols[1].metric("Despesa Empenhada", _brl(final["despesa_empenhada_acumulada"]))
    cols[2].metric("Despesa Liquidada", _brl(final["despesa_liquidada_acumulada"]))
    cols[3].metric("Despesa Paga", _brl(final["despesa_paga_acumulada"]))

    result_cols = st.columns(4)
    result_cols[0].metric(
        "Resultado Orçamentário Formal",
        _brl(final["resultado_orcamentario_formal"]),
        help="Receita realizada menos despesa empenhada.",
    )
    result_cols[1].metric(
        "Receita − Liquidada",
        _brl(final["margem_receita_menos_liquidada"]),
        help="Indicador gerencial solicitado: receita realizada menos despesa liquidada.",
    )
    result_cols[2].metric(
        "Liquidada / Receita",
        _pct(final["liquidada_sobre_receita_pct"]),
    )
    result_cols[3].metric(
        "Liquidada não paga",
        _brl(final["liquidada_nao_paga"]),
    )

    st.markdown("### Evolução acumulada por bimestre")
    chart = year_frame.set_index("bimestre")[[
        "receita_realizada_acumulada",
        "despesa_empenhada_acumulada",
        "despesa_liquidada_acumulada",
        "despesa_paga_acumulada",
    ]].rename(columns={
        "receita_realizada_acumulada": "Receita realizada",
        "despesa_empenhada_acumulada": "Empenhada",
        "despesa_liquidada_acumulada": "Liquidada",
        "despesa_paga_acumulada": "Paga",
    })
    st.line_chart(chart, x_label="Bimestre", y_label="R$")

    left, right = st.columns(2)
    with left:
        st.markdown("### Receita realizada no bimestre")
        movement = year_frame.set_index("bimestre")[["receita_no_bimestre"]].rename(
            columns={"receita_no_bimestre": "Receita no bimestre"}
        )
        st.bar_chart(movement, x_label="Bimestre", y_label="R$")
    with right:
        st.markdown("### Despesa liquidada no bimestre")
        movement = year_frame.set_index("bimestre")[["despesa_liquidada_no_bimestre"]].rename(
            columns={"despesa_liquidada_no_bimestre": "Liquidada no bimestre"}
        )
        st.bar_chart(movement, x_label="Bimestre", y_label="R$")

    st.markdown("### Saldos de execução no fechamento")
    balance_cols = st.columns(3)
    balance_cols[0].metric("Empenhada não liquidada", _brl(final["empenhada_nao_liquidada"]))
    balance_cols[1].metric("Liquidada não paga", _brl(final["liquidada_nao_paga"]))
    balance_cols[2].metric("RPNP inscritos", _brl(final["rpnp_inscritos"]))

    with st.expander("Ver dados oficiais normalizados"):
        display = year_frame.copy()
        st.dataframe(display, use_container_width=True, hide_index=True)

    st.info(
        "Resultado Orçamentário Formal e Receita − Liquidada são conceitos diferentes. "
        "O primeiro usa a despesa empenhada; o segundo é o indicador gerencial baseado na despesa liquidada."
    )
