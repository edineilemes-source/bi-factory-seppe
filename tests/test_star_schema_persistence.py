import json

import pytest

from core.dimensional.discovery import discover_dimensions
from core.dimensional.validation import validate_dimensional_discovery
from core.grain.discovery import discover_grain
from core.grain.validation import validate_grain
from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.star.engine import build_star_schema_contract
from core.star.export import export_star_schema_contract_json, export_validated_star_schema_json
from core.star.validation import effective_star_schema_contract, validate_star_schema_contract
from tests.test_grain_persistence import _persisted_prepared


def _persist_effective_lineage(repository, dataset):
    grain_report = discover_grain(dataset, version=repository.next_grain_report_version(dataset.prepared_dataset_id))
    repository.save_grain_discovery_report(grain_report)
    grain = validate_grain(grain_report, candidate_id=grain_report.recommended_candidate_id,
                           version=repository.next_grain_definition_version(dataset.prepared_dataset_id))
    repository.save_grain_definition(grain)
    dimensional_report = discover_dimensions(dataset, grain, grain_report,
        version=repository.next_dimensional_report_version(dataset.prepared_dataset_id))
    repository.save_dimensional_discovery_report(dimensional_report)
    dimensional = validate_dimensional_discovery(
        dimensional_report, accepted_unresolved_fields=dimensional_report.unresolved_fields,
        version=repository.next_dimensional_validation_version(dataset.prepared_dataset_id))
    repository.save_validated_dimensional_discovery(dimensional)
    return grain, dimensional


def test_contract_validation_persistence_reload_effective_and_versioning(tmp_path):
    repository = SQLiteAnalysisRepository(tmp_path / "star.sqlite3")
    dataset = _persisted_prepared(repository)
    grain, dimensional = _persist_effective_lineage(repository, dataset)
    report = build_star_schema_contract(dataset, grain, dimensional,
        version=repository.next_star_schema_report_version(dataset.prepared_dataset_id))
    repository.save_star_schema_contract_report(report)
    validation = validate_star_schema_contract(
        report, version=repository.next_star_schema_validation_version(dataset.prepared_dataset_id))
    repository.save_validated_star_schema_contract(validation)

    assert repository.list_star_schema_contract_reports(dataset.prepared_dataset_id)[0].report == report
    assert repository.get_effective_star_schema_contract(dataset.prepared_dataset_id) == validation.contract
    assert effective_star_schema_contract(validation) == validation.contract
    assert json.loads(export_star_schema_contract_json(report))["contract"]["lineage"]["prepared_dataset_fingerprint"] == dataset.fingerprint
    assert json.loads(export_validated_star_schema_json(validation))["version"] == 1

    second = build_star_schema_contract(dataset, grain, dimensional,
        version=repository.next_star_schema_report_version(dataset.prepared_dataset_id))
    repository.save_star_schema_contract_report(second)
    assert [item.version for item in repository.list_star_schema_contract_reports(dataset.prepared_dataset_id)] == [2, 1]


def test_contract_lineage_mismatch_is_rejected(tmp_path):
    repository = SQLiteAnalysisRepository(tmp_path / "star-lineage.sqlite3")
    dataset = _persisted_prepared(repository)
    grain, dimensional = _persist_effective_lineage(repository, dataset)
    report = build_star_schema_contract(dataset, grain, dimensional)
    report.lineage.prepared_dataset_fingerprint = "changed"
    with pytest.raises(ValueError, match="incompatível"):
        repository.save_star_schema_contract_report(report)
