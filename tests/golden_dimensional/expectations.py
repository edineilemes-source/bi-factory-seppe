"""Declarative expectations independent from discovery implementation."""

EXPECTED_CASES = {
    "transaction_fact": {"fact_type": "TRANSACTION", "measures": {"quantity", "unit_price"}},
    "dimension_attributes": {"dimension_count": 1, "attributes": {"customer_name", "city", "state"}},
    "degenerate_dimension": {"field": "invoice_number", "role": "DEGENERATE_IDENTIFIER"},
    "role_playing_date": {"role": "ROLE_PLAYING_DIMENSION_CANDIDATE", "role_count": 3},
    "aggregation_risk": {"hint": "REQUIRES_VALIDATION", "warning": True},
    "factless_fact": {"fact_type": "FACTLESS"},
    "multi_grain": {"fact_count": 2, "conformed": True},
    "junk_dimension": {"role": "JUNK_DIMENSION_CANDIDATE"},
    "quality_dependency": {"minimum": 1},
    "not_evaluated": {"role": "UNRESOLVED"},
    "technical_key": {"role": "IGNORED_FOR_ANALYTICS"},
    "field_coverage": {"percentage": 100},
}
