from core.dimensional.validation import validate_dimensional_discovery
from core.profiling.models import SemanticRole
from core.star.engine import build_star_schema_contract
from core.star.models import WarningType
from tests.golden_dimensional.test_golden_dimensional import proposal


def test_full_effective_dimensional_to_star_lineage_risks_quality_and_immutability():
    dataset, grain_report, grain, ids, dimensional_report = proposal("dim_to_star", [
        ("source_row_id", SemanticRole.IDENTIFIER), ("invoice", SemanticRole.IDENTIFIER),
        ("item", SemanticRole.IDENTIFIER), ("customer_id", SemanticRole.IDENTIFIER),
        ("invoice_total", SemanticRole.MEASURE)],
        [["sr1", "I1", "1", "C1", 100], ["sr2", "I1", "2", "C1", 100],
         ["sr3", "I2", "1", "C2", 80], ["sr4", "I2", "2", "C2", 80]],
        ["invoice", "item"])
    dimensional = validate_dimensional_discovery(
        dimensional_report, accepted_unresolved_fields=dimensional_report.unresolved_fields)
    before = dataset.model_dump_json()
    report = build_star_schema_contract(dataset, grain, dimensional)

    assert report.lineage.grain_definition_id == grain.grain_id
    assert report.lineage.dimensional_discovery_id == dimensional.validation_id
    assert report.contract.fact_tables[0].grain_fields == grain.grain_fields
    assert report.contract.fact_tables[0].aggregation_risks == grain_report.aggregation_risks
    assert any(w.warning_type == WarningType.AGGREGATION_RISK for w in report.warnings)
    assert ids["source_row_id"] in report.contract.ignored_fields
    assert dataset.model_dump_json() == before
