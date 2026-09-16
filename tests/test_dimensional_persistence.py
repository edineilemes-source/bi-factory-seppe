import json

import pytest

from core.dimensional.discovery import discover_dimensions
from core.dimensional.export import export_dimensional_discovery_json, export_validated_dimensional_json
from core.dimensional.models import ModelingRole, ProposalStatus
from core.dimensional.validation import effective_dimensional_discovery, validate_dimensional_discovery
from core.grain.discovery import discover_grain
from core.grain.validation import validate_grain
from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from tests.test_grain_persistence import _persisted_prepared


def _lineage(repository, dataset):
    grain_report = discover_grain(dataset, version=repository.next_grain_report_version(dataset.prepared_dataset_id))
    repository.save_grain_discovery_report(grain_report)
    grain = validate_grain(grain_report, candidate_id=grain_report.recommended_candidate_id,
                           version=repository.next_grain_definition_version(dataset.prepared_dataset_id))
    repository.save_grain_definition(grain)
    report = discover_dimensions(dataset, grain, grain_report,
        version=repository.next_dimensional_report_version(dataset.prepared_dataset_id))
    repository.save_dimensional_discovery_report(report)
    return grain_report, grain, report


def test_dimensional_persistence_reload_versioning_effective_and_exports(tmp_path):
    repository = SQLiteAnalysisRepository(tmp_path / "dimensional.sqlite3")
    dataset = _persisted_prepared(repository)
    _, _, first_report = _lineage(repository, dataset)
    validation = validate_dimensional_discovery(
        first_report, accepted_unresolved_fields=first_report.unresolved_fields,
        version=repository.next_dimensional_validation_version(dataset.prepared_dataset_id))
    repository.save_validated_dimensional_discovery(validation)

    assert repository.list_dimensional_discovery_reports(dataset.prepared_dataset_id)[0].report == first_report
    assert repository.get_effective_dimensional_discovery(dataset.prepared_dataset_id) == validation
    assert effective_dimensional_discovery(validation) == validation
    assert json.loads(export_dimensional_discovery_json(first_report))["lineage"]["grain_definition_id"]
    assert json.loads(export_validated_dimensional_json(validation))["validation"]["version"] == 1

    second = discover_dimensions(dataset, repository.get_effective_grain(dataset.prepared_dataset_id),
        repository.list_grain_discovery_reports(dataset.prepared_dataset_id)[0].report,
        version=repository.next_dimensional_report_version(dataset.prepared_dataset_id))
    repository.save_dimensional_discovery_report(second)
    assert [r.version for r in repository.list_dimensional_discovery_reports(dataset.prepared_dataset_id)] == [2, 1]


def test_validation_override_preserves_observed_and_ready_rules():
    from tests.golden_dimensional.test_golden_dimensional import proposal
    from core.profiling.models import SemanticRole
    _, _, _, ids, report = proposal("effective", [
        ("event_id", SemanticRole.IDENTIFIER), ("unknown_measure", SemanticRole.UNKNOWN)],
        [["E1", 1]], ["event_id"])
    original = next(d for d in report.field_decisions if d.source_field_id == ids["unknown_measure"])
    validation = validate_dimensional_discovery(
        report, field_role_overrides={ids["unknown_measure"]: ModelingRole.MEASURE})
    effective = next(d for d in validation.field_decisions if d.source_field_id == ids["unknown_measure"])
    assert original.observed_modeling_role == ModelingRole.UNRESOLVED
    assert original.validated_modeling_role is None
    assert effective.observed_modeling_role == ModelingRole.UNRESOLVED
    assert effective.validated_modeling_role == ModelingRole.MEASURE
    assert effective.effective_modeling_role == ModelingRole.MEASURE
    assert validation.status == ProposalStatus.READY_FOR_STAR_SCHEMA


def test_lineage_mismatch_is_rejected(tmp_path):
    repository = SQLiteAnalysisRepository(tmp_path / "lineage.sqlite3")
    dataset = _persisted_prepared(repository)
    _, _, report = _lineage(repository, dataset)
    invalid = report.model_copy(update={"prepared_dataset_fingerprint": "changed", "report_id": "invalid"})
    with pytest.raises(ValueError, match="incompatível"):
        repository.save_dimensional_discovery_report(invalid)
