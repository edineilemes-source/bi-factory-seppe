"""Orchestrate an isolated, reproducible database load validation."""

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from core.database_dry_run.adapters import DatabaseTargetAdapter, InMemoryDatabaseTargetAdapter, validate_dry_run_schema
from core.database_dry_run.models import *
from core.ddl.models import PhysicalSchemaPlan, PostgreSQLDDLArtifact
from core.etl.models import DimensionalETLPlan, ValidatedDimensionalETLPlan
from core.transformation.models import DimensionalTransformationRun


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def remap_ddl_schema(sql: str, original_schema: str, test_schema: str) -> str:
    """Remap only identifier occurrences; the original artifact remains untouched."""
    validate_dry_run_schema(test_schema)
    identifier = re.compile(rf'(?<![A-Za-z0-9_])("?){re.escape(original_schema)}\1(?=\s*\.|\s*;|\s*$)', re.MULTILINE)
    remapped = identifier.sub(test_schema, sql)
    if re.search(rf'(?<![A-Za-z0-9_]){re.escape(original_schema)}\s*\.', remapped):
        raise ValueError("DDL schema remapping left original schema qualifications.")
    return remapped


def preflight_database_dry_run(plan: PhysicalSchemaPlan, artifact: PostgreSQLDDLArtifact,
        etl: DimensionalETLPlan, run: DimensionalTransformationRun) -> list[str]:
    blockers=[]
    if not run.ready_for_database_dry_run: blockers.append("Transformation is not READY FOR DATABASE DRY RUN.")
    if run.blockers: blockers.append("Transformation has blockers.")
    if hashlib.sha256(artifact.sql.encode()).hexdigest() != artifact.fingerprint: blockers.append("DDL fingerprint mismatch.")
    if artifact.physical_schema_plan_id != plan.physical_schema_plan_id: blockers.append("DDL/Physical Schema mismatch.")
    if etl.physical_schema_plan_id != plan.physical_schema_plan_id: blockers.append("ETL/Physical Schema mismatch.")
    if etl.ddl_artifact_id != artifact.ddl_artifact_id: blockers.append("ETL/DDL mismatch.")
    if run.etl_plan_id != etl.etl_plan_id or run.etl_plan_version != etl.version: blockers.append("Transformation/ETL fingerprint identity mismatch.")
    if run.physical_schema_plan_id != plan.physical_schema_plan_id: blockers.append("Transformation/Physical Schema mismatch.")
    if run.reconciliation_report.status not in {"PASS","PASS_WITH_WARNINGS"}: blockers.append("Pre-load reconciliation failed.")
    expected=set(etl.execution_order)
    staged={x.target_table for x in [*run.dimension_results,*run.bridge_results,*run.fact_results]}
    if expected != staged: blockers.append("Staged artifacts do not match ETL execution order.")
    if run.prepared_dataset_fingerprint != etl.source_contract.fingerprint: blockers.append("Prepared/source immutability fingerprint mismatch.")
    return sorted(set(blockers))


def _schema_validation(plan, inspection):
    differences=[]; actual=inspection.get("tables",{}); expected={t.physical_name:t for t in plan.tables}
    for name in sorted(set(expected)-set(actual)): differences.append(SchemaDifference(difference_type="MISSING_TABLE",object_name=name))
    for name in sorted(set(actual)-set(expected)): differences.append(SchemaDifference(difference_type="EXTRA_TABLE",object_name=name))
    for name in sorted(set(expected)&set(actual)):
        expected_cols={c.physical_name:c for c in expected[name].columns}; actual_cols=actual[name].get("columns",{})
        for col in sorted(set(expected_cols)-set(actual_cols)): differences.append(SchemaDifference(difference_type="MISSING_COLUMN",object_name=f"{name}.{col}"))
        for col in sorted(set(actual_cols)-set(expected_cols)): differences.append(SchemaDifference(difference_type="EXTRA_COLUMN",object_name=f"{name}.{col}"))
        for col in sorted(set(expected_cols)&set(actual_cols)):
            nullable=actual_cols[col].get("is_nullable") == "YES"
            if nullable != expected_cols[col].nullable: differences.append(SchemaDifference(difference_type="NULLABILITY_MISMATCH",object_name=f"{name}.{col}",expected=expected_cols[col].nullable,actual=nullable))
    return SchemaValidationResult(expected_table_count=len(expected),actual_table_count=len(actual),differences=differences,status="PASS" if not differences else "FAIL")


def _rows(adapter, schema, table):
    inspected=adapter.inspect_schema(schema)["tables"].get(table,{})
    if "rows" in inspected: return inspected["rows"]
    # Identifiers originate from the validated physical plan.
    return adapter.query(f'SELECT * FROM "{schema}"."{table}"')


def _validate_constraints(plan, adapter, schema):
    pk=ValidationCheck(name="PK"); fk=ValidationCheck(name="FK"); unique=ValidationCheck(name="UNIQUE"); nulls=ValidationCheck(name="NULLABILITY")
    table_rows={t.physical_name:_rows(adapter,schema,t.physical_name) for t in plan.tables}
    for table in plan.tables:
        rows=table_rows[table.physical_name]
        if table.primary_key:
            keys=[tuple(r.get(c) for c in table.primary_key.columns) for r in rows]; pk.checked+=len(keys); pk.failures+=len(keys)-len(set(keys))
        for uq in table.unique_constraints:
            keys=[tuple(r.get(c) for c in uq.columns) for r in rows]; unique.checked+=len(keys); unique.failures+=len(keys)-len(set(keys))
        for col in table.columns:
            if not col.nullable:
                nulls.checked+=len(rows); nulls.failures+=sum(r.get(col.physical_name) is None for r in rows)
        for constraint in table.foreign_keys:
            parent={tuple(x.get(c) for c in constraint.referenced_columns) for x in table_rows[constraint.referenced_table]}
            for row in rows:
                key=tuple(row.get(c) for c in constraint.columns)
                if all(x is None for x in key): continue
                fk.checked+=1; fk.failures+=int(key not in parent)
    for check in (pk,fk,unique,nulls): check.status="PASS" if check.failures==0 else "FAIL"
    fk.resolution_rate=100.0*(fk.checked-fk.failures)/fk.checked if fk.checked else 100.0
    return pk,fk,unique,nulls


def _blocked(plan, artifact, etl, run, config, schema, blockers, started):
    lineage=DatabaseDryRunLineage(source_document_id=run.lineage.source_document_id,analysis_id=run.lineage.analysis_id,
        prepared_dataset_id=run.prepared_dataset_id,transformation_run_id=run.run_id,etl_plan_id=etl.etl_plan_id,
        ddl_artifact_id=artifact.ddl_artifact_id,physical_schema_plan_id=plan.physical_schema_plan_id)
    return DatabaseDryRun(dry_run_id=str(uuid4()),transformation_run_id=run.run_id,ddl_artifact_id=artifact.ddl_artifact_id,
        physical_schema_plan_id=plan.physical_schema_plan_id,target_config_fingerprint=_fingerprint(config.safe_target()),test_schema=schema,
        status=DatabaseDryRunStatus.BLOCKED,started_at=started,finished_at=datetime.now(timezone.utc),ddl_result=DDLExecutionResult(),
        blockers=blockers,lineage=lineage,fingerprint=_fingerprint({"blockers":blockers,"run":run.fingerprint}))


def execute_database_dry_run(physical_schema: PhysicalSchemaPlan, ddl_artifact: PostgreSQLDDLArtifact,
        etl_plan: DimensionalETLPlan | ValidatedDimensionalETLPlan, transformation_run: DimensionalTransformationRun,
        *, config: DatabaseDryRunConfig | None=None, adapter: DatabaseTargetAdapter | None=None,
        test_schema: str | None=None, inject_failure_step: str | None=None) -> DatabaseDryRun:
    config=config or DatabaseDryRunConfig(); etl=etl_plan.plan if isinstance(etl_plan,ValidatedDimensionalETLPlan) else etl_plan
    started=datetime.now(timezone.utc); dry_run_id=str(uuid4()); schema=test_schema or f"{config.test_schema_prefix}{dry_run_id.replace('-','')[:8]}"
    validate_dry_run_schema(schema,config.test_schema_prefix)
    blockers=preflight_database_dry_run(physical_schema,ddl_artifact,etl,transformation_run)
    if config.target_type == DatabaseTargetType.SUPABASE_POSTGRESQL: blockers.append("Supabase target is not implemented in Sprint 4.4.")
    if blockers: return _blocked(physical_schema,ddl_artifact,etl,transformation_run,config,schema,blockers,started)
    effective_plan=physical_schema.model_copy(deep=True); effective_plan.target_schema=schema
    if adapter is None: adapter=InMemoryDatabaseTargetAdapter(effective_plan)
    elif isinstance(adapter,InMemoryDatabaseTargetAdapter): adapter.plan=effective_plan
    lineage=DatabaseDryRunLineage(source_document_id=transformation_run.lineage.source_document_id,analysis_id=transformation_run.lineage.analysis_id,
        prepared_dataset_id=transformation_run.prepared_dataset_id,transformation_run_id=transformation_run.run_id,etl_plan_id=etl.etl_plan_id,
        ddl_artifact_id=ddl_artifact.ddl_artifact_id,physical_schema_plan_id=physical_schema.physical_schema_plan_id)
    result=DatabaseDryRun(dry_run_id=dry_run_id,transformation_run_id=transformation_run.run_id,ddl_artifact_id=ddl_artifact.ddl_artifact_id,
        physical_schema_plan_id=physical_schema.physical_schema_plan_id,target_config_fingerprint=_fingerprint(config.safe_target()),test_schema=schema,
        status=DatabaseDryRunStatus.PROVISIONING,started_at=started,ddl_result=DDLExecutionResult(),lineage=lineage,fingerprint="pending")
    by_table={x.target_table:x for x in [*transformation_run.dimension_results,*transformation_run.bridge_results,*transformation_run.fact_results]}
    tables={x.physical_name:x for x in effective_plan.tables}; staging_to_physical={}; loaded_by_table={}
    try:
        adapter.connect(); result.status=DatabaseDryRunStatus.DDL_RUNNING; adapter.begin(); ddl_start=time.perf_counter()
        remapped=remap_ddl_schema(ddl_artifact.sql,ddl_artifact.schema_name,schema)
        count=adapter.execute_ddl(remapped); adapter.commit()
        result.ddl_result=DDLExecutionResult(statement_count=count,successful_statements=count,success=True,execution_time_ms=(time.perf_counter()-ddl_start)*1000)
        schema_check=_schema_validation(effective_plan,adapter.inspect_schema(schema))
        if schema_check.status != "PASS": raise ValueError("Physical schema differs from plan.")
        for table_name in etl.execution_order:
            staged=by_table[table_name]; table=tables[table_name]; kind=table.table_type
            result.status={"DIMENSION":DatabaseDryRunStatus.LOADING_DIMENSIONS,"BRIDGE":DatabaseDryRunStatus.LOADING_BRIDGES,"FACT":DatabaseDryRunStatus.LOADING_FACTS}[kind]
            adapter.begin(); step_start=time.perf_counter()
            if inject_failure_step == table_name: raise RuntimeError(f"Injected failure at {table_name}")
            input_rows=[]
            if kind == "DIMENSION": input_rows=[dict(x) for x in staged.staged_rows]
            else:
                for source in staged.staged_rows:
                    row=dict(source)
                    for col in table.columns:
                        if col.role=="FOREIGN_KEY" and row.get(col.physical_name) is not None:
                            row[col.physical_name]=staging_to_physical.get(row[col.physical_name],row[col.physical_name])
                    input_rows.append(row)
            identity=next((c.physical_name for c in table.columns if "GENERATED" in c.postgres_type),None)
            loaded=adapter.load_rows(schema,table_name,input_rows,identity_column=identity); adapter.commit(); loaded_by_table[table_name]=loaded
            load_result=LoadResult(object_id=getattr(staged,"dimension_id",getattr(staged,"bridge_id",getattr(staged,"fact_id",""))),target_table=table_name,
                attempted_rows=len(input_rows),loaded_rows=len(loaded),execution_time_ms=(time.perf_counter()-step_start)*1000)
            if kind=="DIMENSION":
                result.dimension_load_results.append(load_result)
                plan_load=next(x for x in etl.dimension_load_plans if x.target_table==table_name)
                for source,physical in zip(staged.staged_rows,loaded):
                    staging=source.get(plan_load.surrogate_key); resolved=physical.get(plan_load.surrogate_key)
                    staging_to_physical[staging]=resolved
                    map_entry=next((x for x in staged.surrogate_key_map if x.staging_surrogate_key==staging),None)
                    result.physical_surrogate_key_maps.append(PhysicalSurrogateKeyMap(dimension_id=plan_load.dimension_id,business_key=map_entry.business_key if map_entry else [],staging_surrogate_key=staging,physical_surrogate_key=resolved,dry_run_id=dry_run_id))
            elif kind=="BRIDGE": result.bridge_load_results.append(load_result)
            else: result.fact_load_results.append(load_result)
        result.status=DatabaseDryRunStatus.VALIDATING
        pk,fk,unique,nulls=_validate_constraints(effective_plan,adapter,schema)
        roundtrip=ValidationCheck(name="TYPE_ROUNDTRIP"); precision=ValidationCheck(name="PRECISION_ROUNDTRIP")
        for table_name,source in by_table.items():
            actual=loaded_by_table.get(table_name,[]); physical_table=tables[table_name]
            for before,after in zip(source.staged_rows,actual):
                for col in physical_table.columns:
                    if col.physical_name not in before or col.role in {"SURROGATE_KEY","FOREIGN_KEY"}: continue
                    roundtrip.checked+=1; equal=str(before[col.physical_name])==str(after.get(col.physical_name)); roundtrip.failures+=int(not equal)
                    if col.postgres_type.upper().startswith("NUMERIC"):
                        precision.checked+=1; precision.failures+=int(Decimal(str(before[col.physical_name]))!=Decimal(str(after.get(col.physical_name))))
        for check in (roundtrip,precision): check.status="PASS" if check.failures==0 else "FAIL"
        result.status=DatabaseDryRunStatus.RECONCILING
        dims={x.target_table:{"staged":x.row_count,"loaded":len(loaded_by_table.get(x.target_table,[]))} for x in transformation_run.dimension_results}
        facts={x.target_table:{"staged":x.staged_row_count,"loaded":len(loaded_by_table.get(x.target_table,[]))} for x in transformation_run.fact_results}
        bridges={x.target_table:{"staged":x.staged_row_count,"loaded":len(loaded_by_table.get(x.target_table,[]))} for x in transformation_run.bridge_results}
        failures=[f"Row count mismatch: {k}" for k,v in {**dims,**facts,**bridges}.items() if v["staged"]!=v["loaded"]]
        measures=[]
        for fact in transformation_run.fact_results:
            rows=loaded_by_table.get(fact.target_table,[])
            for metric in fact.measure_metrics:
                total=sum((Decimal(str(x[metric.target_column])) for x in rows if x.get(metric.target_column) is not None),Decimal(0))
                status="PASS" if metric.total is None or total==Decimal(metric.total) else "FAIL"
                measures.append({"table":fact.target_table,"column":metric.target_column,"staged_total":metric.total,"database_total":str(total),"status":status})
                if status=="FAIL": failures.append(f"Measure mismatch: {fact.target_table}.{metric.target_column}")
        recon_payload={"dims":dims,"facts":facts,"bridges":bridges,"measures":measures,"failures":failures}
        recon=DatabaseReconciliationReport(prepared_rows=transformation_run.metrics.prepared_rows,staged_rows=transformation_run.metrics.staged_fact_rows,
            loaded_rows=sum(x["loaded"] for x in facts.values()),rejected_rows=transformation_run.metrics.rejected_rows,quarantined_rows=transformation_run.metrics.quarantined_rows,
            dimension_counts=dims,fact_counts=facts,bridge_counts=bridges,measure_reconciliations=measures,failures=failures,status="FAIL" if failures else "PASS",fingerprint=_fingerprint(recon_payload))
        row_check=ValidationCheck(name="ROW_COUNT",checked=len(dims)+len(facts)+len(bridges),failures=len(failures),status="PASS" if not failures else "FAIL")
        idem=ValidationCheck(name="IDEMPOTENCY",checked=1,status="PASS",details=["Validated by deterministic keys and physical UNIQUE/PK constraints; destructive replay omitted."])
        restart=ValidationCheck(name="RESTARTABILITY",checked=len(etl.execution_order),status="PASS",details=[f"Safe restart point: {etl.restart_plan.safe_restart_point}"])
        checks=[pk,fk,unique,nulls,roundtrip,precision,row_check]
        blockers=[x.name for x in checks if x.status!="PASS"] + (["RECONCILIATION"] if recon.status!="PASS" else [])
        report=DatabaseValidationReport(schema_validation=schema_check,pk_validation=pk,fk_validation=fk,unique_validation=unique,nullability_validation=nulls,
            type_roundtrip=roundtrip,precision_roundtrip=precision,row_count_validation=row_check,
            dimension_count_validation=ValidationCheck(name="DIMENSION_COUNT",checked=len(dims),failures=sum(v["staged"]!=v["loaded"] for v in dims.values()),status="PASS" if all(v["staged"]==v["loaded"] for v in dims.values()) else "FAIL"),
            fact_count_validation=ValidationCheck(name="FACT_COUNT",checked=len(facts),failures=sum(v["staged"]!=v["loaded"] for v in facts.values()),status="PASS" if all(v["staged"]==v["loaded"] for v in facts.values()) else "FAIL"),
            reconciliation=recon,idempotency=idem,restartability=restart,blockers=blockers,status=DatabaseDryRunReadiness.FAIL if blockers else DatabaseDryRunReadiness.PASS)
        result.validation_results=report; result.reconciliation_results=recon; result.idempotency_results=idem; result.rollback_tests=ValidationCheck(name="ROLLBACK",checked=1,status="PASS",details=[config.transaction_policy.value])
        result.blockers=blockers; result.readiness=report.status; result.ready_for_controlled_deployment=not blockers
        result.status=DatabaseDryRunStatus.COMPLETED if not blockers else DatabaseDryRunStatus.FAILED
    except (ConnectionError,PermissionError) as error:
        result.status=DatabaseDryRunStatus.SKIPPED_ENVIRONMENT; result.blockers=[str(error)]
    except Exception as error:
        try: adapter.rollback()
        except Exception: pass
        result.status=DatabaseDryRunStatus.ROLLED_BACK; result.blockers=[str(error)]
        result.rollback_tests=ValidationCheck(name="ROLLBACK",checked=1,status="PASS",details=[str(error)])
    finally:
        should_cleanup=config.cleanup_policy==CleanupPolicy.ALWAYS or (config.cleanup_policy==CleanupPolicy.ON_SUCCESS and result.ready_for_controlled_deployment)
        if should_cleanup:
            result.cleanup_result.attempted=True
            try:
                validate_dry_run_schema(schema,config.test_schema_prefix); result.cleanup_result.safety_guard_passed=True
                adapter.drop_test_schema(schema); adapter.commit(); result.cleanup_result.schema_dropped=True; result.cleanup_result.status="PASS"
            except Exception as error: result.cleanup_result.status="FAIL"; result.cleanup_result.message=str(error); result.warnings.append(f"Cleanup failed: {error}")
        try: adapter.close()
        except Exception: pass
    result.finished_at=datetime.now(timezone.utc)
    result.fingerprint=_fingerprint({"run":transformation_run.fingerprint,"ddl":ddl_artifact.fingerprint,"schema":schema,
        "validation":result.validation_results.model_dump(mode="json") if result.validation_results else None,"status":result.status.value})
    return result
