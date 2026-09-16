from pathlib import Path

from core.ddl.generator import generate_postgresql_ddl
from core.etl.planner import build_dimensional_etl_plan
from core.etl.validation import validate_dimensional_etl_plan
from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.star.models import SCDType
from core.transformation.engine import TransformationConfig, execute_dimensional_transformation
from core.transformation.export import validate_artifact_consistency
from tests.test_ddl_persistence import _effective_star
from tests.test_grain_persistence import _persisted_prepared


def test_transformation_metadata_persistence_and_artifact_consistency(tmp_path):
    repository = SQLiteAnalysisRepository(tmp_path / "transform.sqlite3")
    dataset = _persisted_prepared(repository)
    validation = _effective_star(repository, dataset)
    for dimension in validation.contract.dimension_tables:
        dimension.scd_strategy.strategy = SCDType.TYPE_1
        dimension.scd_strategy.requires_validation = False
    validation.contract.ignored_fields.extend(validation.contract.unresolved_fields)
    validation.contract.unresolved_fields = []
    physical, artifact = generate_postgresql_ddl(validation)
    repository.save_physical_schema_plan(physical)
    repository.save_postgresql_ddl_artifact(artifact)
    artifact = repository.validate_postgresql_ddl_artifact(artifact)
    physical = repository.get_effective_physical_schema(dataset.prepared_dataset_id)
    plan = build_dimensional_etl_plan(dataset, validation.contract, physical, artifact)
    repository.save_dimensional_etl_plan(plan)
    repository.save_validated_dimensional_etl_plan(validate_dimensional_etl_plan(plan))

    before = dataset.model_dump_json()
    run = execute_dimensional_transformation(dataset, plan,
        config=TransformationConfig(artifact_root=tmp_path / "artifacts", persist_artifacts=True))
    assert validate_artifact_consistency(run) == []
    repository.save_dimensional_transformation_run(run)
    loaded = repository.get_dimensional_transformation_run(run.run_id)

    assert loaded.status == run.status and loaded.fingerprint == run.fingerprint
    assert loaded.artifact_root == run.artifact_root
    assert loaded.reconciliation_report == run.reconciliation_report
    assert all(not result.staged_rows for result in loaded.dimension_results + loaded.fact_results + loaded.bridge_results)
    assert all(Path(path).exists() for step in loaded.execution_steps for path in step.artifact_paths)
    assert dataset.model_dump_json() == before
