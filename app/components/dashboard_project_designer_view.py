"""Dashboard-project designer UI."""
from __future__ import annotations

import json
import os
from uuid import uuid4
from pathlib import Path

import pandas as pd
import streamlit.components.v1 as components
from streamlit.components.v1 import declare_component
from app.components.information_product_registry import TYPES, create_product, load_registry, update_product

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
        {"name": m.label, "type": "bar" if chart.component_type == ComponentType.BAR else "line", "smooth": True,
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
        "color": chart.series_colors or ["#168BAF", "#35A78B", "#E3A243", "#727AD1"],
        "textStyle": {"fontFamily": chart.font_family, "color": chart.text_color},
    }
    return (
        '<div id="chart" style="width:100%;height:340px;background:' + chart.background_color + ';"></div>'
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
        if component.component_type in (ComponentType.LINE, ComponentType.BAR, ComponentType.TABLE):
            with st.container(border=True):
                st.markdown(f"#### {component.title}")
                if all(m.field in filtered.columns for m in component.metrics):
                    if component.component_type == ComponentType.TABLE:
                        st.dataframe(filtered[["bimestre"] + [m.field for m in component.metrics]].rename(columns={"bimestre":"Bimestre", **{m.field:m.label for m in component.metrics}}), hide_index=True, use_container_width=True)
                    else:
                        components.html(_echarts_html(filtered, component), height=365)
                else:
                    st.warning("Métrica não encontrada no dataset.")
    st.caption("O filtro de bimestre determina o fechamento dos KPIs e o limite da série histórica. "
               "Valores acumulados não são somados entre bimestres.")

def _component_exists(items, kind, metric, exclude_id=None):
    """Prevent identical type/metric visualizations in the same project."""
    return any(item["type"] == kind and item["metric"] == metric
               and item.get("id") != exclude_id for item in items)


@st.dialog("Adicionar componente")
def _add_component_dialog(kind: str):
    labels = {"KPI": "Indicador KPI", "LINE": "Gráfico de linha",
              "BAR": "Gráfico de barras", "TABLE": "Tabela"}
    items = st.session_state["dashboard_items"]
    st.caption(f"Objeto: {labels[kind]} · fonte fiscal oficial, bimestral")
    available = list(FISCAL_METRICS) if kind != "KPI" else [m for m in FISCAL_METRICS if not _component_exists(items, kind, m)]
    if not available:
        st.warning("Todas as métricas disponíveis já têm um KPI.")
        if st.button("Fechar"):
            st.rerun()
        return
    selected = (st.selectbox("Indicador", available, key="new_component_metric") if kind == "KPI" else st.multiselect("Métricas no mesmo objeto", available, default=available[:1], key="new_component_metrics"))
    metric = selected if kind == "KPI" else (selected[0] if selected else "")
    title = st.text_input("Título do componente",
                          value=metric if kind == "KPI" else f"{labels[kind]} — {metric}",
                          key="new_component_title")
    width = st.selectbox("Largura", [3, 4, 6, 8, 12],
                         index=0 if kind == "KPI" else 4, key="new_component_width")
    if kind != "KPI":
        st.info("Dimensão disponível: Bimestre. Os dados são acumulados por bimestre.")
    if st.button("Adicionar ao painel", type="primary", use_container_width=True):
        if not metric:
            st.error("Selecione pelo menos uma métrica.")
        elif not title.strip():
            st.error("Informe um título.")
        elif kind == "KPI" and _component_exists(items, kind, metric):
            st.warning("Este tipo de componente com esta métrica já existe.")
        else:
            items.append({"id": str(uuid4()), "type": kind, "metric": metric,
                          "metrics": [metric] if kind == "KPI" else selected,
                          "title": title.strip(), "width": width})
            st.rerun()


@st.dialog("Biblioteca de visualizações · Apache ECharts")
def _chart_catalog_dialog():
    categories = {
        "Indicadores": [("KPI", "Cartão KPI")],
        "Comparações": [("BAR", "Barras / Colunas")],
        "Evolução": [("LINE", "Linhas")],
        "Detalhamento": [("TABLE", "Tabela")],
    }
    category = st.radio("Categoria", list(categories), horizontal=True, key="catalog_category")
    options = categories[category]
    labels = [label for _, label in options]
    selected = st.radio("Modelo", labels, key="catalog_model")
    st.caption("A visualização utilizará o Apache ECharts e a fonte fiscal validada. Outros modelos serão liberados após validação dos dados e do contrato de publicação.")
    if st.button("Configurar este objeto", type="primary", use_container_width=True):
        kind = next(kind for kind, label in options if label == selected)
        st.session_state["dashboard_show_catalog"] = False
        st.session_state["dashboard_dialog_kind"] = kind
        st.rerun()


_studio_component = declare_component(
    "bi_factory_visual_studio",
    path=str(Path(__file__).resolve().parent / "studio_frontend"),
)


def _render_visual_studio() -> None:
    """Visual designer at 8502; server-side publication only."""
    try:
        frame = _load_fiscal_data()
    except (FileNotFoundError, ValueError) as exc:
        st.error(f"Fonte fiscal indisponível: {exc}")
        return
    st.markdown("#### Produto de informação")
    with st.expander("Criar novo produto (ficha de identificação)"):
        with st.form("studio_create_product"):
            new_name = st.text_input("Nome do produto")
            new_type = st.selectbox("Tipo de produto", TYPES)
            new_description = st.text_area("Descrição")
            new_refresh = st.selectbox("Atualização", ["Manual", "Conforme fonte", "Diária", "Semanal", "Mensal"])
            new_destination = st.text_input("Destino / distribuição")
            create = st.form_submit_button("Criar produto", type="primary")
        if create:
            try:
                new_product = create_product(new_name, new_type, new_description, new_refresh, new_destination)
                st.session_state["studio_product_id"] = new_product["id"]
                st.success("Produto cadastrado: " + new_product["code"])
            except (ValueError, OSError) as exc:
                st.error(str(exc))
    try:
        products = load_registry()
    except (OSError, ValueError) as exc:
        st.error(f"Catálogo indisponível: {exc}")
        return
    options = {"Sala publicada (legado)": ""}
    options.update({p["code"] + " · " + p["name"]: p["id"] for p in products})
    chosen = st.session_state.get("studio_product_id", "")
    labels = list(options)
    default_index = next((i for i, label in enumerate(labels) if options[label] == chosen), 0)
    label = st.selectbox("Produto em edição", labels, index=default_index)
    product_id = options[label]
    st.session_state["studio_product_id"] = product_id
    if product_id:
        current_product = next(p for p in products if p["id"] == product_id)
        st.caption(f"Chave: {current_product['code']} · Tipo: {current_product['type']} · Versão: {current_product['version']}")
        if current_product["type"] not in ("Painel", "Portal"):
            st.info("Este produto possui ficha cadastrada. A publicação web na 8503 é reservada aos painéis.")
    safe_rows = frame.astype(object).where(pd.notna(frame), None).to_dict(orient="records")
    published_items = []
    load_published = st.session_state.pop("studio_open_published", False)
    if load_published:
        target = Path(__file__).resolve().parents[2] / "storage/dashboard_projects/published.json"
        try:
            project = json.loads(target.read_text(encoding="utf-8"))
            published_items = [item for page in project.get("pages", [])
                               for item in page.get("components", [])
                               if not product_id or item.get("product_id") == product_id]
        except (OSError, ValueError, TypeError) as exc:
            st.error(f"Não foi possível abrir o produto publicado: {exc}")
    event = _studio_component(rows=safe_rows, published_components=published_items,
                              load_published=load_published, product_id=product_id,
                              result=st.session_state.get("studio_publish_result"),
                              key="bi_factory_visual_studio", height=920)
    if not isinstance(event, dict) or event.get("action") not in ("publish", "unpublish"):
        return
    event_id = event.get("event_id")
    if not event_id or event_id == st.session_state.get("studio_last_event_id"):
        return
    st.session_state["studio_last_event_id"] = event_id
    if product_id and next((p for p in products if p["id"] == product_id), {}).get("type") not in ("Painel", "Portal"):
        st.error("Somente painéis e portais podem ser enviados à 8503.")
        return
    item = event.get("component")
    if not isinstance(item, dict):
        st.error("Componente inválido para publicação.")
        return
    if event["action"] == "unpublish":
        identifier = str(item.get("id", ""))
        if not identifier or len(identifier) > 128:
            st.error("Identificador inválido.")
            return
        target = Path(__file__).resolve().parents[2] / "storage/dashboard_projects/published.json"
        if not target.exists():
            st.info("Nenhum projeto publicado.")
            return
        try:
            project = json.loads(target.read_text(encoding="utf-8"))
            for page in project.get("pages", []):
                page["components"] = [c for c in page.get("components", []) if c.get("id") != identifier]
            temporary = target.with_suffix(".tmp")
            temporary.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporary, target)
        except (OSError, ValueError, TypeError) as exc:
            st.error(f"Falha ao retirar componente: {exc}")
        else:
            if product_id:
                from app.components.information_product_registry import sync_product_components
                try:
                    ids = [c["id"] for page in project.get("pages", []) for c in page.get("components", []) if c.get("product_id") == product_id]
                    sync_product_components(product_id, ids)
                except (OSError, ValueError, KeyError) as exc:
                    st.warning(f"Retirada concluída, mas catálogo não atualizado: {exc}")
            st.session_state["studio_publish_result"] = {"id": identifier, "published": False, "message": "Componente retirado da Sala de Situação."}
            st.success("Componente retirado da Sala de Situação.")
            st.rerun()
        return
    metric_names = item.get("metrics", [])
    if not isinstance(metric_names, list) or not metric_names or any(m not in FISCAL_METRICS for m in metric_names):
        st.error("Métricas não reconhecidas. Publicação cancelada.")
        return
    kind = item.get("type")
    supported = {"KPI": "KPI", "LINE": "LINE", "BAR": "BAR", "TABLE": "TABLE",
                 "STACK": "BAR", "HORIZONTAL": "BAR", "AREA": "LINE",
                 "PIE": "BAR", "DONUT": "BAR"}
    if kind not in supported:
        st.error("Tipo de gráfico não reconhecido.")
        return
    identifier = str(item.get("id", ""))
    if not identifier or len(identifier) > 128:
        st.error("Identificador de componente inválido.")
        return
    colors = [v for v in item.get("colors", []) if isinstance(v, str) and len(v) == 7 and v.startswith("#")]
    component = {
        "id": identifier,
        "product_id": product_id or None,
        "title": str(item.get("title", "Visualização"))[:180],
        "component_type": supported[kind],
        "visual_subtype": kind,
        "metrics": [{"field": FISCAL_METRICS[m], "label": m, "aggregation": "MAX", "number_format": "BRL_COMPACT"} for m in metric_names[:7]],
        "dimensions": [{"field": "bimestre", "label": "Bimestre", "role": "TEMPORAL_DIMENSION", "granularity": "BIMESTRAL"}] if kind != "KPI" else [],
        "position": {"x": 0, "y": 0, "width": max(3, min(12, int(item.get("width", 6)))), "height": 5},
        "background_color": item.get("bg", "#FFFFFF"),
        "text_color": item.get("text", "#19283B"),
        "series_colors": colors,
        "font_family": "Inter",
    }
    target = Path(__file__).resolve().parents[2] / "storage/dashboard_projects/published.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        if target.exists():
            project = json.loads(target.read_text(encoding="utf-8"))
        else:
            project = {"name": "Sala de Situação — SEPPE", "audience": {"name": "Painel executivo"}, "pages": [{"title": "Visão principal", "components": []}]}
        if project.get("product_id") not in (None, product_id):
            raise ValueError("A 8503 já está vinculada a outro produto. Troca de sala exige publicação controlada.")
        pages = project.setdefault("pages", [{"title": "Visão principal", "components": []}])
        if not pages:
            pages.append({"title": "Visão principal", "components": []})
        existing = pages[0].setdefault("components", [])
        idx = next((i for i, c in enumerate(existing) if c.get("id") == identifier), None)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        component["created_at"] = existing[idx].get("created_at", now) if idx is not None else now
        component["updated_at"] = now
        if idx is None:
            existing.append(component)
        else:
            existing[idx] = component
        project.setdefault("created_at", now)
        project["updated_at"] = now
        if product_id:
            project["product_id"] = product_id
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, target)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        st.error(f"Falha na publicação: {exc}")
    else:
        if product_id:
            from app.components.information_product_registry import sync_product_components
            try:
                ids = [c["id"] for page in project.get("pages", []) for c in page.get("components", []) if c.get("product_id") == product_id]
                sync_product_components(product_id, ids, "Publicado")
            except (OSError, ValueError, KeyError) as exc:
                st.warning(f"Publicação concluída, mas catálogo não atualizado: {exc}")
        st.session_state["studio_publish_result"] = {"id": identifier, "published": True, "message": "Publicado na Sala de Situação. Atualize a 8503."}
        st.success(f"Componente '{component['title']}' publicado na Sala de Situação (8503).")
        st.rerun()



def render_dashboard_project_designer() -> None:
    st.subheader("Projetos de Dashboard")
    mode = st.radio("Ambiente de edição", ["Estúdio Visual (novo)", "Editor clássico"], horizontal=True, key="dashboard_editor_mode")
    if mode == "Estúdio Visual (novo)":
        _render_visual_studio()
        return
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

    st.markdown("### Editor de componentes")
    st.caption("Adicione, configure e reordene cada elemento. A série histórica disponível é bimestral.")
    if "dashboard_items" not in st.session_state:
        st.session_state["dashboard_items"] = (
            [{"type": "KPI", "metric": m, "title": m, "width": 3}
             for m in ["Receita realizada", "Despesa empenhada", "Despesa liquidada", "Despesa paga"]]
            + [{"type": "LINE", "metric": "Receita realizada", "title": "Evolução da receita", "width": 12}]
        )
    items = st.session_state["dashboard_items"]
    st.caption("Você pode começar com uma página vazia ou carregar um modelo. Nenhum KPI ou gráfico é obrigatório.")
    start_actions = st.columns(2)
    if start_actions[0].button("Nova página vazia", use_container_width=True, key="designer_blank_page"):
        st.session_state["dashboard_items"] = []
        st.rerun()
    if start_actions[1].button("Carregar modelo fiscal", use_container_width=True, key="designer_load_template"):
        st.session_state["dashboard_items"] = (
            [{"id": str(uuid4()), "type": "KPI", "metric": m, "title": m, "width": 3}
             for m in ["Receita realizada", "Despesa empenhada", "Despesa liquidada", "Despesa paga"]]
            + [{"id": str(uuid4()), "type": "LINE", "metric": "Receita realizada",
                "metrics": ["Receita realizada"], "title": "Evolução da receita", "width": 12}]
        )
        st.rerun()
    st.caption("Métricas disponíveis: " + " · ".join(FISCAL_METRICS))
    st.caption("Dimensões da fonte atual: Ano e Bimestre. Dados acumulados por bimestre.")
    st.caption("Catálogo Apache ECharts · escolha o tipo de visualização antes de configurar as métricas.")
    if st.button("＋ Abrir biblioteca de visualizações", type="primary", use_container_width=True):
        st.session_state["dashboard_show_catalog"] = True
    requested_kind = st.session_state.pop("dashboard_dialog_kind", None)
    if requested_kind:
        _add_component_dialog(requested_kind)
    elif st.session_state.get("dashboard_show_catalog"):
        _chart_catalog_dialog()
    for i, item in enumerate(items):
        if "id" not in item:
            item["id"] = str(uuid4())
        uid = item["id"]
        with st.expander(f"{i+1}. {item['title']} · {item['type']}", expanded=False):
            item["title"] = st.text_input("Título", value=item["title"], key=f"item_title_{uid}")
            if item["type"] == "KPI":
                item["metric"] = st.selectbox("Métrica", list(FISCAL_METRICS),
                    index=list(FISCAL_METRICS).index(item["metric"]), key=f"item_metric_{uid}")
                item["metrics"] = [item["metric"]]
            else:
                item["metrics"] = st.multiselect("Métricas deste objeto", list(FISCAL_METRICS),
                    default=item.get("metrics", [item["metric"]]), key=f"item_metrics_{uid}")
                if item["metrics"]:
                    item["metric"] = item["metrics"][0]
                else:
                    st.warning("Selecione ao menos uma métrica.")
            with st.container(border=True):
                st.markdown("**Aparência do componente**")
                item["background_color"] = st.color_picker("Fundo", value=item.get("background_color", "#FFFFFF"), key=f"bg_{uid}")
                item["text_color"] = st.color_picker("Texto", value=item.get("text_color", "#19283B"), key=f"fg_{uid}")
                fonts = ["Inter", "Arial", "Georgia", "Verdana", "Roboto"]
                item["font_family"] = st.selectbox("Fonte", fonts,
                    index=fonts.index(item.get("font_family", "Inter")), key=f"font_{uid}")
                if item["type"] != "KPI":
                    old_colors = item.get("series_colors", [])
                    item["series_colors"] = [
                        st.color_picker(f"Cor: {metric}", value=old_colors[i] if i < len(old_colors) else ["#168BAF", "#E3A243", "#35A78B", "#727AD1", "#D65A75", "#607D8B"][i % 6],
                                        key=f"series_{uid}_{metric}")
                        for i, metric in enumerate(item["metrics"])
                    ]
            item["width"] = st.select_slider("Largura no grid (12 colunas)", options=[3, 4, 6, 8, 12],
                value=item["width"], key=f"item_width_{uid}")
            if item["type"] != "KPI":
                st.caption("Dimensão: Bimestre · granularidade bimestral (fixa nesta fonte)")
            controls = st.columns(3)
            if controls[0].button("↑ Subir", key=f"item_up_{uid}", disabled=i==0):
                items[i-1],items[i]=items[i],items[i-1]
                st.rerun()
            if controls[1].button("↓ Descer", key=f"item_down_{uid}", disabled=i==len(items)-1):
                items[i+1],items[i]=items[i],items[i+1]
                st.rerun()
            if controls[2].button("Remover", key=f"item_remove_{uid}"):
                items.pop(i)
                st.rerun()
    if any(not item.get("metrics", [item["metric"]]) for item in items):
        st.error("Há componente sem métricas. Selecione pelo menos uma métrica.")
        return
    kpis = [item["metric"] for item in items if item["type"] == "KPI"]
    trend = [item["metric"] for item in items if item["type"] == "LINE"]
    audience_map = {"Executivo": AudienceType.EXECUTIVE, "Gerencial": AudienceType.MANAGERIAL, "Técnico": AudienceType.TECHNICAL, "Público": AudienceType.PUBLIC}
    output_map = {"Web": OutputType.WEB, "PDF": OutputType.PDF, "Excel": OutputType.EXCEL, "Impressão": OutputType.PRINT}
    try:
        project = _build_project(name, audience_name, audience_map[audience_label], objective, filters, kpis, trend, [output_map[x] for x in output_labels])
    except ValueError as exc:
        st.error(f"Projeto inválido: {exc}")
        return

    # Replace the initial template components with the individually edited composition.
    arranged = []
    cursor_y = 0
    for item in items:
        visual_type = ComponentType(item["type"])
        dimension = ([DimensionBinding(field="bimestre", label="Bimestre",
                      role=FieldRole.TEMPORAL_DIMENSION if visual_type == ComponentType.LINE else FieldRole.DIMENSION,
                      granularity="BIMESTRAL")] if visual_type != ComponentType.KPI else [])
        arranged.append(DashboardComponent(
            title=item["title"], component_type=visual_type, source_id="fiscal",
            metrics=[_metric(m) for m in item.get("metrics", [item["metric"]])], dimensions=dimension,
            background_color=item.get("background_color", "#FFFFFF"),
            text_color=item.get("text_color", "#19283B"),
            font_family=item.get("font_family", "Inter"),
            series_colors=item.get("series_colors", []),
            position=GridPosition(x=0, y=cursor_y, width=item["width"],
                                  height=2 if visual_type == ComponentType.KPI else 5),
        ))
        cursor_y += 2 if visual_type == ComponentType.KPI else 5
    project.pages[0].components = arranged
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
