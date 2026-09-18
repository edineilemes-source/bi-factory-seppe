"""Human-in-the-loop dimensional discovery UI; artifact-backed and restart-safe."""

from collections import Counter
from collections.abc import Iterator, MutableMapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import streamlit as st

from app.session_state import resolve_prepared_artifact_for_analysis
from core.dimensional.discovery import discover_dimensions
from core.dimensional.export import export_dimensional_discovery_json, export_validated_dimensional_json
from core.dimensional.models import DimensionRole, FactType, ModelingRole
from core.dimensional.validation import validate_dimensional_discovery
from core.prepared.artifact_reader import PreparedDatasetArtifactReader
from core.prepared.models import PreparedDatasetArtifact, PreparedRow


class _LazyPreparedRows:
    """Re-iterable Prepared rows backed by the persisted CSV."""

    def __init__(self, reader: PreparedDatasetArtifactReader,
                 artifact: PreparedDatasetArtifact, chunk_size: int = 5000):
        self.reader = reader
        self.artifact = artifact
        self.chunk_size = chunk_size
        self.technical_to_source = {
            field.technical_name: field.source_field_id for field in artifact.schema_fields
        }
        self.source_ids = {field.source_field_id for field in artifact.schema_fields}

    def __iter__(self) -> Iterator[PreparedRow]:
        fallback_sheet = self.artifact.schema_fields[0].sheet_name if self.artifact.schema_fields else ""
        for chunk in self.reader.iter_chunks(chunk_size=self.chunk_size):
            for position, raw in enumerate(chunk):
                if hasattr(raw, "to_dict"):
                    raw = raw.to_dict()
                elif not isinstance(raw, dict):
                    raw = dict(raw)

                values = {}
                for key, value in raw.items():
                    if key in {"source_row_id", "sheet_name", "source_row_number"}:
                        continue
                    source_id = key if key in self.source_ids else self.technical_to_source.get(key)
                    if source_id:
                        values[source_id] = value

                row_number = raw.get("source_row_number")
                try:
                    row_number = int(row_number)
                except (TypeError, ValueError):
                    row_number = position + 1

                yield PreparedRow(
                    source_row_id=str(raw.get("source_row_id") or f"artifact-row:{row_number}"),
                    sheet_name=str(raw.get("sheet_name") or fallback_sheet),
                    source_row_number=row_number,
                    values=values,
                )


@dataclass
class _ArtifactBackedPreparedDataset:
    """Duck-typed PreparedDataset contract without full row materialization."""

    artifact: PreparedDatasetArtifact
    reader: PreparedDatasetArtifactReader
    unresolved_quality_issues: list[Any]
    chunk_size: int = 5000

    @property
    def prepared_dataset_id(self): return self.artifact.prepared_dataset_id
    @property
    def source_document_id(self): return self.artifact.source_document_id
    @property
    def analysis_id(self): return self.artifact.analysis_id
    @property
    def version(self): return self.artifact.version
    @property
    def ruleset_version(self): return self.artifact.ruleset_version
    @property
    def row_count(self): return self.artifact.row_count
    @property
    def field_count(self): return self.artifact.field_count
    @property
    def status(self): return self.artifact.status
    @property
    def schema_fields(self): return self.artifact.schema_fields
    @property
    def statistics(self): return self.artifact.statistics
    @property
    def fingerprint(self): return self.artifact.fingerprint
    @property
    def artifact_location(self): return self.artifact.artifact_location

    @property
    def rows(self):
        return _LazyPreparedRows(self.reader, self.artifact, self.chunk_size)


def _quality_issues(state: MutableMapping[str, Any]) -> list[Any]:
    report = state.get("current_quality_report")
    if report is None:
        return []
    return list(getattr(report, "issues", None) or
                getattr(report, "quality_issues", None) or [])


def _resolve_inputs(state: MutableMapping[str, Any]):
    artifact = resolve_prepared_artifact_for_analysis(state)
    repository = state.get("repository")
    if repository is None:
        raise ValueError("Descoberta Dimensional indisponível: repositório não resolvido.")

    grain = state.get("current_grain_definition")
    if grain is None or grain.prepared_dataset_id != artifact.prepared_dataset_id:
        grain = repository.get_effective_grain(artifact.prepared_dataset_id)
        state["current_grain_definition"] = grain
    if grain is None:
        raise ValueError("Effective Grain validado não encontrado para o Prepared Dataset.")

    grain_report = state.get("current_grain_report")
    expected_report_id = grain.grain_discovery_report_id
    if grain_report is None or grain_report.grain_discovery_report_id != expected_report_id:
        records = repository.list_grain_discovery_reports(artifact.prepared_dataset_id)
        grain_report = next(
            (record.report for record in records
             if record.report.grain_discovery_report_id == expected_report_id), None)
        state["current_grain_report"] = grain_report
    if grain_report is None:
        raise ValueError("Relatório Grain associado à definição validada não encontrado.")

    if (grain.prepared_dataset_id != artifact.prepared_dataset_id
            or grain.prepared_dataset_version != artifact.version
            or grain.prepared_dataset_fingerprint != artifact.fingerprint):
        raise ValueError("Prepared e Effective Grain possuem versão/fingerprint incompatíveis.")

    reader = PreparedDatasetArtifactReader(
        artifact, analysis_id=artifact.analysis_id,
        prepared_dataset_id=artifact.prepared_dataset_id,
        source_document_id=artifact.source_document_id,
        version=artifact.version, fingerprint=artifact.fingerprint)

    dataset = _ArtifactBackedPreparedDataset(
        artifact=artifact, reader=reader,
        unresolved_quality_issues=_quality_issues(state))
    return artifact, dataset, grain, grain_report


def run_dimensional_discovery(state: MutableMapping[str, Any]):
    artifact, dataset, grain, grain_report = _resolve_inputs(state)
    repository = state.get("repository")
    version = repository.next_dimensional_report_version(artifact.prepared_dataset_id) if repository else 1
    report = discover_dimensions(dataset, grain, grain_report, version=version)
    if repository:
        repository.save_dimensional_discovery_report(report)
    state["current_dimensional_report"] = report
    return report


def render_dimensional_discovery(state: MutableMapping[str, Any]) -> None:
    st.markdown("## DESCOBERTA DIMENSIONAL")
    try:
        artifact, _, grain, _ = _resolve_inputs(state)
    except (ValueError, OSError, RuntimeError) as error:
        st.error(f"Não foi possível carregar a Descoberta Dimensional: {error}")
        return

    st.caption("Proposta explicável; nenhuma tabela, FK, DDL ou ETL será gerada nesta etapa.")
    cols = st.columns(5)
    cols[0].metric("Processo", grain.effective_process or "Não definido")
    cols[1].metric("Evento", grain.effective_event or "Não definido")
    cols[2].metric("Grão validado", grain.effective_grain_description)
    cols[3].metric("Prepared Dataset", artifact.prepared_dataset_id[:12])
    cols[4].metric("Quality Gate", artifact.status.value)

    report = state.get("current_dimensional_report")
    if report is not None and (
        report.prepared_dataset_id != artifact.prepared_dataset_id
        or report.prepared_dataset_version != artifact.version
        or report.prepared_dataset_fingerprint != artifact.fingerprint
        or report.grain_definition_id != grain.grain_id
    ):
        report = None
        state["current_dimensional_report"] = None

    if st.button("Redescobrir fatos e dimensões" if report else "Descobrir fatos e dimensões"):
        try:
            run_dimensional_discovery(state)
        except (ValueError, OSError, RuntimeError) as error:
            st.error(str(error))
        else:
            st.rerun()

    if report is None:
        return

    st.markdown("### FACT CANDIDATES")
    for fact in report.fact_candidates:
        with st.expander(f"{fact.human_readable_name} · {fact.fact_type.value} · {fact.confidence:.0%}"):
            st.write("Grão", fact.grain_fields)
            st.write("Medidas", fact.measure_candidates or "Factless")
            st.write("Identificadores degenerados", fact.degenerate_dimensions)
            st.write("Dimensões relacionadas", fact.foreign_dimension_candidates)
            for risk in fact.aggregation_risks:
                st.warning(risk.description)

    st.markdown("### DIMENSION CANDIDATES")
    for dimension in report.dimension_candidates:
        st.write({"nome": dimension.human_readable_name,
                  "business_identifier": dimension.business_identifier_fields,
                  "atributos": dimension.descriptive_attributes,
                  "hierarquias": dimension.hierarchy_candidates,
                  "cardinalidade": dimension.cardinality, "papel": dimension.role.value,
                  "conformed_candidate": dimension.conformed_candidate,
                  "quality_dependencies": len(dimension.quality_dependencies),
                  "confiança": f"{dimension.confidence:.0%}"})

    counts = Counter(item.effective_modeling_role.value for item in report.field_decisions)
    st.markdown("### FIELD COVERAGE")
    st.write(f"{len(report.field_decisions)} campos analisados · " + " · ".join(
        f"{count} → {role}" for role, count in sorted(counts.items())))

    with st.expander("Editar classificação dos campos"):
        overrides = {}
        for decision in report.field_decisions:
            selected = st.selectbox(
                decision.source_field_id, [role.value for role in ModelingRole],
                index=list(ModelingRole).index(decision.effective_modeling_role),
                key=f"modeling_role_{report.report_id}_{decision.source_field_id}")
            if selected != decision.effective_modeling_role.value:
                overrides[decision.source_field_id] = ModelingRole(selected)

        accepted = st.multiselect("Manter não resolvido (aceito explicitamente)",
                                  report.unresolved_fields)
        edited_facts = deepcopy(report.fact_candidates)
        for fact in edited_facts:
            st.markdown(f"**Editar fato: {fact.human_readable_name}**")
            fact.name = st.text_input("Nome do fato", fact.name,
                                      key=f"fact_name_{fact.fact_candidate_id}")
            fact.fact_type = FactType(st.selectbox(
                "Tipo do fato", [item.value for item in FactType],
                index=list(FactType).index(fact.fact_type),
                key=f"fact_type_{fact.fact_candidate_id}"))
            fact.measure_candidates = st.multiselect(
                "Medidas", [m.source_field_id for m in report.measure_candidates],
                default=fact.measure_candidates, key=f"fact_measures_{fact.fact_candidate_id}")
            fact.foreign_dimension_candidates = st.multiselect(
                "Dimensões relacionadas", [d.dimension_candidate_id for d in report.dimension_candidates],
                default=fact.foreign_dimension_candidates, key=f"fact_dims_{fact.fact_candidate_id}")
            fact.degenerate_dimensions = st.multiselect(
                "Identificadores degenerados", [d.source_field_id for d in report.field_decisions],
                default=fact.degenerate_dimensions, key=f"fact_degenerate_{fact.fact_candidate_id}")

        edited_dimensions = deepcopy(report.dimension_candidates)
        all_fields = [d.source_field_id for d in report.field_decisions]
        for dimension in edited_dimensions:
            st.markdown(f"**Editar dimensão: {dimension.human_readable_name}**")
            dimension.name = st.text_input(
                "Nome da dimensão", dimension.name,
                key=f"dim_name_{dimension.dimension_candidate_id}")
            dimension.role = DimensionRole(st.selectbox(
                "Papel dimensional", [item.value for item in DimensionRole],
                index=list(DimensionRole).index(dimension.role),
                key=f"dim_role_{dimension.dimension_candidate_id}"))
            dimension.business_identifier_fields = st.multiselect(
                "Business identifier", all_fields, default=dimension.business_identifier_fields,
                key=f"dim_bk_{dimension.dimension_candidate_id}")
            dimension.descriptive_attributes = st.multiselect(
                "Atributos associados", all_fields, default=dimension.descriptive_attributes,
                key=f"dim_attrs_{dimension.dimension_candidate_id}")

        if st.button("Confirmar proposta"):
            repository = state.get("repository")
            version = repository.next_dimensional_validation_version(report.prepared_dataset_id) if repository else 1
            validation = validate_dimensional_discovery(
                report, field_role_overrides=overrides,
                fact_candidates=edited_facts, dimension_candidates=edited_dimensions,
                accepted_unresolved_fields=accepted, version=version)
            if repository:
                repository.save_validated_dimensional_discovery(validation)
            state["current_validated_dimensional"] = validation
            st.rerun()

    st.info("Para corrigir o grão, volte à etapa Grain Validation; ele não é alterado nesta tela.")
    st.download_button("Baixar descoberta dimensional — JSON",
                       export_dimensional_discovery_json(report),
                       file_name=f"dimensional-discovery-{report.prepared_dataset_id}-v{report.version}.json",
                       mime="application/json")
    validation = state.get("current_validated_dimensional")
    if validation:
        st.success(validation.status.value)
        st.download_button("Baixar proposta validada — JSON",
                           export_validated_dimensional_json(validation),
                           file_name=f"validated-dimensional-{validation.prepared_dataset_id}-v{validation.version}.json",
                           mime="application/json")
