"""Streamlit presentation components for workbook diagnostics."""

import streamlit as st

from app.dataframe_compat import arrow_compatible_dataframe

from core.profiling.models import FieldProfile, SheetProfile, WorkbookProfile


def _field_row(field: FieldProfile) -> dict[str, object]:
    return {
        "Campo original": field.original_name,
        "Nome técnico": field.technical_name,
        "Tipo detectado": field.detected_type,
        "Tipo recomendado": field.recommended_type,
        "Papel semântico sugerido": field.semantic_role_candidate.value,
        "Confiança": f"{field.semantic_role_confidence:.0%}",
        "Nulos %": field.null_percentage,
        "Distintos": field.distinct_count,
        "Exemplos": ", ".join(map(str, field.examples)),
    }


def _show_warnings(sheet: SheetProfile) -> None:
    st.markdown("#### Alertas da aba")
    if not sheet.warnings:
        st.success("Nenhum alerta estrutural identificado na amostra.")
        return
    for warning in sheet.warnings:
        field = f" — campo: {warning.field_name}" if warning.field_name else ""
        renderer = {
            "info": st.info,
            "warning": st.warning,
            "error": st.error,
        }[warning.level]
        renderer(f"[{warning.code}] {warning.message}{field}")


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
            "Estratégia de amostragem": sheet.sampling_strategy,
            "Alertas": len(sheet.warnings),
        }
        for sheet in profile.sheets
    ]
    st.dataframe(arrow_compatible_dataframe(
        inventory,
        integer_columns=("Linhas aproximadas", "Colunas", "Cabeçalho provável (linha)",
                         "Linhas amostradas", "Alertas"),
    ), use_container_width=True, hide_index=True)

    selected_name = st.selectbox(
        "Selecione uma aba para detalhar",
        options=[sheet.name for sheet in profile.sheets],
    )
    selected_sheet = next(sheet for sheet in profile.sheets if sheet.name == selected_name)
    st.markdown(f"### Profiling dos campos — {selected_sheet.name}")
    st.info(f"Classificação sugerida (hipótese): {selected_sheet.role_hypothesis}")
    st.warning("Classificação semântica preliminar — requer validação.")
    st.dataframe(
        arrow_compatible_dataframe(
            [_field_row(field) for field in selected_sheet.fields],
            numeric_columns=("Nulos %",), integer_columns=("Distintos",),
        ),
        use_container_width=True,
        hide_index=True,
    )
    with st.expander("Evidências, alertas e estatísticas detalhadas"):
        for field in selected_sheet.fields:
            st.markdown(f"#### {field.original_name}")
            st.write("Evidências:", field.semantic_evidence or ["Sem evidência suficiente na amostra."])
            st.write("Warnings:", [warning.model_dump() for warning in field.warnings] or [])
            st.json({
                "sample_status": field.sample_status.value,
                "non_null_count": field.non_null_count,
                "distinct_ratio": field.distinct_ratio,
                "average_text_length": field.average_text_length,
                "min_text_length": field.min_text_length,
                "max_text_length": field.max_text_length,
                "numeric_min": field.numeric_min,
                "numeric_max": field.numeric_max,
                "numeric_mean": field.numeric_mean,
                "negative_count": field.negative_count,
                "zero_count": field.zero_count,
                "constant_value": field.constant_value,
            })
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
