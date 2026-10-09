"""Dashboard-project designer UI."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import streamlit.components.v1 as components

import streamlit as st

from core.dashboard_project import (
    AnalyticalSource, AudienceType, ComponentType, DashboardAudience,
    DashboardComponent, DashboardFilter, DashboardPage, DashboardProject,
    DimensionBinding, FieldRole, GridPosition, MetricBinding, OutputType,
)

FISCAL_METRICS = {
    "Receita realizada": "receita_realizada_acumulada",
    "Despesa empenhada": "despesa_empenhada_acumulada",
    "Despesa liquidada": "despesa_liquidada_acumulada",
    "Despesa paga": "despesa_paga_acumulada",
    "Resultado orçamentário formal": "resultado_orcamentario_formal",
    "Margem receita × liquidada": "margem_receita_menos_liquidada",
    "Liquidada não paga": "liquidada_nao_paga",
}
FISCAL_FILTERS = {"Exercício": "exercicio", "Bimestre": "bimestre", "Ente": "ente"}

def _metric(label: str) -> MetricBinding:
    return MetricBinding(field=FISCAL_METRICS[label], label=label, aggregation="MAX", number_format="BRL_COMPACT")

def _build_project(name, audience_name, audience_type, objective, filters, kpis, trend_metrics, outputs):
    global_filters = [
        DashboardFilter(field=FISCAL_FILTERS[label], label=label, selection="SINGLE")
        for label in filters
    ]
    components = []
    for index, label in enumerate(kpis):
        row, col = divmod(index, 4)
        components.append(DashboardComponent(
            title=label, component_type=ComponentType.KPI, source_id="fiscal",
            metrics=[_metric(label)],
            position=GridPosition(x=col * 3, y=row * 2, width=3, height=2),
        ))
    trend_y = ((len(kpis) + 3) // 4) * 2
    if trend_metrics:
        components.append(DashboardComponent(
            title="Evolução da execução orçamentária",
            component_type=ComponentType.LINE,
            source_id="fiscal",
            metrics=[_metric(label) for label in trend_metrics],
            dimensions=[DimensionBinding(field="bimestre", label="Bimestre", role=FieldRole.TEMPORAL_DIMENSION, granularity="BIMESTRAL")],
            position=GridPosition(x=0, y=trend_y, width=12, height=5),
        ))
    return DashboardProject(
        name=name,
        audience=DashboardAudience(name=audience_name, audience_type=audience_type, objective=objective),
        sources=[AnalyticalSource(source_id="fiscal", name="Execução Orçamentária", fact_table="bi_fiscal.vw_execucao_orcamentaria")],
        pages=[DashboardPage(title="Visão principal", global_filters=global_filters, components=components)],
        outputs=outputs,
        refresh_policy="Conforme atualização da fonte analítica",
    )

DATA_PATH = Path(__file__).resolve().parents[2] / "storage/reports/official_fiscal/rreo-2025-dashboard.csv"

def _load_fiscal_data(path: Path = DATA_PATH) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path)
    if frame.empty or not {"ano", "bimestre"}.issubset(frame.columns):
        raise ValueError("Dados fiscais vazios ou sem exercício/bimestre")
    return frame.sort_values(["ano", "bimestre"]).reset_index(drop=True)

def _format_brl(value: float) -> str:
    return ("R$ {:,.2f}".format(value)).replace(",", "#").replace(".", ",").replace("#", ".")

def _echarts_html(frame: pd.DataFrame, chart: DashboardComponent) -> str:
    """Generate a sandboxed ECharts visualization from trusted field bindings."""
    labels = [f"{int(v)}º bim." for v in frame["bimestre"]]
    series = [
        {"name": m.label, "type": "line", "smooth": True,
         "data": [float(v) for v in frame[m.field]]}
        for m in chart.metrics
    ]
    option = {
        "tooltip": {"trigger": "axis"},
        "legend": {"type": "scroll", "top": 0},
        "grid": {"left": 75, "right": 28, "top": 65, "bottom": 48},
        "xAxis": {"type": "category", "data": labels},
        "yAxis": {"type": "value", "axisLabel": {"formatter": "{value}"}},
        "series": series,
    }
    return (
        '<div id="chart" style="width:100%;height:340px"></div>'
        '<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>'
        '<script>const option=' + json.dumps(option, ensure_ascii=False) + ';'
        'const el=document.getElementById("chart");'
        'if(window.echarts){const chart=echarts.init(el);chart.setOption(option);'
        'new ResizeObserver(()=>chart.resize()).observe(el);}'
        'else{el.textContent="Não foi possível carregar ECharts. Verifique a conexão.";}</script>'
    )

def _render_preview(project: DashboardProject):
    page = project.pages[0]
    st.markdown("### Prévia com dados oficiais")
    st.caption("Fonte: SICONFI/RREO 2025 · granularidade bimestral. "
               "Não representa movimentação diária ou semanal.")
    try:
        frame = _load_fiscal_data()
    except (FileNotFoundError, ValueError) as exc:
        st.warning("Dataset fiscal não encontrado. Gere o relatório oficial antes de visualizar valores.")
        st.caption(str(exc))
        return
    years = sorted(frame["ano"].dropna().astype(int).unique(), reverse=True)
    year = st.selectbox("Exercício da prévia", years, key="designer_preview_year")
    year_frame = frame[frame["ano"] == year]
    periods = sorted(year_frame["bimestre"].astype(int).unique())
    period = st.selectbox("Fechamento do bimestre", periods, index=len(periods)-1, key="designer_preview_period")
    filtered = year_frame[year_frame["bimestre"] <= period]
    final = filtered.iloc[-1]
    st.caption(f"Valores acumulados até o {period}º bimestre de {year}.")
    kpis = [c for c in page.components if c.component_type == ComponentType.KPI]
    for start in range(0, len(kpis), 4):
        cols = st.columns(4)
        for col, component in zip(cols, kpis[start:start+4]):
            field = component.metrics[0].field
            if field in final.index:
                col.metric(component.title, _format_brl(float(final[field])))
            else:
                col.warning(f"Campo indisponível: {field}")
    for component in page.components:
        if component.component_type == ComponentType.LINE:
            with st.container(border=True):
                st.markdown(f"#### {component.title}")
                if all(m.field in filtered.columns for m in component.metrics):
                    components.html(_echarts_html(filtered, component), height=365)
                else:
                    st.warning("Métrica não encontrada no dataset.")
    st.caption("O filtro de bimestre determina o fechamento dos KPIs e o limite da série histórica. "
               "Valores acumulados não são somados entre bimestres.")

def render_dashboard_project_designer() -> None:
    st.subheader("Projetos de Dashboard")
    st.write("Monte produtos de informação diferentes sobre fatos e dimensões já validadas pela BI Factory.")

    left, right = st.columns([1, 1])
    with left:
        name = st.text_input("Nome do projeto", value="Sala Executiva — Execução Orçamentária")
        audience_name = st.text_input("Público", value="Prefeita")
        audience_label = st.selectbox("Tipo de público", ["Executivo", "Gerencial", "Técnico", "Público"])
    with right:
        objective = st.text_area("Objetivo", value="Acompanhar rapidamente a execução fiscal e sua tendência.")
        st.selectbox("Fonte analítica", ["Execução Orçamentária — bi_fiscal.vw_execucao_orcamentaria"], disabled=True)
        output_labels = st.multiselect("Saídas", ["Web", "PDF", "Excel", "Impressão"], default=["Web", "PDF"])

    st.markdown("### Filtros")
    filters = st.multiselect("Filtros globais", list(FISCAL_FILTERS), default=["Exercício", "Bimestre"])

    st.markdown("### Componentes")
    kpis = st.multiselect("KPIs", list(FISCAL_METRICS), default=["Receita realizada", "Despesa empenhada", "Despesa liquidada", "Despesa paga", "Resultado orçamentário formal", "Margem receita × liquidada"])
    trend = st.multiselect("Séries do gráfico de evolução", list(FISCAL_METRICS), default=["Receita realizada", "Despesa empenhada", "Despesa liquidada", "Despesa paga"])

    audience_map = {"Executivo": AudienceType.EXECUTIVE, "Gerencial": AudienceType.MANAGERIAL, "Técnico": AudienceType.TECHNICAL, "Público": AudienceType.PUBLIC}
    output_map = {"Web": OutputType.WEB, "PDF": OutputType.PDF, "Excel": OutputType.EXCEL, "Impressão": OutputType.PRINT}
    try:
        project = _build_project(name, audience_name, audience_map[audience_label], objective, filters, kpis, trend, [output_map[x] for x in output_labels])
    except ValueError as exc:
        st.error(f"Projeto inválido: {exc}")
        return

    _render_preview(project)
    st.markdown("### Publicação")
    st.caption("Publique a configuração para a Sala de Situação. A publicação não modifica a fonte fiscal.")
    if st.button("Publicar na Sala de Situação", type="primary"):
        target = Path(__file__).resolve().parents[2] / "storage/dashboard_projects/published.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        try:
            temporary.write_text(
                json.dumps(project.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temporary, target)
        except OSError as exc:
            st.error(f"Falha ao publicar: {exc}")
        else:
            st.success("Projeto publicado. Atualize a Sala de Situação na porta 8503.")
    st.markdown("### Especificação")
    st.download_button(
        "Baixar especificação JSON",
        data=json.dumps(project.model_dump(mode="json"), ensure_ascii=False, indent=2),
        file_name="dashboard-project.json",
        mime="application/json",
    )
    with st.expander("Ver contrato técnico"):
        st.json(project.model_dump(mode="json"))
