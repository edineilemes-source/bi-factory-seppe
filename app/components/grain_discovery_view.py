"""Human-in-the-loop analytical-grain discovery UI."""

from collections.abc import MutableMapping
from typing import Any

import streamlit as st

from core.grain.discovery import discover_grain
from core.grain.artifact_discovery import GRAIN_ENGINE_VERSION, discover_grain_from_artifact
from core.grain.export import export_grain_definition_json, export_grain_discovery_json
from core.grain.models import GrainDefinition, GrainDiscoveryReport
from core.grain.validation import record_unknown_grain, validate_grain
from core.prepared.models import PreparedDataset, PreparedDatasetArtifact, PreparedDatasetStatus
from app.session_state import validate_grain_prepared_artifact
from core.prepared.artifact_reader import PreparedDatasetArtifactReader


def run_grain_discovery(state: MutableMapping[str, Any]) -> GrainDiscoveryReport:
    artifact = validate_grain_prepared_artifact(state)
    if artifact.status == PreparedDatasetStatus.BLOCKED:
        raise ValueError("O Quality Gate está BLOCKED; resolva ou valide os bloqueios primeiro.")
    repository = state.get("repository")
    if repository:
        for record in repository.list_grain_discovery_reports(artifact.prepared_dataset_id):
            report = record.report
            if (report.analysis_id == artifact.analysis_id
                    and report.prepared_dataset_version == artifact.version
                    and report.prepared_dataset_fingerprint == artifact.fingerprint
                    and report.engine_version == GRAIN_ENGINE_VERSION):
                state["current_grain_report"] = report
                state["grain_report_reused"] = True
                return report
    reader = PreparedDatasetArtifactReader(
        artifact, analysis_id=artifact.analysis_id,
        prepared_dataset_id=artifact.prepared_dataset_id,
        source_document_id=artifact.source_document_id, version=artifact.version,
        fingerprint=artifact.fingerprint)
    version = (repository.next_grain_report_version(artifact.prepared_dataset_id)
               if repository else 1)
    report = discover_grain_from_artifact(reader, version=version)
    if repository:
        repository.save_grain_discovery_report(report)
    state["current_grain_report"] = report
    state["grain_report_reused"] = False
    return report


def _save_validation(state: MutableMapping[str, Any], report: GrainDiscoveryReport,
                     candidate_id: str | None, manual: str | None,
                     process: str | None, event: str | None,
                     source_record_grain: bool = False) -> GrainDefinition:
    repository = state.get("repository")
    version = (repository.next_grain_definition_version(report.prepared_dataset_id)
               if repository else 1)
    definition = validate_grain(
        report, candidate_id=candidate_id, user_grain_description=manual or None,
        validated_process=process or None, validated_event=event or None,
        version=version, source_record_grain=source_record_grain)
    if repository:
        repository.save_grain_definition(definition)
    state["current_grain_definition"] = definition
    return definition


def _save_unknown(state: MutableMapping[str, Any], report: GrainDiscoveryReport) -> GrainDefinition:
    repository = state.get("repository")
    version = repository.next_grain_definition_version(report.prepared_dataset_id) if repository else 1
    definition = record_unknown_grain(report, version=version)
    if repository:
        repository.save_grain_definition(definition)
    state["current_grain_definition"] = definition
    return definition


def render_grain_discovery(state: MutableMapping[str, Any]) -> None:
    try:
        artifact: PreparedDatasetArtifact = validate_grain_prepared_artifact(state)
    except (ValueError, OSError) as error:
        st.error(f"Não foi possível carregar Grain Discovery: {error}")
        return
    st.markdown("## GRÃO ANALÍTICO")
    st.write("Grão define o que cada linha representa.")
    st.info("Em uma tabela de vendas, uma linha pode representar uma venda, um item da venda "
            "ou um pagamento. Essa diferença determina como os valores podem ser somados e comparados.")
    header = st.columns(5)
    header[0].metric("Prepared Dataset", artifact.prepared_dataset_id[:12])
    header[1].metric("Versão", artifact.version)
    header[2].metric("Fingerprint", artifact.fingerprint[:12])
    header[3].metric("Linhas", artifact.row_count)
    header[4].metric("Quality Gate", artifact.status.value)
    report: GrainDiscoveryReport | None = state.get("current_grain_report")
    definition: GrainDefinition | None = state.get("current_grain_definition")
    label = "Reanalisar grão" if report else "Descobrir grão"
    if st.button(label):
        if definition:
            st.warning("Existe uma definição de grão validada para esta versão do dataset. "
                       "A reanálise criará novo relatório e não a sobrescreverá.")
        try:
            run_grain_discovery(state)
        except (ValueError, RuntimeError) as error:
            st.error(str(error))
        else:
            st.rerun()
    if report is None:
        return
    st.metric("Classificação", report.grain_classification.value)
    st.caption(f"Motor {report.engine_version}. Toda hipótese exige validação humana.")
    st.info("Hipótese inicial do MVP (não confirmada): um registro de despesa/pagamento "
            "conforme a granularidade original da fonte.")
    if report.process_candidates:
        st.write("Processos candidatos:", ", ".join(item.name for item in report.process_candidates))
    if report.event_candidates:
        st.write("Eventos candidatos:", ", ".join(item.name for item in report.event_candidates))
    with st.expander("Exemplos reais da fonte (máximo 5 linhas)"):
        reader = PreparedDatasetArtifactReader(
            artifact, analysis_id=artifact.analysis_id,
            prepared_dataset_id=artifact.prepared_dataset_id,
            source_document_id=artifact.source_document_id, version=artifact.version,
            fingerprint=artifact.fingerprint)
        from app.dataframe_compat import arrow_compatible_dataframe
        st.dataframe(arrow_compatible_dataframe(next(reader.iter_chunks(chunk_size=5), [])))
    options = {f"{item.human_readable_description} ({item.confidence:.0%})": item.candidate_id
               for item in report.grain_candidates}
    selected_label = st.selectbox("Escolher candidato", list(options)) if options else None
    selected_id = options[selected_label] if selected_label else None
    selected = next((item for item in report.grain_candidates
                     if item.candidate_id == selected_id), None)
    if selected:
        st.write("Campos:", selected.candidate_fields)
        coverage = selected.coverage_ratio if selected.coverage_ratio is not None else 1-selected.null_ratio
        complete = (selected.complete_row_count if selected.complete_row_count is not None
                    else selected.distinct_count + selected.duplicate_count)
        st.write(f"Unicidade condicional: {selected.uniqueness_ratio:.2%} · "
                 f"Cobertura: {coverage:.2%} · Linhas completas: {complete:,} · "
                 f"Confiança: {selected.confidence:.2%}")
        if selected.business_process_compatibility:
            st.write("Compatibilidade:", selected.business_process_compatibility)
        st.write("Evidências:", selected.evidence)
        if selected.counter_evidence:
            st.warning("Possíveis problemas: " + " ".join(selected.counter_evidence))
        if selected.quality_dependencies:
            st.warning("A qualidade dos identificadores pode afetar esta hipótese.")
    for risk in report.aggregation_risks:
        st.warning("ATENÇÃO — " + risk.description)
    with st.expander("Detalhes técnicos"):
        st.write("Dependências funcionais observadas", report.functional_dependencies)
        st.write("Hierarquias observadas", report.identifier_hierarchies)
        st.write("Limite de candidatos", report.candidate_limit_configured)
    source_record = st.checkbox(
        "Usar a granularidade do registro de origem com chave substituta técnica",
        help="Preserva todas as linhas e identificadores originais sem afirmar uma chave natural global.")
    manual = st.text_area("Ou descreva manualmente: Uma linha representa ...")
    process = st.text_input("Processo validado/corrigido")
    event = st.text_input("Evento validado/corrigido")
    actions = st.columns(2)
    if actions[0].button("Confirmar definição de grão"):
        try:
            _save_validation(state, report, None if (manual or source_record) else selected_id,
                             manual or None, process or None, event or None,
                             source_record_grain=source_record)
        except ValueError as error:
            st.error(str(error))
        else:
            st.rerun()
    if actions[1].button("Não sei / preciso investigar"):
        _save_unknown(state, report)
        st.rerun()
    st.download_button("Baixar relatório de descoberta do grão — JSON",
                       export_grain_discovery_json(report),
                       file_name=f"grain-discovery-{report.prepared_dataset_id}-v{report.version}.json",
                       mime="application/json")
    if definition and definition.status.value == "READY_FOR_DIMENSIONAL_MODELING":
        st.success("READY_FOR_DIMENSIONAL_MODELING — definição humana validada.")
        st.download_button("Baixar definição validada do grão — JSON",
                           export_grain_definition_json(definition),
                           file_name=f"grain-definition-{definition.prepared_dataset_id}-v{definition.version}.json",
                           mime="application/json")
