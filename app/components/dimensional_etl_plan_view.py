"""Review UI for declarative ETL plans; never executes a load."""

from collections.abc import MutableMapping
from typing import Any

import streamlit as st

from core.etl.export import export_etl_mapping_csv, export_etl_plan_json, export_execution_order_json
from core.etl.models import IncrementalLoadStrategy, RejectionAction
from core.etl.planner import ETLPlanningConfig, build_dimensional_etl_plan
from core.etl.validation import validate_dimensional_etl_plan


def run_dimensional_etl_plan(state: MutableMapping[str, Any], *, config: ETLPlanningConfig | None = None):
    dataset = state.get("current_prepared_dataset")
    star_validation = state.get("current_validated_star_schema")
    physical = state.get("current_physical_schema_plan")
    artifact = state.get("current_ddl_artifact")
    if not all((dataset, star_validation, physical, artifact)):
        raise ValueError("Prepared Dataset, Effective Star Contract e Effective Physical Schema são obrigatórios.")
    repository = state.get("repository")
    version = repository.next_etl_plan_version(physical.physical_schema_plan_id) if repository else 1
    plan = build_dimensional_etl_plan(dataset, star_validation.contract, physical, artifact,
        grain=state.get("current_grain_definition"), quality_report=state.get("current_quality_report"),
        config=config, version=version)
    if repository: repository.save_dimensional_etl_plan(plan)
    state["current_etl_plan"] = plan
    state["current_validated_etl_plan"] = None
    return plan


def render_dimensional_etl_plan(state: MutableMapping[str, Any]) -> None:
    artifact = state.get("current_ddl_artifact")
    if not artifact or not artifact.ready_for_dimensional_etl:
        return
    st.markdown("## DIMENSIONAL ETL PLAN")
    st.caption("Plano declarativo. Nenhuma dimensão, fato ou bridge será carregada.")
    with st.expander("Editar política do plano"):
        unknown = st.checkbox("Permitir unknown member para lookup opcional", value=True)
        rejection = RejectionAction(st.selectbox("Política de rejeição", [x.value for x in RejectionAction]))
        incremental = IncrementalLoadStrategy(st.selectbox("Estratégia incremental", [x.value for x in IncrementalLoadStrategy],
                                                           index=list(IncrementalLoadStrategy).index(IncrementalLoadStrategy.UNKNOWN)))
    plan = state.get("current_etl_plan")
    if st.button("Regenerar ETL Plan" if plan else "Gerar ETL Plan"):
        try:
            run_dimensional_etl_plan(state, config=ETLPlanningConfig(
                unknown_member_enabled=unknown, rejection_action=rejection,
                incremental_strategy=incremental))
        except ValueError as error: st.error(str(error))
        else: st.rerun()
    if not plan: return
    st.write("Status", plan.status.value)
    st.write({"Dimensions": len(plan.dimension_load_plans), "Facts": len(plan.fact_load_plans),
              "Bridges": len(plan.bridge_load_plans), "Mappings": len(plan.field_mappings),
              "Surrogate lookups": len(plan.surrogate_key_resolution_plans),
              "Target coverage": f"{plan.target_coverage_percentage:.2f}%"})
    st.write("Execution Order", plan.execution_order)
    st.write("SCD", [item.model_dump(mode="json") for item in plan.scd_plans])
    st.write("Unknown Members", [item.model_dump(mode="json") for item in plan.unknown_member_plans])
    st.write("Rejections", plan.rejection_policy.model_dump(mode="json"))
    st.write("Reconciliation", plan.reconciliation_plan.model_dump(mode="json"))
    for blocker in plan.blockers: st.error(blocker)
    for warning in plan.warnings: st.warning(warning)
    downloads = st.columns(3)
    downloads[0].download_button("Baixar ETL Plan — JSON", export_etl_plan_json(plan),
                                 file_name=f"etl-plan-v{plan.version}.json", mime="application/json")
    downloads[1].download_button("Baixar ETL Mapping — CSV", export_etl_mapping_csv(plan),
                                 file_name=f"etl-mapping-v{plan.version}.csv", mime="text/csv")
    downloads[2].download_button("Baixar Execution Order — JSON", export_execution_order_json(plan),
                                 file_name=f"etl-order-v{plan.version}.json", mime="application/json")
    if st.button("Validar ETL Plan", disabled=bool(state.get("current_validated_etl_plan"))):
        repository = state.get("repository")
        version = repository.next_etl_validation_version(plan.prepared_dataset_id) if repository else 1
        try:
            validation = validate_dimensional_etl_plan(plan, version=version)
            if repository: repository.save_validated_dimensional_etl_plan(validation)
        except ValueError as error: st.error(str(error))
        else:
            state["current_validated_etl_plan"] = validation
            st.rerun()
    if state.get("current_validated_etl_plan"): st.success("EFFECTIVE ETL PLAN")
    st.info("Grain não é editável aqui. Para alterá-lo, volte à Grain Validation; para modelagem, volte ao Star Schema.")
