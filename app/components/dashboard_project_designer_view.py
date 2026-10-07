"""Dashboard-project designer UI."""
from __future__ import annotations

import json
from pathlib import Path

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

def _render_preview(project: DashboardProject):
    page = project.pages[0]
    st.markdown("### Prévia da composição")
    if page.global_filters:
        st.caption("Filtros: " + " · ".join(item.label for item in page.global_filters))
    kpis = [c for c in page.components if c.component_type == ComponentType.KPI]
    for start in range(0, len(kpis), 4):
        cols = st.columns(4)
        for col, component in zip(cols, kpis[start:start + 4]):
            col.metric(component.title, "—")
    for component in page.components:
        if component.component_type == ComponentType.LINE:
            with st.container(border=True):
                st.markdown(f"#### {component.title}")
                st.caption("Séries: " + " · ".join(m.label for m in component.metrics))
                st.info("Prévia estrutural — o renderer ECharts será conectado à consulta da fato na próxima etapa.")

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
    st.markdown("### Especificação")
    st.download_button(
        "Baixar especificação JSON",
        data=json.dumps(project.model_dump(mode="json"), ensure_ascii=False, indent=2),
        file_name="dashboard-project.json",
        mime="application/json",
    )
    with st.expander("Ver contrato técnico"):
        st.json(project.model_dump(mode="json"))
