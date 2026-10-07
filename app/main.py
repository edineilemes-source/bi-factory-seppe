"""Main Streamlit application."""

from pathlib import Path
from typing import Callable
import logging

import streamlit as st

from app.components.profiling_view import render_profile
from app.components.semantic_validation_view import render_semantic_validation
from app.components.data_quality_view import render_data_quality
from app.components.prepared_dataset_view import render_prepared_dataset
from app.components.grain_discovery_view import render_grain_discovery
from app.components.dimensional_discovery_view import render_dimensional_discovery
from app.components.star_schema_contract_view import render_star_schema_contract
from app.components.postgresql_ddl_view import render_postgresql_ddl
from app.components.dimensional_etl_plan_view import render_dimensional_etl_plan
from app.components.dimensional_transformation_view import render_dimensional_transformation
from app.components.database_dry_run_view import render_database_dry_run
from app.components.official_fiscal_dashboard_view import render_official_fiscal_dashboard
from app.components.dashboard_project_designer_view import render_dashboard_project_designer
from app.session_state import (
    initialize_session_state,
    reset_analysis_state,
    resume_persistent_analysis,
    resolve_render_stage,
    select_analysis,
    start_persistent_analysis,
)
from core.ingestion.file_loader import (LoadedWorkbook, discover_workspace_files,
                                        load_tabular_file, load_workspace_file)
from core.persistence.repository import AnalysisRepository
from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.profiling.models import ProjectContext, WorkbookProfile
from core.semantic.models import AnalysisStatus
from core.persistence.models import AnalysisHistoryItem
from core.persistence.models import AnalysisStage
from core.profiling.workbook_profiler import profile_workbook


LOGGER = logging.getLogger(__name__)


@st.cache_resource
def _repository() -> SQLiteAnalysisRepository:
    repository = SQLiteAnalysisRepository()
    repository.mark_stale_prepared_generations_interrupted()
    return repository


def _start_analysis(repository: AnalysisRepository, content: bytes, original_name: str,
                    factory: Callable[[], WorkbookProfile], workbook: LoadedWorkbook) -> None:
    try:
        with st.spinner("Analisando a estrutura da fonte..."):
            start_persistent_analysis(
                st.session_state, repository, content, original_name, factory,
            )
    except (ValueError, OSError, RuntimeError) as error:
        st.error(f"Não foi possível processar o arquivo: {error}")
    else:
        st.session_state["current_workbook"] = workbook
        st.session_state["current_source_content"] = content
        st.session_state["current_source_name"] = original_name
        st.session_state["current_source_type"] = workbook.source_type
        st.success("Nova análise criada e persistida.")


def _resume_analysis(repository: AnalysisRepository, analysis_id: str,
                     source_document_id: str, workbook: LoadedWorkbook, content: bytes) -> None:
    try:
        select_analysis(st.session_state, analysis_id, source_document_id)
        resume_persistent_analysis(st.session_state, repository, analysis_id)
    except (ValueError, OSError, RuntimeError) as error:
        st.error(f"Não foi possível recuperar a análise: {error}")
    else:
        st.session_state["current_workbook"] = workbook
        st.session_state["current_source_content"] = content
        st.session_state["current_source_name"] = workbook.original_name
        st.session_state["current_source_type"] = workbook.source_type
        artifact = st.session_state.get("current_prepared_artifact")
        LOGGER.info(
            "ui_resume analysis_id=%s current_stage=%s last_successful_stage=%s "
            "prepared_dataset_id=%s artifact_loaded=%s grain_report_loaded=%s",
            analysis_id, st.session_state.get("current_analysis_stage"),
            st.session_state.get("last_successful_stage"),
            st.session_state.get("current_prepared_dataset_id"), artifact is not None,
            st.session_state.get("current_grain_report") is not None,
        )
        st.success("Análise recuperada do histórico local.")


def history_actions(item: AnalysisHistoryItem) -> tuple[str, ...]:
    """Pure action policy, also used by component-level regression tests."""
    if item.is_completed:
        return ("view", "artifacts")
    return (("continue", "details", "artifacts") if item.is_resumable
            else ("details", "artifacts"))


def _render_history_item(repository: AnalysisRepository, item: AnalysisHistoryItem,
                         key: str, workbook: LoadedWorkbook, content: bytes) -> None:
    latest = " · Mais recente" if item.is_latest else ""
    resumable = " · Pode ser retomada" if item.is_resumable else ""
    title = (f"{item.created_at.astimezone().strftime('%d/%m/%Y %H:%M')} — "
             f"{item.current_stage.value.replace('_', ' ').title()} — {item.status}{latest}{resumable}")
    with st.container(border=True):
        st.markdown(f"#### {title}")
        metrics = st.columns(4)
        metrics[0].metric("Etapa atual", item.current_stage.value)
        metrics[1].metric("Última concluída", item.last_successful_stage.value)
        metrics[2].metric("Perguntas", f"{item.semantic_answered_count}/{item.semantic_question_count}")
        metrics[3].metric("Artefatos", item.artifact_count)
        st.write(
            f"Semântica: {item.semantic_status} · Qualidade: {item.quality_status} "
            f"({item.quality_issue_count} issues) · Prepared: {item.prepared_dataset_status}"
        )
        st.caption(
            f"Grão: {item.grain_status} · Dimensional: {item.dimensional_status} · "
            f"Star: {item.star_schema_status} · DDL: {item.ddl_status} · "
            f"ETL: {item.etl_plan_status} · Transformação: {item.transformation_status} · "
            f"Dry Run: {item.database_dry_run_status}"
        )
        if item.warnings:
            st.warning("ANALYSIS_RECOVERY_WARNING — " + " ".join(item.warnings))
        actions = history_actions(item)
        columns = st.columns(len(actions))
        labels = {"continue": "Continuar esta análise", "view": "Ver análise concluída",
                  "details": "Ver detalhes", "artifacts": "Ver artefatos"}
        for column, action in zip(columns, actions):
            if column.button(labels[action], key=f"{action}_{key}_{item.analysis_id}"):
                if action in ("continue", "view"):
                    _resume_analysis(repository, item.analysis_id, item.source_document_id,
                                     workbook, content)
                elif action == "artifacts":
                    st.json(item.artifact_ids)
        with st.expander("Detalhes técnicos"):
            st.json({
                "analysis_id": item.analysis_id,
                "source_document_id": item.source_document_id,
                "created_at_utc": item.created_at.isoformat(),
                "updated_at_utc": item.updated_at.isoformat(),
                "status": item.status,
                "artifact_ids": item.artifact_ids,
            })


def _source_actions(repository: AnalysisRepository, content: bytes, original_name: str,
                    key: str, factory: Callable[[], WorkbookProfile],
                    workbook: LoadedWorkbook) -> None:
    document = repository.find_document(content)
    analyses = (repository.list_analyses_for_document(document.source_document_id)
                if document else [])
    if analyses:
        st.info(f"Este documento possui {len(analyses)} análises anteriores.")
        st.write("Escolha qual análise deseja abrir ou inicie uma nova análise.")
        unfinished = [item for item in analyses if item.has_unfinished_work]
        if len(unfinished) > 1:
            st.warning(f"Existem {len(unfinished)} análises não concluídas deste documento.")
        for item in analyses:
            _render_history_item(repository, item, key, workbook, content)
        if unfinished:
            st.warning("Existe uma análise em andamento deste documento.")
            if st.button("Iniciar nova análise mesmo assim", key=f"new_force_{key}"):
                _start_analysis(repository, content, original_name, factory, workbook)
        elif st.button("Iniciar nova análise", key=f"new_{key}"):
            _start_analysis(repository, content, original_name, factory, workbook)
    elif st.button("Analisar", key=f"analyze_{key}"):
        _start_analysis(repository, content, original_name, factory, workbook)


def run() -> None:
    """Render source selection and the session-persistent diagnosis."""
    st.set_page_config(page_title="BI Factory SEPPE", page_icon="📊", layout="wide")
    initialize_session_state(st.session_state)
    repository = _repository()
    st.title("BI Factory SEPPE")

    mode = st.sidebar.radio(
        "Área",
        ("BI Fiscal Oficial", "Projetos de Dashboard", "BI Factory — Planilhas"),
        index=0,
        key="app_area",
    )
    if mode == "BI Fiscal Oficial":
        render_official_fiscal_dashboard()
        return
    if mode == "Projetos de Dashboard":
        render_dashboard_project_designer()
        return

    if st.sidebar.checkbox("BI MVP por Analysis ID (artefatos persistidos)", value=st.query_params.get("mvp") == "1"):
        from app.components.bi_mvp_view import render_bi_mvp
        render_bi_mvp(repository)
        return
    st.subheader("Plataforma de Engenharia da Informação")
    st.write("Módulo 01 — Ingestão, Profiling e Validação Semântica")

    with st.sidebar:
        st.header("Contexto do projeto")
        project_name = st.text_input("Nome do projeto")
        business_domain = st.text_input("Domínio de negócio")
        purpose = st.text_area("Finalidade")
        notes = st.text_area("Observações opcionais")
        if st.session_state["analysis_completed"] and st.button("Fechar análise atual"):
            reset_analysis_state(st.session_state)
            st.success("A tela foi limpa. A análise permanece salva no SQLite.")

    context = ProjectContext(
        project_name=project_name, business_domain=business_domain,
        purpose=purpose, notes=notes,
    )
    uploaded_file = st.file_uploader(
        "Envie uma fonte tabular", type=["xlsx", "xlsm", "csv"],
        help="O arquivo é processado em memória e não é alterado.",
    )
    if uploaded_file is not None:
        upload_bytes = uploaded_file.getvalue()
        upload_workbook = load_tabular_file(uploaded_file.name, upload_bytes, source_type="browser_upload")
        st.caption(f"Tamanho do upload: {uploaded_file.size / (1024 * 1024):.2f} MB")
        _source_actions(
            repository, upload_bytes, uploaded_file.name, "upload",
            lambda: profile_workbook(
                upload_workbook,
                context,
            ),
            upload_workbook,
        )

    st.markdown("### Arquivos disponíveis no ambiente")
    workspace_files = discover_workspace_files()
    if workspace_files:
        selected_path: Path = st.selectbox(
            "Selecione um arquivo de storage/originals", options=workspace_files,
            format_func=lambda path: f"{path.name} ({path.stat().st_size / (1024 * 1024):.2f} MB)",
        )
        stat = selected_path.stat()
        workspace_bytes = selected_path.read_bytes()
        workspace_workbook = load_workspace_file(selected_path)
        st.caption(f"Tamanho do arquivo: {stat.st_size / (1024 * 1024):.2f} MB")
        _source_actions(
            repository, workspace_bytes, selected_path.name, "workspace",
            lambda: profile_workbook(workspace_workbook, context), workspace_workbook,
        )
    else:
        st.info("Nenhum arquivo XLSX, XLSM ou CSV disponível em storage/originals.")

    if not st.session_state["analysis_completed"]:
        st.info("Selecione uma fonte e clique em Analisar para gerar o diagnóstico técnico.")
        return

    render_profile(st.session_state["current_profile"])
    render_semantic_validation(st.session_state)
    if st.session_state["current_validation_report"].analysis_status != AnalysisStatus.IN_PROGRESS:
        try:
            stage = resolve_render_stage(st.session_state)
        except (ValueError, OSError) as error:
            st.error(f"Não foi possível resolver a etapa ativa: {error}")
            return
        renderers = {
            AnalysisStage.QUALITY: render_data_quality,
            AnalysisStage.PREPARED_DATASET: render_prepared_dataset,
            AnalysisStage.GRAIN_DISCOVERY: render_grain_discovery,
            AnalysisStage.DIMENSIONAL_DISCOVERY: render_dimensional_discovery,
            AnalysisStage.STAR_SCHEMA: render_star_schema_contract,
            AnalysisStage.DDL: render_postgresql_ddl,
            AnalysisStage.ETL_PLAN: render_dimensional_etl_plan,
            AnalysisStage.TRANSFORMATION: render_dimensional_transformation,
            AnalysisStage.DATABASE_DRY_RUN: render_database_dry_run,
        }
        renderer = renderers.get(stage)
        if renderer is None:
            st.error(f"Não existe componente registrado para a etapa {stage.value}.")
            return
        renderer(st.session_state)
