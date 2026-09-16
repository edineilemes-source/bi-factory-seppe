from core.ddl.generator import generate_postgresql_ddl
from core.etl.export import export_etl_mapping_csv, export_etl_plan_json, export_execution_order_json
from core.etl.planner import build_dimensional_etl_plan
from core.etl.validation import validate_dimensional_etl_plan
from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.star.models import SCDType
from tests.test_ddl_persistence import _effective_star
from tests.test_grain_persistence import _persisted_prepared


def test_ddl_to_etl_plan_persist_reload_exports_fingerprint_and_source_immutability(tmp_path):
    repository = SQLiteAnalysisRepository(tmp_path / "etl.sqlite3")
    dataset = _persisted_prepared(repository)
    validation = _effective_star(repository, dataset)
    for dimension in validation.contract.dimension_tables:
        dimension.scd_strategy.strategy = SCDType.TYPE_1
        dimension.scd_strategy.requires_validation = False
    validation.contract.ignored_fields.extend(validation.contract.unresolved_fields)
    validation.contract.unresolved_fields = []
    # Persist a new validated logical version carrying the explicit ETL-ready SCD policy.
    # Existing validation is already persisted; updating it in memory is sufficient for this
    # isolated lineage because the physical plan retains the same validated contract identity.
    physical, artifact = generate_postgresql_ddl(validation)
    repository.save_physical_schema_plan(physical)
    repository.save_postgresql_ddl_artifact(artifact)
    artifact = repository.validate_postgresql_ddl_artifact(artifact)
    effective_physical = repository.get_effective_physical_schema(dataset.prepared_dataset_id)
    before = dataset.model_dump_json()
    plan = build_dimensional_etl_plan(dataset, validation.contract, effective_physical, artifact,
        version=repository.next_etl_plan_version(effective_physical.physical_schema_plan_id))
    repository.save_dimensional_etl_plan(plan)
    reloaded = repository.get_dimensional_etl_plan(plan.etl_plan_id)

    assert reloaded == plan and reloaded.fingerprint == plan.fingerprint
    assert export_etl_plan_json(reloaded) == plan.model_dump_json(indent=2).encode()
    assert export_etl_mapping_csv(reloaded) == export_etl_mapping_csv(plan)
    assert export_execution_order_json(reloaded) == export_execution_order_json(plan)
    validated = validate_dimensional_etl_plan(reloaded)
    repository.save_validated_dimensional_etl_plan(validated)
    assert repository.get_effective_dimensional_etl_plan(dataset.prepared_dataset_id) == plan
    assert dataset.model_dump_json() == before
