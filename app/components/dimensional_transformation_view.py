"""Local dimensional transformation execution and artifact downloads."""

from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

import streamlit as st

from app.dataframe_compat import arrow_compatible_dataframe

from core.transformation.engine import TransformationConfig, execute_dimensional_transformation
from core.transformation.export import (
    export_reconciliation_json, export_transformation_run_report, read_staged_artifact,
)


def run_dimensional_transformation(state: MutableMapping[str, Any]):
    dataset = state.get("current_prepared_dataset")
    validation = state.get("current_validated_etl_plan")
    if not dataset or not validation:
        raise ValueError("Effective ETL Plan validado é obrigatório.")
    run = execute_dimensional_transformation(dataset, validation,
        config=TransformationConfig(artifact_root=Path("artifacts/staged"), persist_artifacts=True))
    repository = state.get("repository")
    if repository: repository.save_dimensional_transformation_run(run)
    state["current_transformation_run"] = run
    return run


def render_dimensional_transformation(state: MutableMapping[str, Any]) -> None:
    if not state.get("current_validated_etl_plan"): return
    st.markdown("## DIMENSIONAL TRANSFORMATION")
    st.caption("Execução local de staging; nenhuma conexão ou operação de banco é realizada.")
    run = state.get("current_transformation_run")
    if st.button("Executar transformação dimensional"):
        try: run_dimensional_transformation(state)
        except (ValueError, OSError) as error: st.error(str(error))
        else: st.rerun()
    if not run: return
    st.write("Run ID", run.run_id)
    st.write("Prepared Dataset", run.prepared_dataset_id)
    st.write("ETL Plan", run.etl_plan_id)
    st.write("Status", run.status.value)
    st.write("Quality Gate", run.readiness.value)
    st.write("Execution Steps", [{"step": x.step_id, "status": x.status.value} for x in run.execution_steps])
    st.write("Dimensions", [{"table": x.target_table, "rows": x.row_count,
                              "new_members": x.inserted_member_count, "warnings": x.warnings}
                             for x in run.dimension_results])
    st.write("Facts", [{"table": x.target_table, "source": x.source_row_count,
                         "staged": x.staged_row_count, "rejected": x.rejected_row_count,
                         "unknown": x.unknown_member_usage_count} for x in run.fact_results])
    st.write("Reconciliation", run.reconciliation_report.status)
    for result in [*run.dimension_results, *run.fact_results, *run.bridge_results]:
        if result.artifact_path:
            st.download_button(f"Baixar {result.target_table}", read_staged_artifact(result.artifact_path),
                               file_name=Path(result.artifact_path).name, mime="text/csv",
                               key=f"download_{run.run_id}_{result.target_table}")
        with st.expander(f"Preview {result.target_table}"):
            st.dataframe(arrow_compatible_dataframe(result.staged_rows[:100]))
    st.download_button("Baixar Reconciliação", export_reconciliation_json(run),
                       file_name=f"reconciliation-{run.run_id}.json", mime="application/json")
    st.download_button("Baixar Transformation Run Report", export_transformation_run_report(run),
                       file_name=f"transformation-run-{run.run_id}.json", mime="application/json")
    if run.ready_for_database_dry_run: st.success("READY_FOR_DATABASE_DRY_RUN")
