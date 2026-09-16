"""Declarative outcomes, intentionally independent from engine heuristics."""

EXPECTED = {
    "transaction": {"facts": 1, "dimensions": 3, "measures": 2, "cardinality": "MANY_TO_ONE"},
    "degenerate": {"fact_member": "invoice_number", "forbidden_dimension": "invoice"},
    "role_playing": {"base_dimensions": 1, "relationships": 3},
    "factless": {"measures": 0, "valid": True},
    "multi_fact": {"facts": 2, "shared_dimension": True},
    "many_to_many": {"warning": "MANY_TO_MANY_RELATIONSHIP", "bridge": 1},
    "scd_unknown": {"strategy": "UNKNOWN", "requires_validation": True},
    "scd_type_2": {"strategy": "TYPE_2", "plans": 3},
    "aggregation_risk": {"warning": "AGGREGATION_RISK"},
    "business_key": {"separate_from_surrogate": True},
    "technical_key": {"excluded": "source_row_id"},
    "nullability": {"optional": "true"},
    "collision": {"unique": True, "warning": "NAME_COLLISION"},
    "coverage": {"percentage": 100},
}
