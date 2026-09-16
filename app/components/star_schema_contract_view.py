"""Review UI for a logical Star Schema Contract; emits JSON, never SQL."""

from copy import deepcopy
from collections.abc import MutableMapping
from typing import Any

import streamlit as st

from core.star.engine import build_star_schema_contract
from core.star.export import (
    export_star_schema_contract_json, export_validated_star_schema_json, star_schema_mermaid,
)
from core.star.models import Cardinality, SCDStrategyContract, SCDType
from core.star.validation import validate_star_schema_contract


def run_star_schema_contract(state: MutableMapping[str, Any]):
    dataset = state.get("current_prepared_dataset")
    grain = state.get("current_grain_definition")
    dimensional = state.get("current_validated_dimensional")
    if dataset is None or grain is None or dimensional is None:
        raise ValueError("Effective Dimensional Discovery validada é obrigatória.")
    repository = state.get("repository")
    version = repository.next_star_schema_report_version(dataset.prepared_dataset_id) if repository else 1
    report = build_star_schema_contract(dataset, grain, dimensional, version=version)
    if repository:
        repository.save_star_schema_contract_report(report)
    state["current_star_schema_report"] = report
    return report


def render_star_schema_contract(state: MutableMapping[str, Any]) -> None:
    if state.get("current_validated_dimensional") is None:
        return
    st.markdown("## STAR SCHEMA CONTRACT")
    st.caption("Contrato lógico sujeito a confirmação humana; nenhum SQL ou objeto físico é criado.")
    report = state.get("current_star_schema_report")
    if st.button("Regerar contrato lógico" if report else "Gerar Star Schema Contract"):
        try:
            run_star_schema_contract(state)
        except ValueError as error:
            st.error(str(error))
        else:
            st.rerun()
    if report is None:
        return
    contract = report.contract
    st.write("Fatos", [item.logical_name for item in contract.fact_tables])
    st.write("Dimensões", [item.logical_name for item in contract.dimension_tables])
    st.write("Relacionamentos", len(contract.relationships))
    st.write("Medidas", sum(len(item.measures) for item in contract.fact_tables))
    st.write("Surrogate Keys", [item.surrogate_key_plan.name for item in contract.dimension_tables])
    for warning in report.warnings:
        (st.error if warning.blocker else st.warning)(f"{warning.warning_type.value}: {warning.message}")
    with st.expander("Visualização lógica"):
        st.code(star_schema_mermaid(report), language="mermaid")
    with st.expander("Editar e validar contrato"):
        edited = deepcopy(contract)
        scd_overrides = {}
        for fact in edited.fact_tables:
            fact.logical_name = st.text_input("Nome lógico do fato", fact.logical_name,
                                              key=f"star_fact_{fact.fact_id}")
        all_fields = [field.source_field_id for field in
                      state["current_validated_dimensional"].field_decisions]
        for dimension in edited.dimension_tables:
            dimension.logical_name = st.text_input("Nome lógico da dimensão", dimension.logical_name,
                                                   key=f"star_dim_{dimension.dimension_id}")
            dimension.business_key_fields.fields = st.multiselect(
                "Business key", all_fields, default=dimension.business_key_fields.fields,
                key=f"star_bk_{dimension.dimension_id}")
            strategy = SCDType(st.selectbox(
                "Estratégia SCD", [item.value for item in SCDType],
                index=list(SCDType).index(dimension.scd_strategy.strategy),
                key=f"star_scd_{dimension.dimension_id}"))
            if strategy != dimension.scd_strategy.strategy:
                scd_overrides[dimension.dimension_id] = SCDStrategyContract(
                    dimension_id=dimension.dimension_id, strategy=strategy,
                    tracked_attributes=dimension.attributes,
                    effective_from_field_plan="effective_from" if strategy == SCDType.TYPE_2 else None,
                    effective_to_field_plan="effective_to" if strategy == SCDType.TYPE_2 else None,
                    current_flag_plan="is_current" if strategy == SCDType.TYPE_2 else None,
                    reason="Estratégia editada pelo usuário.", requires_validation=False)
        for relationship in edited.relationships:
            relationship.cardinality = Cardinality(st.selectbox(
                f"Cardinalidade {relationship.relationship_id}", [item.value for item in Cardinality],
                index=list(Cardinality).index(relationship.cardinality),
                key=f"star_rel_{relationship.relationship_id}"))
        if st.button("Confirmar contrato"):
            repository = state.get("repository")
            version = repository.next_star_schema_validation_version(contract.prepared_dataset_id) if repository else 1
            try:
                validation = validate_star_schema_contract(
                    report, contract=edited, scd_overrides=scd_overrides, version=version)
                if repository:
                    repository.save_validated_star_schema_contract(validation)
            except ValueError as error:
                st.error(str(error))
            else:
                state["current_validated_star_schema"] = validation
                st.rerun()
    st.info("Para revisar classificações, volte à Descoberta Dimensional.")
    st.download_button("Baixar Star Schema Contract — JSON", export_star_schema_contract_json(report),
                       file_name=f"star-schema-contract-v{report.version}.json", mime="application/json")
    validation = state.get("current_validated_star_schema")
    if validation:
        st.success(validation.readiness.value)
        st.download_button("Baixar Star Schema Contract validado — JSON",
                           export_validated_star_schema_json(validation),
                           file_name=f"validated-star-schema-v{validation.version}.json",
                           mime="application/json")
