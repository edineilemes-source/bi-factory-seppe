"""Main Streamlit application."""

import streamlit as st

from app.components.profiling_view import render_profile
from core.ingestion.file_loader import (
    discover_workspace_files,
    load_tabular_file,
    load_workspace_file,
)
from core.profiling.models import ProjectContext
from core.profiling.workbook_profiler import profile_workbook


def run() -> None:
    """Render upload, project context and the technical diagnosis."""
    st.set_page_config(page_title="BI Factory SEPPE", page_icon="📊", layout="wide")
    st.title("BI Factory SEPPE")
    st.subheader("Plataforma de Engenharia da Informação")
    st.write("Módulo 01 — Ingestão e Profiling")

    with st.sidebar:
        st.header("Contexto do projeto")
        project_name = st.text_input("Nome do projeto")
        business_domain = st.text_input("Domínio de negócio")
        purpose = st.text_area("Finalidade")
        notes = st.text_area("Observações opcionais")

    uploaded_file = st.file_uploader(
        "Envie uma fonte tabular",
        type=["xlsx", "xlsm", "csv"],
        help="O arquivo é processado em memória e não é alterado.",
    )
    if uploaded_file is not None:
        st.caption(f"Tamanho do upload: {uploaded_file.size / (1024 * 1024):.2f} MB")

    st.markdown("### Arquivos disponíveis no ambiente")
    workspace_files = discover_workspace_files()
    selected_workspace_file = None
    analyze_workspace_file = False
    if workspace_files:
        selected_workspace_file = st.selectbox(
            "Selecione um arquivo de storage/originals",
            options=workspace_files,
            format_func=lambda path: (
                f"{path.name} ({path.stat().st_size / (1024 * 1024):.2f} MB)"
            ),
        )
        analyze_workspace_file = st.button("Analisar arquivo")
    else:
        st.info("Nenhum arquivo XLSX, XLSM ou CSV disponível em storage/originals.")

    if uploaded_file is None and not analyze_workspace_file:
        st.info(
            "Envie um arquivo XLSX, XLSM ou CSV ou selecione um arquivo disponível "
            "no ambiente para gerar o diagnóstico técnico."
        )
        return

    context = ProjectContext(
        project_name=project_name,
        business_domain=business_domain,
        purpose=purpose,
        notes=notes,
    )
    try:
        with st.spinner("Analisando a estrutura da fonte..."):
            if analyze_workspace_file and selected_workspace_file is not None:
                workbook = load_workspace_file(selected_workspace_file)
            else:
                workbook = load_tabular_file(
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                    source_type="browser_upload",
                )
            profile = profile_workbook(workbook, context)
    except (ValueError, OSError, RuntimeError) as error:
        st.error(f"Não foi possível processar o arquivo: {error}")
        return

    st.success("Diagnóstico técnico concluído.")
    render_profile(profile)
