import json

from core.grain.discovery import discover_grain
from core.grain.export import export_grain_definition_json, export_grain_discovery_json
from core.grain.models import GrainReadiness
from core.grain.validation import effective_grain, validate_grain
from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.prepared.service import prepare_dataset
from tests.golden_prepared.pipeline import golden_prepared_inputs


def _persisted_prepared(repository):
    workbook, semantic, quality = golden_prepared_inputs()
    document = repository.register_document(b"grain persistence", "grain.xlsx")
    analysis = repository.create_analysis(document.source_document_id, semantic.observed_profile)
    role_by_name = {item.technical_name: item.validated_role for item in semantic.validated_semantics}
    for item in analysis.report.validated_semantics:
        item.validated_role = role_by_name[item.technical_name]
    quality.analysis_id = analysis.analysis_id
    for issue in quality.issues:
        issue.analysis_id = analysis.analysis_id
    dataset = prepare_dataset(workbook, analysis.report, quality)
    repository.save_prepared_dataset(dataset)
    return dataset


def test_candidate_confirmation_persists_reloads_and_resolves_effective_grain(tmp_path):
    repository = SQLiteAnalysisRepository(tmp_path / "grain.sqlite3")
    dataset = _persisted_prepared(repository)
    report = discover_grain(dataset, version=repository.next_grain_report_version(dataset.prepared_dataset_id))
    repository.save_grain_discovery_report(report)
    definition = validate_grain(
        report, candidate_id=report.recommended_candidate_id,
        validated_process="processo confirmado", validated_event="evento confirmado",
        version=repository.next_grain_definition_version(dataset.prepared_dataset_id))
    repository.save_grain_definition(definition)

    restored = repository.get_effective_grain(dataset.prepared_dataset_id)
    assert restored == definition
    assert effective_grain(restored) == definition
    assert restored.status == GrainReadiness.READY_FOR_DIMENSIONAL_MODELING
    assert restored.effective_process == "processo confirmado"
    assert restored.effective_event == "evento confirmado"
    discovery_export = json.loads(export_grain_discovery_json(report))
    definition_export = json.loads(export_grain_definition_json(restored))
    assert discovery_export["prepared_dataset_fingerprint"] == dataset.fingerprint
    assert definition_export["effective_process"] == "processo confirmado"
    assert definition_export["lineage"]["grain_id"] == restored.grain_id


def test_reanalysis_and_new_validation_create_versions_without_overwrite(tmp_path):
    repository = SQLiteAnalysisRepository(tmp_path / "grain-versions.sqlite3")
    dataset = _persisted_prepared(repository)
    first_report = discover_grain(dataset, version=repository.next_grain_report_version(dataset.prepared_dataset_id))
    repository.save_grain_discovery_report(first_report)
    first = validate_grain(first_report, candidate_id=first_report.recommended_candidate_id,
                           version=repository.next_grain_definition_version(dataset.prepared_dataset_id))
    repository.save_grain_definition(first)
    second_report = discover_grain(dataset, version=repository.next_grain_report_version(dataset.prepared_dataset_id))
    repository.save_grain_discovery_report(second_report)
    second = validate_grain(second_report, user_grain_description="Uma linha representa revisão manual.",
                            grain_fields=[],
                            version=repository.next_grain_definition_version(dataset.prepared_dataset_id))
    repository.save_grain_definition(second)

    assert [item.version for item in repository.list_grain_discovery_reports(dataset.prepared_dataset_id)] == [2, 1]
    assert first.version == 1 and second.version == 2
    assert repository.get_effective_grain(dataset.prepared_dataset_id) == second


def test_without_human_validation_dataset_is_not_ready():
    assert effective_grain(None) is None
