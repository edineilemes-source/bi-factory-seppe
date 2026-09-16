from core.grain.discovery import GrainDiscoveryConfig, discover_grain
from core.grain.models import GrainClassification
from core.quality.models import IdentifierConstraint
from tests.golden_grain.expectations import EXPECTED
from tests.golden_grain.fixtures import (
    aggregation_dataset, ambiguous_dataset, insufficient_dataset,
    multi_grain_dataset, optional_dataset, quality_dependency_dataset,
    single_grain_dataset, technical_key_dataset,
)


def test_single_composite_and_repeated_identifier_cases():
    report = discover_grain(single_grain_dataset())
    recommended = next(item for item in report.grain_candidates
                       if item.candidate_id == report.recommended_candidate_id)
    assert report.grain_classification.value == EXPECTED["single"]
    assert recommended.candidate_fields == EXPECTED["composite_fields"]
    order = next(item for item in report.grain_candidates
                 if item.candidate_fields == ["orders::order_id"])
    assert order.duplicate_count > 0
    assert recommended.confidence > order.confidence


def test_technical_key_is_never_business_grain():
    dataset = technical_key_dataset()
    report = discover_grain(dataset, {
        "orders::source_row_id": IdentifierConstraint(technical_key=True, unique=True)})
    assert all("orders::source_row_id" not in item.candidate_fields
               for item in report.grain_candidates)


def test_aggregation_risk_is_conservative():
    report = discover_grain(aggregation_dataset())
    risk = next(item for item in report.aggregation_risks
                if item.measure_field_id == "invoice::invoice_total"
                and item.repeated_at_fields == ["invoice::invoice_id"])
    assert risk.aggregation_hint.value == "REQUIRES_GRAIN_VALIDATION"
    assert "poderá duplicar" in risk.description


def test_multi_grain_ambiguous_and_insufficient_are_representable():
    assert discover_grain(multi_grain_dataset()).grain_classification.value == EXPECTED["multi"]
    ambiguous = discover_grain(ambiguous_dataset())
    assert ambiguous.grain_classification.value == EXPECTED["ambiguous"]
    assert ambiguous.requires_user_validation
    insufficient = discover_grain(insufficient_dataset())
    assert insufficient.grain_classification.value == EXPECTED["insufficient"]
    assert insufficient.recommended_candidate_id is None


def test_quality_dependency_and_optional_field_are_preserved():
    quality = discover_grain(quality_dependency_dataset())
    assert quality.quality_dependencies
    assert any(candidate.quality_dependencies for candidate in quality.grain_candidates
               if "quality::item_id" in candidate.candidate_fields)
    optional = discover_grain(optional_dataset())
    recommended = next(item for item in optional.grain_candidates
                       if item.candidate_id == optional.recommended_candidate_id)
    assert recommended.candidate_fields == ["optional::order_id", "optional::item_id"]


def test_candidate_generation_is_bounded():
    columns = [(f"id_{index}", __import__("core.profiling.models", fromlist=["SemanticRole"]).SemanticRole.IDENTIFIER)
               for index in range(30)]
    from tests.golden_grain.fixtures import prepared
    dataset = prepared("wide", columns,
                       [[f"{column}-{row}" for column in range(30)] for row in range(5)])
    config = GrainDiscoveryConfig(max_candidates=EXPECTED["max_candidates"],
                                  max_identifier_fields=12, max_candidate_fields=3)
    report = discover_grain(dataset, config=config)
    assert report.candidate_count <= EXPECTED["max_candidates"]
    assert report.candidates_truncated
