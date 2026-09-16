"""Declarative expectations intentionally separated from engine heuristics."""

EXPECTED = {
    "single": "SINGLE_GRAIN",
    "composite_fields": ["orders::order_id", "orders::item_id"],
    "multi": "MULTI_GRAIN",
    "ambiguous": "AMBIGUOUS_GRAIN",
    "insufficient": "INSUFFICIENT_EVIDENCE",
    "max_candidates": 20,
}
