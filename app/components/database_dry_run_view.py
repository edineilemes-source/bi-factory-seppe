"""Streamlit surface for isolated PostgreSQL database dry runs."""
import os
from collections.abc import MutableMapping
from typing import Any
import streamlit as st

from core.database_dry_run.adapters import PostgreSQLLocalAdapter
from core.database_dry_run.engine import execute_database_dry_run
from core.database_dry_run.export import export_database_dry_run, export_database_reconciliation, export_database_validation_report
from core.database_dry_run.models import DatabaseDryRunConfig


def run_database_dry_run(state: MutableMapping[str,Any]):
    required=(state.get("current_physical_schema_plan"),state.get("current_ddl_artifact"),
              state.get("current_validated_etl_plan"),state.get("current_transformation_run"))
    if not all(required): raise ValueError("Physical Schema, DDL, ETL Plan e Transformation Run são obrigatórios.")
    config=DatabaseDryRunConfig(host=os.getenv("PGHOST","localhost"),port=int(os.getenv("PGPORT","5432")),
        database=os.getenv("PGDATABASE","postgres"),user=os.getenv("PGUSER","postgres"),password_env="PGPASSWORD")
    result=execute_database_dry_run(*required,config=config,adapter=PostgreSQLLocalAdapter(config))
    if repository:=state.get("repository"): repository.save_database_dry_run(result)
    state["current_database_dry_run"]=result
    return result


def render_database_dry_run(state: MutableMapping[str,Any]):
    run=state.get("current_transformation_run")
    if not run or not run.ready_for_database_dry_run: return
    st.markdown("## POSTGRESQL DATABASE DRY RUN")
    st.caption("Target: Local PostgreSQL / Test. Somente schemas dryrun_* são aceitos.")
    if st.button("Executar Database Dry Run"):
        run_database_dry_run(state); st.rerun()
    result=state.get("current_database_dry_run")
    if not result: return
    st.write("Schema",result.test_schema); st.write("DDL","PASS" if result.ddl_result.success else result.status.value)
    st.write("Dimensions loaded",sum(x.loaded_rows for x in result.dimension_load_results))
    st.write("Facts loaded",sum(x.loaded_rows for x in result.fact_load_results)); st.write("Bridges loaded",sum(x.loaded_rows for x in result.bridge_load_results))
    report=result.validation_results
    if report:
        st.write("PK",report.pk_validation.status); st.write("FK",report.fk_validation.status)
        st.write("Roundtrip",report.type_roundtrip.status); st.write("Reconciliation",report.reconciliation.status)
        st.write("Idempotency",report.idempotency.status); st.write("Restartability",report.restartability.status)
    st.success("READY FOR CONTROLLED DEPLOYMENT: YES") if result.ready_for_controlled_deployment else st.warning("READY FOR CONTROLLED DEPLOYMENT: NO")
    st.download_button("Baixar Dry Run Report JSON",export_database_dry_run(result),file_name=f"database-dry-run-{result.dry_run_id}.json")
    st.download_button("Baixar Database Validation Report JSON",export_database_validation_report(result),file_name=f"database-validation-{result.dry_run_id}.json")
    st.download_button("Baixar Database Reconciliation JSON",export_database_reconciliation(result),file_name=f"database-reconciliation-{result.dry_run_id}.json")
