from core.dimensional.discovery import DimensionalDiscoveryConfig, discover_dimensions
from core.dimensional.models import DimensionRole, FactType, ModelingRole, ProposalStatus
from core.dimensional.validation import effective_dimensional_discovery, validate_dimensional_discovery
from core.grain.discovery import discover_grain
from core.grain.models import GrainClassification, ObservedFunctionalDependency
from core.grain.validation import validate_grain
from core.profiling.models import SemanticRole
from core.quality.models import FieldQualityStatus, QualityIssue, QualityIssueType, QualitySeverity
from tests.golden_dimensional.expectations import EXPECTED_CASES
from tests.golden_grain.fixtures import prepared


def proposal(name, columns, data, grain_names, *, fds=None, issues=None, multi_groups=None):
    dataset = prepared(name, columns, data, issues=issues)
    report = discover_grain(dataset)
    report.functional_dependencies = fds or []
    ids = {field.technical_name: field.source_field_id for field in dataset.schema_fields}
    definition = validate_grain(report, user_grain_description="evento validado",
                                grain_fields=[ids[item] for item in grain_names])
    if multi_groups:
        definition.grain_type = GrainClassification.MULTI_GRAIN
        definition.grain_groups = [[ids[item] for item in group] for group in multi_groups]
    return dataset, report, definition, ids, discover_dimensions(dataset, definition, report)


def test_a_transaction_fact_measure_is_semantic_not_merely_numeric():
    dataset, _, _, ids, result = proposal("tx", [
        ("order_id", SemanticRole.IDENTIFIER), ("item_id", SemanticRole.IDENTIFIER),
        ("product_id", SemanticRole.IDENTIFIER), ("customer_id", SemanticRole.IDENTIFIER),
        ("quantity", SemanticRole.MEASURE), ("unit_price", SemanticRole.MEASURE),
        ("numeric_code", SemanticRole.CODE)],
        [["O1", "1", "P1", "C1", 2, 10, 100], ["O1", "2", "P2", "C1", 1, 20, 200]],
        ["order_id", "item_id"])
    assert result.fact_candidates[0].fact_type == FactType(EXPECTED_CASES["transaction_fact"]["fact_type"])
    assert {m.source_field_id for m in result.measure_candidates} == {ids["quantity"], ids["unit_price"]}
    assert ids["numeric_code"] not in {m.source_field_id for m in result.measure_candidates}


def test_b_fd_groups_dimension_attributes_without_independent_fact_measure():
    columns = [("customer_id", SemanticRole.IDENTIFIER), ("customer_name", SemanticRole.DESCRIPTION),
               ("city", SemanticRole.CATEGORY), ("state", SemanticRole.CATEGORY)]
    dataset = prepared("customers", columns, [["C1", "Ana", "X", "S"], ["C2", "Bia", "Y", "T"]])
    ids = {f.technical_name: f.source_field_id for f in dataset.schema_fields}
    report = discover_grain(dataset)
    report.functional_dependencies = [ObservedFunctionalDependency(
        determinant=[ids["customer_id"]], dependent=ids[name], support=2, violations=0, confidence=1)
        for name in ("customer_name", "city", "state")]
    definition = validate_grain(report, user_grain_description="cadastro de cliente", grain_fields=[])
    result = discover_dimensions(dataset, definition, report)
    dim = next(d for d in result.dimension_candidates if ids["customer_id"] in d.business_identifier_fields)
    assert set(dim.descriptive_attributes) == {ids[n] for n in EXPECTED_CASES["dimension_attributes"]["attributes"]}
    assert result.fact_candidates[0].fact_type == FactType.FACTLESS


def test_c_degenerate_identifier():
    _, _, _, ids, result = proposal("invoice_line", [
        ("invoice_number", SemanticRole.IDENTIFIER), ("line_id", SemanticRole.IDENTIFIER),
        ("amount", SemanticRole.MEASURE)], [["I1", "1", 5], ["I1", "2", 8]],
        ["invoice_number", "line_id"])
    decision = next(d for d in result.field_decisions if d.source_field_id == ids["invoice_number"])
    assert decision.effective_modeling_role == ModelingRole.DEGENERATE_IDENTIFIER


def test_d_role_playing_date_is_one_candidate():
    _, _, _, _, result = proposal("dates", [
        ("event_id", SemanticRole.IDENTIFIER), ("order_date", SemanticRole.DATE),
        ("ship_date", SemanticRole.DATE), ("payment_date", SemanticRole.DATE)],
        [["E1", "2026-01-01", "2026-01-02", "2026-01-03"]], ["event_id"])
    dim = next(d for d in result.dimension_candidates
               if d.role == DimensionRole.ROLE_PLAYING_DIMENSION_CANDIDATE)
    assert len(dim.role_playing_roles) == EXPECTED_CASES["role_playing_date"]["role_count"]


def test_e_aggregation_risk_blocks_additive_claim():
    dataset = prepared("risk", [("invoice", SemanticRole.IDENTIFIER),
        ("item", SemanticRole.IDENTIFIER), ("invoice_total", SemanticRole.MEASURE)],
        [["I1", "1", 100], ["I1", "2", 100], ["I2", "1", 80], ["I2", "2", 80]])
    report = discover_grain(dataset)
    ids = {f.technical_name: f.source_field_id for f in dataset.schema_fields}
    definition = validate_grain(report, user_grain_description="linha", grain_fields=[ids["invoice"], ids["item"]])
    result = discover_dimensions(dataset, definition, report)
    measure = result.measure_candidates[0]
    assert measure.additivity.value == EXPECTED_CASES["aggregation_risk"]["hint"]
    assert measure.measure_modeling_warning


def test_f_factless_fact():
    _, _, _, _, result = proposal("factless", [
        ("event_id", SemanticRole.IDENTIFIER), ("customer_id", SemanticRole.IDENTIFIER),
        ("campaign_id", SemanticRole.IDENTIFIER), ("event_date", SemanticRole.DATE)],
        [["E1", "C1", "P1", "2026-01-01"], ["E2", "C2", "P1", "2026-01-02"]], ["event_id"])
    assert result.fact_candidates[0].fact_type == FactType.FACTLESS


def test_g_multi_grain_creates_separate_facts_and_conformed_candidates():
    _, _, _, _, result = proposal("multi", [
        ("event_a", SemanticRole.IDENTIFIER), ("event_b", SemanticRole.IDENTIFIER),
        ("customer_id", SemanticRole.IDENTIFIER), ("amount", SemanticRole.MEASURE)],
        [["A1", None, "C1", 2], [None, "B1", "C1", 3]], ["event_a", "event_b"],
        multi_groups=[["event_a"], ["event_b"]])
    assert len(result.fact_candidates) == EXPECTED_CASES["multi_grain"]["fact_count"]
    assert any(d.conformed_candidate for d in result.dimension_candidates)


def test_h_junk_dimension_is_only_a_candidate():
    _, _, _, _, result = proposal("junk", [
        ("event_id", SemanticRole.IDENTIFIER), ("active_flag", SemanticRole.BOOLEAN),
        ("status", SemanticRole.CATEGORY), ("amount", SemanticRole.MEASURE)],
        [["E1", True, "new", 1], ["E2", False, "done", 2]], ["event_id"])
    assert any(d.role == DimensionRole.JUNK_DIMENSION_CANDIDATE for d in result.dimension_candidates)


def test_i_quality_dependency_preserves_dimension():
    issue = QualityIssue(issue_id="q1", analysis_id="analysis:q", source_field_id="q::customer_id",
        issue_type=QualityIssueType.IDENTIFIER_INCONSISTENCY, severity=QualitySeverity.ERROR,
        affected_count=1, reason="identificador inconsistente")
    dataset, report, definition, ids, _ = proposal("q", [
        ("event_id", SemanticRole.IDENTIFIER), ("customer_id", SemanticRole.IDENTIFIER)],
        [["E1", "C1"], ["E2", "C2"]], ["event_id"], issues=[issue])
    result = discover_dimensions(dataset, definition, report)
    dim = next(d for d in result.dimension_candidates if ids["customer_id"] in d.source_fields)
    assert dim.quality_dependencies


def test_j_not_evaluated_remains_unresolved():
    dataset, report, definition, ids, _ = proposal("deferred", [
        ("event_id", SemanticRole.IDENTIFIER), ("mystery", SemanticRole.CATEGORY)],
        [["E1", "x"]], ["event_id"])
    next(f for f in dataset.schema_fields if f.technical_name == "mystery").quality_status = FieldQualityStatus.NOT_EVALUATED
    result = discover_dimensions(dataset, definition, report)
    assert next(d for d in result.field_decisions if d.source_field_id == ids["mystery"]).effective_modeling_role == ModelingRole.UNRESOLVED


def test_k_technical_key_excluded():
    _, _, _, ids, result = proposal("tech", [
        ("source_row_id", SemanticRole.IDENTIFIER), ("event_id", SemanticRole.IDENTIFIER)],
        [["internal1", "E1"]], ["event_id"])
    decision = next(d for d in result.field_decisions if d.source_field_id == ids["source_row_id"])
    assert decision.effective_modeling_role == ModelingRole.IGNORED_FOR_ANALYTICS
    assert all(ids["source_row_id"] not in d.source_fields for d in result.dimension_candidates)


def test_l_full_field_coverage_limits_effective_and_source_immutable():
    dataset, report, definition, _, _ = proposal("coverage", [
        ("event_id", SemanticRole.IDENTIFIER), ("label", SemanticRole.DESCRIPTION),
        ("amount", SemanticRole.MEASURE)], [["E1", "x", 1], ["E2", "y", 2]], ["event_id"])
    before = dataset.model_dump_json()
    result = discover_dimensions(dataset, definition, report,
        config=DimensionalDiscoveryConfig(max_fact_candidates=3, max_dimension_candidates=4))
    assert len(result.field_decisions) == dataset.field_count
    assert dataset.model_dump_json() == before
    validated = validate_dimensional_discovery(result, accepted_unresolved_fields=result.unresolved_fields)
    assert effective_dimensional_discovery(validated) == validated
    assert validated.status == ProposalStatus.READY_FOR_STAR_SCHEMA
    assert result.max_fact_candidates == 3 and result.max_dimension_candidates == 4
