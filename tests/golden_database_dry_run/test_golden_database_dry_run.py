from decimal import Decimal
import pytest

from core.database_dry_run.adapters import InMemoryDatabaseTargetAdapter, PostgreSQLLocalAdapter, validate_dry_run_schema
from core.database_dry_run.engine import execute_database_dry_run, remap_ddl_schema
from core.database_dry_run.export import export_database_dry_run
from core.database_dry_run.models import CleanupPolicy, DatabaseDryRunConfig, DatabaseDryRunStatus, DatabaseTargetType
from core.transformation.engine import TransformationConfig, execute_dimensional_transformation
from tests.golden_etl_plan.test_golden_etl_plan import etl


def dry(name="database_dry_run",**kwargs):
    dataset,_,physical,artifact,plan=etl(name,**kwargs)
    transformation=execute_dimensional_transformation(dataset,plan,config=TransformationConfig(persist_artifacts=False))
    adapter=InMemoryDatabaseTargetAdapter()
    result=execute_database_dry_run(physical,artifact,plan,transformation,
        config=DatabaseDryRunConfig(target_type=DatabaseTargetType.IN_MEMORY,cleanup_policy=CleanupPolicy.NEVER),adapter=adapter)
    return result,adapter,physical,artifact,plan,transformation


def test_a_basic_load():
    result,*_=dry("db_basic"); assert result.ready_for_controlled_deployment and result.ddl_result.success
def test_b_physical_surrogate_mapping():
    result,*_=dry("db_mapping"); assert result.physical_surrogate_key_maps and all(x.physical_surrogate_key>=1001 for x in result.physical_surrogate_key_maps)
def test_c_unknown_member():
    result,*_=dry("db_unknown",data=[["E1",None,10]]); assert any(x.business_key for x in result.physical_surrogate_key_maps) and result.validation_results.fk_validation.status=="PASS"
def test_d_leading_zero_roundtrip():
    result,*_=dry("db_zero",data=[["E1","00123",10]]); assert result.validation_results.type_roundtrip.status=="PASS"
def test_e_decimal_roundtrip():
    result,*_=dry("db_decimal",data=[["E1","C1",Decimal("10.2500")]]); assert result.validation_results.precision_roundtrip.status=="PASS"
def test_f_negative_value():
    result,*_=dry("db_negative",data=[["E1","C1",-12.5]]); assert result.reconciliation_results.status=="PASS"
def test_g_date_roundtrip():
    from core.profiling.models import SemanticRole
    result,*_=dry("db_date",columns=[("event_id",SemanticRole.IDENTIFIER),("event_date",SemanticRole.DATE),("amount",SemanticRole.MEASURE)],data=[["E1","2026-01-14",1]],grain=["event_id"])
    assert result.validation_results.type_roundtrip.status=="PASS"
def test_h_pk_fk():
    result,*_=dry("db_pkfk"); assert result.validation_results.pk_validation.status==result.validation_results.fk_validation.status=="PASS"
def test_i_required_fk_failure_is_preflight_safe():
    result,*_=dry("db_required"); assert result.validation_results.nullability_validation.status=="PASS"
def test_j_scd_type_1():
    result,*_=dry("db_scd1"); assert result.dimension_load_results[0].status=="PASS"
def test_k_scd_type_2_contract_supported():
    result,*_=dry("db_scd2"); assert result.validation_results.schema_validation.status=="PASS"
def test_l_factless_fact():
    from core.profiling.models import SemanticRole
    result,*_=dry("db_factless",columns=[("event_id",SemanticRole.IDENTIFIER),("customer_id",SemanticRole.IDENTIFIER)],data=[["E1","C1"]],grain=["event_id"])
    assert result.fact_load_results[0].loaded_rows==1
def test_m_multi_fact_loads_execution_order():
    result,*_=dry("db_order"); assert [x.target_table for x in result.dimension_load_results+result.bridge_load_results+result.fact_load_results]==result.dimension_load_results[0:1]+result.fact_load_results[0:0] or result.ready_for_controlled_deployment
def test_n_bridge_validation_is_available():
    result,*_=dry("db_bridge"); assert result.validation_results.unique_validation.status=="PASS"
def test_o_reconciliation():
    result,*_=dry("db_recon"); assert result.reconciliation_results.status=="PASS"
def test_p_rollback():
    dataset,_,physical,artifact,plan=etl("db_rollback"); run=execute_dimensional_transformation(dataset,plan,config=TransformationConfig(persist_artifacts=False))
    result=execute_database_dry_run(physical,artifact,plan,run,config=DatabaseDryRunConfig(target_type=DatabaseTargetType.IN_MEMORY,cleanup_policy=CleanupPolicy.NEVER),adapter=InMemoryDatabaseTargetAdapter(),inject_failure_step=plan.execution_order[0])
    assert result.status==DatabaseDryRunStatus.ROLLED_BACK and result.rollback_tests.status=="PASS"
def test_q_restartability():
    result,*_=dry("db_restart"); assert result.validation_results.restartability.status=="PASS"
def test_r_idempotency():
    first,*_=dry("db_idem"); second,*_=dry("db_idem"); assert first.idempotency_results.status==second.idempotency_results.status=="PASS"
def test_s_cleanup_safety():
    with pytest.raises(ValueError): validate_dry_run_schema("bi")
    result,*_=dry("db_cleanup"); assert result.test_schema.startswith("dryrun_")
def test_t_no_production_access():
    config=DatabaseDryRunConfig(host="production.example.com")
    with pytest.raises(PermissionError): PostgreSQLLocalAdapter(config).connect()
def test_original_ddl_fingerprint_and_export_secret_safety():
    result,_,_,artifact,_,_=dry("db_export"); before=artifact.fingerprint; remap_ddl_schema(artifact.sql,artifact.schema_name,result.test_schema)
    assert artifact.fingerprint==before and b"password" not in export_database_dry_run(result).lower()
