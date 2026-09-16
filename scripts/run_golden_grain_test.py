"""Readable permanent Golden Grain gate."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.grain.discovery import GrainDiscoveryConfig, discover_grain
from core.quality.models import IdentifierConstraint
from tests.golden_grain.fixtures import (
    aggregation_dataset, ambiguous_dataset, insufficient_dataset,
    multi_grain_dataset, optional_dataset, quality_dependency_dataset,
    single_grain_dataset, technical_key_dataset,
)

checks = {
    "Single Grain": discover_grain(single_grain_dataset()).grain_classification.value == "SINGLE_GRAIN",
    "Repeated Identifier": any(c.duplicate_count for c in discover_grain(single_grain_dataset()).grain_candidates),
    "Technical Key Exclusion": all("source_row_id" not in "|".join(c.candidate_fields)
        for c in discover_grain(technical_key_dataset(), {"orders::source_row_id": IdentifierConstraint(technical_key=True)}).grain_candidates),
    "Composite Grain": discover_grain(single_grain_dataset()).grain_candidates[0].candidate_fields == ["orders::order_id", "orders::item_id"],
    "Aggregation Risk": bool(discover_grain(aggregation_dataset()).aggregation_risks),
    "Multi-Grain": discover_grain(multi_grain_dataset()).grain_classification.value == "MULTI_GRAIN",
    "Ambiguous": discover_grain(ambiguous_dataset()).grain_classification.value == "AMBIGUOUS_GRAIN",
    "Insufficient Evidence": discover_grain(insufficient_dataset()).grain_classification.value == "INSUFFICIENT_EVIDENCE",
    "Quality Dependency": bool(discover_grain(quality_dependency_dataset()).quality_dependencies),
    "Optional Field": discover_grain(optional_dataset()).recommended_candidate_id is not None,
}
print("GOLDEN GRAIN TEST")
for name, passed in checks.items():
    print(f"{name:.<30} {'PASS' if passed else 'FAIL'}")
if not all(checks.values()):
    raise SystemExit(1)
print("GOLDEN GRAIN STATUS: PASSED")
