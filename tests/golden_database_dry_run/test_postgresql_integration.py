import os
import shutil
import subprocess
import pytest
from decimal import Decimal

from core.database_dry_run.adapters import PostgreSQLLocalAdapter
from core.database_dry_run.engine import execute_database_dry_run
from core.database_dry_run.models import CleanupPolicy,DatabaseDryRunConfig
from core.transformation.engine import TransformationConfig,execute_dimensional_transformation
from tests.golden_etl_plan.test_golden_etl_plan import etl
from core.database_dry_run.models import DatabaseDryRunStatus
from core.profiling.models import SemanticRole


def _available():
    if not PostgreSQLLocalAdapter.driver_available() or not shutil.which("pg_isready"): return False
    return subprocess.run(["pg_isready","-h",os.getenv("TEST_POSTGRES_HOST","127.0.0.1"),"-p",os.getenv("TEST_POSTGRES_PORT","55432"),"-d",os.getenv("TEST_POSTGRES_DB","bi_factory_test")],capture_output=True).returncode==0


@pytest.mark.postgres_integration
@pytest.mark.skipif(not _available(),reason="SKIPPED_ENVIRONMENT: local PostgreSQL/psycopg unavailable")
def test_generated_ddl_and_load_on_local_postgresql():
    dataset,_,physical,artifact,plan=etl("postgres_physical")
    transformation=execute_dimensional_transformation(dataset,plan,config=TransformationConfig(persist_artifacts=False))
    config=DatabaseDryRunConfig(host=os.getenv("TEST_POSTGRES_HOST","127.0.0.1"),port=int(os.getenv("TEST_POSTGRES_PORT","55432")),database=os.getenv("TEST_POSTGRES_DB","bi_factory_test"),user=os.getenv("TEST_POSTGRES_USER",os.getenv("USER","codespace")),password_env="TEST_POSTGRES_PASSWORD",cleanup_policy=CleanupPolicy.ALWAYS)
    result=execute_database_dry_run(physical,artifact,plan,transformation,config=config,adapter=PostgreSQLLocalAdapter(config))
    assert result.ready_for_controlled_deployment
    assert result.cleanup_result.schema_dropped


def _physical(name, *, data=None, columns=None, grain=None, transform=None, inject_failure_step=None):
    dataset,_,physical,artifact,plan=etl(name,data=data,columns=columns,grain=grain,transform=transform)
    transformation=execute_dimensional_transformation(dataset,plan,config=TransformationConfig(persist_artifacts=False))
    config=DatabaseDryRunConfig(host=os.getenv("TEST_POSTGRES_HOST","127.0.0.1"),
        port=int(os.getenv("TEST_POSTGRES_PORT","55432")),database=os.getenv("TEST_POSTGRES_DB","bi_factory_test"),
        user=os.getenv("TEST_POSTGRES_USER",os.getenv("USER","codespace")),password_env="TEST_POSTGRES_PASSWORD",
        cleanup_policy=CleanupPolicy.ALWAYS)
    return execute_database_dry_run(physical,artifact,plan,transformation,config=config,
        adapter=PostgreSQLLocalAdapter(config),inject_failure_step=inject_failure_step),plan


@pytest.mark.postgres_integration
@pytest.mark.skipif(not _available(),reason="SKIPPED_ENVIRONMENT: local PostgreSQL/psycopg unavailable")
@pytest.mark.parametrize(("name","value"),[("pg_zero","00123"),("pg_decimal",Decimal("10.2500")),("pg_negative",Decimal("-12.50"))])
def test_real_postgresql_roundtrips(name,value):
    data=[["E1",value,Decimal("10.2500")]] if name=="pg_zero" else [["E1","C1",value]]
    result,_=_physical(name,data=data)
    assert result.validation_results.type_roundtrip.status=="PASS"
    assert result.validation_results.precision_roundtrip.status=="PASS"
    assert result.reconciliation_results.status=="PASS"


@pytest.mark.postgres_integration
@pytest.mark.skipif(not _available(),reason="SKIPPED_ENVIRONMENT: local PostgreSQL/psycopg unavailable")
def test_real_postgresql_date_and_unknown_member():
    result,_=_physical("pg_date_unknown",columns=[("event_id",SemanticRole.IDENTIFIER),
        ("event_date",SemanticRole.DATE),("amount",SemanticRole.MEASURE)],
        data=[["E1","2026-01-14",Decimal("1.00")]],grain=["event_id"])
    assert result.validation_results.type_roundtrip.status=="PASS"
    assert result.physical_surrogate_key_maps
    assert result.validation_results.fk_validation.status=="PASS"


@pytest.mark.postgres_integration
@pytest.mark.skipif(not _available(),reason="SKIPPED_ENVIRONMENT: local PostgreSQL/psycopg unavailable")
def test_real_postgresql_rollback_restart_idempotency_and_cleanup():
    dataset,_,physical,artifact,plan=etl("pg_rollback")
    transformation=execute_dimensional_transformation(dataset,plan,config=TransformationConfig(persist_artifacts=False))
    config=DatabaseDryRunConfig(host=os.getenv("TEST_POSTGRES_HOST","127.0.0.1"),port=int(os.getenv("TEST_POSTGRES_PORT","55432")),
        database=os.getenv("TEST_POSTGRES_DB","bi_factory_test"),user=os.getenv("TEST_POSTGRES_USER",os.getenv("USER","codespace")),cleanup_policy=CleanupPolicy.ALWAYS)
    failed=execute_database_dry_run(physical,artifact,plan,transformation,config=config,
        adapter=PostgreSQLLocalAdapter(config),inject_failure_step=plan.execution_order[-1])
    assert failed.status==DatabaseDryRunStatus.ROLLED_BACK
    assert failed.rollback_tests.status=="PASS" and failed.cleanup_result.schema_dropped
    resumed=execute_database_dry_run(physical,artifact,plan,transformation,config=config,adapter=PostgreSQLLocalAdapter(config))
    assert resumed.validation_results.restartability.status=="PASS"
    assert resumed.validation_results.idempotency.status=="PASS"
    assert resumed.cleanup_result.schema_dropped


@pytest.mark.postgres_integration
@pytest.mark.skipif(not _available(),reason="SKIPPED_ENVIRONMENT: local PostgreSQL/psycopg unavailable")
def test_real_postgresql_bridge_load_and_foreign_keys():
    def accept_bridge(_,validation):
        for bridge in validation.contract.bridge_candidates: bridge.requires_validation=False
    result,_=_physical("pg_bridge",columns=[("event_id",SemanticRole.IDENTIFIER),
        ("person_id",SemanticRole.IDENTIFIER),("group_id",SemanticRole.IDENTIFIER)],
        data=[["E1","P1","G1"],["E2","P1","G2"],["E3","P2","G1"],["E4","P2","G2"]],
        grain=["event_id"],transform=accept_bridge)
    assert result.bridge_load_results and result.bridge_load_results[0].loaded_rows==4
    assert result.validation_results.fk_validation.status=="PASS"
