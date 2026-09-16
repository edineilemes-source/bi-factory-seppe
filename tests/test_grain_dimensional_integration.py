from core.dimensional.discovery import discover_dimensions
from core.dimensional.models import ModelingRole
from core.grain.discovery import discover_grain
from core.grain.validation import validate_grain
from core.profiling.models import SemanticRole
from tests.golden_grain.fixtures import prepared


def test_effective_grain_semantics_quality_and_prepared_values_flow_to_dimensional():
    dataset = prepared("integration", [
        ("source_row_id", SemanticRole.IDENTIFIER),
        ("business_id", SemanticRole.IDENTIFIER),
        ("numeric_identifier", SemanticRole.CODE),
        ("quantity", SemanticRole.MEASURE)],
        [["sr1", "B1", 100, 2], ["sr2", "B2", 200, 3]])
    before = dataset.model_dump_json()
    grain_report = discover_grain(dataset)
    ids = {f.technical_name: f.source_field_id for f in dataset.schema_fields}
    grain = validate_grain(grain_report, user_grain_description="evento por business id",
                           grain_fields=[ids["business_id"]], validated_event="evento validado")
    dimensional = discover_dimensions(dataset, grain, grain_report)

    assert dimensional.fact_candidates[0].grain_fields == [ids["business_id"]]
    assert dimensional.fact_candidates[0].event == "evento validado"
    assert {m.source_field_id for m in dimensional.measure_candidates} == {ids["quantity"]}
    assert next(d for d in dimensional.field_decisions
                if d.source_field_id == ids["source_row_id"]).effective_modeling_role == ModelingRole.IGNORED_FOR_ANALYTICS
    assert dataset.model_dump_json() == before
