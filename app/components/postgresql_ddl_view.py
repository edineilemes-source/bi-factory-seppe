"""PostgreSQL DDL preview, validation, and persisted exports."""

from collections.abc import MutableMapping
from typing import Any

import streamlit as st

from core.ddl.export import export_ddl_report_json, export_physical_schema_plan_json, export_postgresql_sql
from core.ddl.generator import DDLGeneratorConfig, generate_postgresql_ddl
from core.ddl.models import DDLMode
from core.ddl.models import PhysicalSchemaStatus


def run_postgresql_ddl(state: MutableMapping[str, Any], *, schema: str = "bi",
                       mode: DDLMode = DDLMode.STRICT_CREATE):
    validation = state.get("current_validated_star_schema")
    if validation is None:
        raise ValueError("Effective Star Schema Contract READY_FOR_DDL é obrigatório.")
    repository = state.get("repository")
    version = repository.next_ddl_version(validation.contract.contract_id) if repository else 1
    plan, artifact = generate_postgresql_ddl(
        validation, config=DDLGeneratorConfig(target_schema=schema, ddl_mode=mode), version=version)
    if repository:
        repository.save_physical_schema_plan(plan)
        repository.save_postgresql_ddl_artifact(artifact)
    state["current_physical_schema_plan"] = plan
    state["current_ddl_artifact"] = artifact
    return plan, artifact


def render_postgresql_ddl(state: MutableMapping[str, Any]) -> None:
    if state.get("current_validated_star_schema") is None:
        return
    st.markdown("## POSTGRESQL DDL")
    st.caption("Geração e validação local do artefato; nenhum SQL é executado.")
    schema = st.text_input("Schema PostgreSQL", "bi", key="ddl_target_schema")
    mode = DDLMode(st.selectbox("DDL mode", [item.value for item in DDLMode], key="ddl_mode"))
    plan = state.get("current_physical_schema_plan")
    artifact = state.get("current_ddl_artifact")
    if st.button("Regenerar" if artifact else "Gerar DDL PostgreSQL"):
        try:
            run_postgresql_ddl(state, schema=schema, mode=mode)
        except ValueError as error:
            st.error(str(error))
        else:
            st.rerun()
    if plan is None or artifact is None:
        return
    dimensions = sum(table.table_type == "DIMENSION" for table in plan.tables)
    facts = sum(table.table_type == "FACT" for table in plan.tables)
    bridges = sum(table.table_type == "BRIDGE" for table in plan.tables)
    st.write("Target", plan.target_platform)
    st.write("Schema", plan.target_schema)
    st.write("Versão", artifact.version)
    st.write("Fingerprint", artifact.fingerprint)
    st.write({"DIMENSIONS": dimensions, "FACTS": facts, "BRIDGES": bridges,
              "COLUMNS": len(plan.columns), "PRIMARY KEYS": len(plan.primary_keys),
              "FOREIGN KEYS": len(plan.foreign_keys), "INDEXES": len(plan.indexes),
              "CONSTRAINTS": artifact.constraint_count, "WARNINGS": len(artifact.warnings)})
    for warning in artifact.warnings:
        st.warning(warning)
    st.code("\n".join(artifact.sql.splitlines()[:200]), language="sql")
    if len(artifact.sql.splitlines()) > 200:
        st.caption("Preview limitado a 200 linhas. O download contém o SQL completo.")
    downloads = st.columns(3)
    downloads[0].download_button("Baixar DDL PostgreSQL (.sql)", export_postgresql_sql(artifact),
                                 file_name=f"postgresql-ddl-v{artifact.version}.sql", mime="text/sql")
    downloads[1].download_button("Baixar Physical Schema Plan (.json)",
                                 export_physical_schema_plan_json(plan),
                                 file_name=f"physical-schema-plan-v{plan.version}.json", mime="application/json")
    downloads[2].download_button("Baixar DDL Report (.json)", export_ddl_report_json(artifact),
                                 file_name=f"postgresql-ddl-report-v{artifact.version}.json", mime="application/json")
    if st.button("Validar DDL", disabled=artifact.human_validated):
        repository = state.get("repository")
        artifact = (repository.validate_postgresql_ddl_artifact(artifact) if repository
                    else artifact.model_copy(update={"human_validated": True,
                                                     "ready_for_dimensional_etl": True}))
        state["current_ddl_artifact"] = artifact
        plan.lifecycle_status = PhysicalSchemaStatus.EFFECTIVE
        state["current_physical_schema_plan"] = plan
        st.rerun()
    if artifact.ready_for_dimensional_etl:
        st.success("READY_FOR_DIMENSIONAL_ETL")
    st.info("Para revisar decisões conceituais, volte ao Star Schema Contract.")
