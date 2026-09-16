from copy import deepcopy

from core.grain.discovery import discover_grain
from core.prepared.service import prepare_dataset
from tests.golden_prepared.pipeline import golden_prepared_inputs


def test_source_to_prepared_to_grain_uses_effective_complete_values_without_mutation():
    workbook, semantic, quality = golden_prepared_inputs()
    source_before = deepcopy(workbook.sheets[0].rows)
    prepared = prepare_dataset(workbook, semantic, quality)
    report = discover_grain(prepared)

    assert report.prepared_dataset_id == prepared.prepared_dataset_id
    assert report.prepared_dataset_fingerprint == prepared.fingerprint
    assert report.dataset_row_count == prepared.row_count == len(workbook.sheets[0].rows) - 1
    assert all("source_row_id" not in field
               for candidate in report.grain_candidates for field in candidate.candidate_fields)
    assert all(field in {item.source_field_id for item in prepared.schema_fields}
               for candidate in report.grain_candidates for field in candidate.candidate_fields)
    assert workbook.sheets[0].rows == source_before
