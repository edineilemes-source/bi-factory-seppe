from core.ddl.export import export_postgresql_sql
from core.ddl.generator import generate_postgresql_ddl
from core.ddl.models import PhysicalSchemaStatus
from core.dimensional.discovery import discover_dimensions
from core.dimensional.validation import validate_dimensional_discovery
from core.grain.discovery import discover_grain
from core.grain.validation import validate_grain
from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.star.engine import build_star_schema_contract
from core.star.validation import validate_star_schema_contract
from tests.test_grain_persistence import _persisted_prepared


def _effective_star(repository, dataset):
    grain_report = discover_grain(dataset)
    repository.save_grain_discovery_report(grain_report)
    grain = validate_grain(grain_report, candidate_id=grain_report.recommended_candidate_id)
    repository.save_grain_definition(grain)
    discovery = discover_dimensions(dataset, grain, grain_report)
    repository.save_dimensional_discovery_report(discovery)
    dimensional = validate_dimensional_discovery(discovery, accepted_unresolved_fields=discovery.unresolved_fields)
    repository.save_validated_dimensional_discovery(dimensional)
    report = build_star_schema_contract(dataset, grain, dimensional)
    repository.save_star_schema_contract_report(report)
    validation = validate_star_schema_contract(report)
    repository.save_validated_star_schema_contract(validation)
    return validation


def test_star_to_ddl_persistence_reload_export_fingerprint_and_effective_gate(tmp_path):
    repository = SQLiteAnalysisRepository(tmp_path / "ddl.sqlite3")
    dataset = _persisted_prepared(repository)
    before = dataset.model_dump_json()
    validation = _effective_star(repository, dataset)
    plan, artifact = generate_postgresql_ddl(validation, version=repository.next_ddl_version(validation.contract.contract_id))
    repository.save_physical_schema_plan(plan)
    repository.save_postgresql_ddl_artifact(artifact)

    reloaded = repository.get_postgresql_ddl_artifact(artifact.ddl_artifact_id)
    assert reloaded and reloaded.sql == artifact.sql
    assert reloaded.fingerprint == artifact.fingerprint
    assert export_postgresql_sql(reloaded) == artifact.sql.encode()
    assert repository.get_effective_physical_schema(dataset.prepared_dataset_id) is None

    validated = repository.validate_postgresql_ddl_artifact(reloaded)
    effective = repository.get_effective_physical_schema(dataset.prepared_dataset_id)
    assert validated.ready_for_dimensional_etl
    assert effective and effective.lifecycle_status == PhysicalSchemaStatus.EFFECTIVE
    assert dataset.model_dump_json() == before
