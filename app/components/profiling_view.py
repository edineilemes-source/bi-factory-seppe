"""Streamlit presentation components for workbook diagnostics."""

import streamlit as st

from core.profiling.models import FieldProfile, SheetProfile, WorkbookProfile


def _field_row(field: FieldProfile) -> dict[str, object]:
    return {
        "Nome original": field.original_name,
        "Nome técnico": field.technical_name,
        "Tipo detectado": field.detected_type,
        "Tipo recomendado": field.recommended_type,
        "Nulos": field.null_count,
        "% nulos": field.null_percentage,
        "Distintos": field.distinct_count,
        "Exemplos": ", ".join(map(str, field.examples)),
        "Chave candidata": field.is_candidate_key,
        "Possível data": field.is_possible_date,
        "Possível medida": field.is_possible_measure,
        "Possível categoria": field.is_possible_category,
    }


def _show_warnings(sheet: SheetProfile) -> None:
    st.markdown("#### Alertas da aba")
    if not sheet.warnings:
        st.success("Nenhum alerta estrutural identificado na amostra.")
        return
    for warning in sheet.warnings:
        field = f" — campo: {warning.field_name}" if warning.field_name else ""
        st.warning(f"{warning.message}{field}")


def render_profile(profile: WorkbookProfile) -> None:
    """Render summary, inventory, fields, warnings and JSON export."""
    summary = profile.summary
    st.markdown("### Resumo geral")
    st.caption(
        f"Arquivo: {profile.original_name} · Origem: {profile.source_type} · "
        f"Tamanho: {profile.size_bytes / (1024 * 1024):.2f} MB"
    )
    metric_columns = st.columns(4)
    metric_columns[0].metric("Abas", summary.sheet_count)
    metric_columns[1].metric("Linhas aproximadas", summary.total_approximate_rows)
    metric_columns[2].metric("Colunas", summary.total_columns)
    metric_columns[3].metric("Alertas", summary.warning_count)

    st.caption(
        "Contagens são aproximadas e o profiling usa amostra controlada de até "
        "10.000 linhas por aba. As classificações abaixo são hipóteses heurísticas."
    )
    inventory = [
        {
            "Aba/fonte": sheet.name,
            "Papel sugerido (hipótese)": sheet.role_hypothesis,
            "Linhas aproximadas": sheet.approximate_row_count,
            "Colunas": sheet.column_count,
            "Cabeçalho provável (linha)": sheet.probable_header_row,
            "Linhas amostradas": sheet.sampled_data_row_count,
            "Alertas": len(sheet.warnings),
        }
        for sheet in profile.sheets
    ]
    st.dataframe(inventory, use_container_width=True, hide_index=True)

    selected_name = st.selectbox(
        "Selecione uma aba para detalhar",
        options=[sheet.name for sheet in profile.sheets],
    )
    selected_sheet = next(sheet for sheet in profile.sheets if sheet.name == selected_name)
    st.markdown(f"### Profiling dos campos — {selected_sheet.name}")
    st.info(f"Classificação sugerida (hipótese): {selected_sheet.role_hypothesis}")
    st.dataframe(
        [_field_row(field) for field in selected_sheet.fields],
        use_container_width=True,
        hide_index=True,
    )
    _show_warnings(selected_sheet)

    diagnostic_json = profile.model_dump_json(indent=2)
    with st.expander("JSON completo do diagnóstico"):
        st.json(profile.model_dump(mode="json"))
    st.download_button(
        "Baixar diagnóstico em JSON",
        data=diagnostic_json,
        file_name=f"{profile.original_name}.diagnostico.json",
        mime="application/json",
    )
