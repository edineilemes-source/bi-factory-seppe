"""Streamlit view for persisted, read-only data-quality findings."""

from collections.abc import MutableMapping
from typing import Any

import streamlit as st

from app.dataframe_compat import arrow_compatible_dataframe

from core.quality.engine import analyze_data_quality
from core.quality.export import (
    export_field_summary_csv, export_quality_report_json, quality_report_id,
)
from core.quality.models import DataQualityReport
from core.quality.gate import decide_quality_gate, is_blocking_issue
from core.persistence.models import AnalysisStage


def _render_report(report: DataQualityReport) -> None:
    st.markdown("## QUALIDADE DOS DADOS")
    metrics = st.columns(9)
    metrics[0].metric("Quality Score", f"{report.score:.2f}")
    metrics[1].metric("Observed Completeness", f"{report.observed_completeness:.2f}%")
    metrics[2].metric("Issues", report.issues_count)
    metrics[3].metric("Critical", report.critical_count)
    metrics[4].metric("Errors", report.error_count)
    metrics[5].metric("Warnings", report.warning_count)
    metrics[6].metric("Evaluated Fields", report.evaluated_fields)
    metrics[7].metric("Not Evaluated Fields", report.not_evaluated_fields)
    metrics[8].metric("Linhas analisadas", report.total_rows)
    st.caption(report.score_formula)
    gate = report.gate_decision or decide_quality_gate(report.issues)
    st.markdown("### QUALITY GATE")
    gate_metrics = st.columns(4)
    gate_metrics[0].metric("Status", gate.status.value)
    gate_metrics[1].metric("Blocking issues", gate.blocking_issues)
    gate_metrics[2].metric("Warnings", gate.warnings)
    gate_metrics[3].metric("Needs business rule", gate.unresolved_business_rules)
    st.caption(gate.reason)
    field_summary = arrow_compatible_dataframe([{
        "Campo": item.field_name,
        "Papel Semântico Efetivo": item.effective_semantic_role.value,
        "Requirement": item.requirement.value,
        "Applicability": item.applicability.value,
        "Quality Status": item.quality_status.value,
        "Quality Score": item.quality_score,
        "Completeness": item.observed_completeness,
        "Issues": item.issues_count,
        "Severidade máxima": item.maximum_severity.value if item.maximum_severity else "—",
    } for item in report.field_summaries],
        numeric_columns=("Quality Score", "Completeness"),
        integer_columns=("Issues",),
    )
    st.dataframe(
        field_summary, use_container_width=True, hide_index=True,
        column_config={
            "Quality Score": st.column_config.NumberColumn(format="%.2f"),
            "Completeness": st.column_config.NumberColumn(format="%.2f%%"),
        },
    )
    field_options = {f"{item.sheet_name} · {item.field_name}": item.source_field_id
                     for item in report.field_summaries}
    if field_options:
        selected = st.selectbox("Detalhar campo", list(field_options))
        findings = [issue for issue in report.issues
                    if issue.source_field_id == field_options[selected]]
        for issue in findings:
            with st.container(border=True):
                st.write(f"{issue.issue_type.value} · {issue.severity.value.upper()}")
                st.write("Quality defect status:", issue.quality_defect_status.value)
                st.write("Blocking?:", "Sim" if is_blocking_issue(issue) else "Não")
                if issue.blocking_reason:
                    st.write("Blocking reason:", issue.blocking_reason)
                st.write(issue.reason)
                st.caption(f"{issue.affected_count} ocorrência(s) · {issue.affected_percentage:.2f}%")
                st.write("Exemplos:", issue.examples)
                if issue.evidence:
                    st.write("Evidência:", issue.evidence)
                st.write("Ação sugerida:", issue.suggested_action)


def _render_downloads(report: DataQualityReport, source_document_id: str) -> None:
    report_id = quality_report_id(report).replace(":", "-")
    downloads = st.columns(2)
    downloads[0].download_button(
        "Baixar relatório completo de qualidade (JSON)",
        data=export_quality_report_json(report, source_document_id),
        file_name=f"relatorio-qualidade-{report.analysis_id}-{report_id}.json",
        mime="application/json",
    )
    downloads[1].download_button(
        "Baixar resumo por campo (CSV)",
        data=export_field_summary_csv(report, source_document_id),
        file_name=f"resumo-qualidade-{report.analysis_id}-{report_id}.csv",
        mime="text/csv",
    )


def reanalyze_quality(state: MutableMapping[str, Any]) -> DataQualityReport:
    """Replace the current report only with the newly generated/persisted version."""
    repository = state.get("repository")
    current = state.get("current_quality_report")
    version = (current.version + 1 if current else
               len(repository.list_quality_reports(state["analysis_id"])) + 1
               if repository else 1)
    generated = analyze_data_quality(
        state["current_workbook"], state["current_validation_report"])
    generated.version = version
    if repository is not None:
        generated = repository.save_quality_report(generated)
    state["current_quality_report"] = generated
    state["current_analysis_stage"] = AnalysisStage.PREPARED_DATASET
    state["last_successful_stage"] = AnalysisStage.QUALITY
    return generated


def render_data_quality(state: MutableMapping[str, Any]) -> None:
    report = state.get("current_quality_report")
    repository = state.get("repository")
    workbook = state.get("current_workbook")
    semantic = state.get("current_validation_report")
    if report:
        _render_report(report)
        label = "Reanalisar qualidade"
    else:
        st.markdown("## QUALIDADE DOS DADOS")
        label = "Analisar qualidade dos dados"
    if workbook is None:
        st.info("Selecione novamente a fonte original para executar ou reexecutar a qualidade.")
        return
    if st.button(label):
        with st.spinner("Analisando a qualidade dos dados..."):
            reanalyze_quality(state)
        st.rerun()
    if report:
        source_document_id = (state.get("source_document_id")
                              or getattr(semantic, "source_document_id", None)
                              or "unknown-source-document")
        _render_downloads(report, source_document_id)
