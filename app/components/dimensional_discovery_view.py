"""Human-in-the-loop dimensional discovery UI; never emits physical schema."""

from collections import Counter
from copy import deepcopy
from collections.abc import MutableMapping
from typing import Any

import streamlit as st

from core.dimensional.discovery import discover_dimensions
from core.dimensional.export import export_dimensional_discovery_json, export_validated_dimensional_json
from core.dimensional.models import DimensionRole, FactType, ModelingRole
from core.dimensional.validation import validate_dimensional_discovery


def run_dimensional_discovery(state: MutableMapping[str, Any]):
    dataset, grain = state.get("current_prepared_dataset"), state.get("current_grain_definition")
    grain_report = state.get("current_grain_report")
    if dataset is None or grain is None or grain_report is None:
        raise ValueError("Prepared Dataset e Effective Grain validado são obrigatórios.")
    repository = state.get("repository")
    version = repository.next_dimensional_report_version(dataset.prepared_dataset_id) if repository else 1
    report = discover_dimensions(dataset, grain, grain_report, version=version)
    if repository:
        repository.save_dimensional_discovery_report(report)
    state["current_dimensional_report"] = report
    return report


def render_dimensional_discovery(state: MutableMapping[str, Any]) -> None:
    grain = state.get("current_grain_definition")
    if grain is None:
        return
    st.markdown("## DESCOBERTA DIMENSIONAL")
    st.caption("Proposta explicável; nenhuma tabela, FK, DDL ou ETL será gerada nesta etapa.")
    cols = st.columns(5)
    cols[0].metric("Processo", grain.effective_process or "Não definido")
    cols[1].metric("Evento", grain.effective_event or "Não definido")
    cols[2].metric("Grão validado", grain.effective_grain_description)
    dataset = state.get("current_prepared_dataset")
    cols[3].metric("Prepared Dataset", dataset.prepared_dataset_id[:12] if dataset else "-")
    cols[4].metric("Quality Gate", dataset.status.value if dataset else "-")
    report = state.get("current_dimensional_report")
    if st.button("Redescobrir fatos e dimensões" if report else "Descobrir fatos e dimensões"):
        try:
            run_dimensional_discovery(state)
        except ValueError as error:
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
            selected = st.selectbox(decision.source_field_id, [role.value for role in ModelingRole],
                                    index=list(ModelingRole).index(decision.effective_modeling_role),
                                    key=f"modeling_role_{report.report_id}_{decision.source_field_id}")
            if selected != decision.effective_modeling_role.value:
                overrides[decision.source_field_id] = ModelingRole(selected)
        accepted = st.multiselect("Manter não resolvido (aceito explicitamente)", report.unresolved_fields)
        edited_facts = deepcopy(report.fact_candidates)
        for fact in edited_facts:
            st.markdown(f"**Editar fato: {fact.human_readable_name}**")
            fact.name = st.text_input("Nome do fato", fact.name, key=f"fact_name_{fact.fact_candidate_id}")
            fact.fact_type = FactType(st.selectbox(
                "Tipo do fato", [item.value for item in FactType],
                index=list(FactType).index(fact.fact_type), key=f"fact_type_{fact.fact_candidate_id}"))
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
            dimension.name = st.text_input("Nome da dimensão", dimension.name,
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
    st.download_button("Baixar descoberta dimensional — JSON", export_dimensional_discovery_json(report),
                       file_name=f"dimensional-discovery-{report.prepared_dataset_id}-v{report.version}.json",
                       mime="application/json")
    validation = state.get("current_validated_dimensional")
    if validation:
        st.success(validation.status.value)
        st.download_button("Baixar proposta validada — JSON", export_validated_dimensional_json(validation),
                           file_name=f"validated-dimensional-{validation.prepared_dataset_id}-v{validation.version}.json",
                           mime="application/json")
