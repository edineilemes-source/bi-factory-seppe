"""Logical Star Schema Contract engine (no physical SQL)."""

from core.star.engine import StarSchemaConfig, build_star_schema_contract
from core.star.validation import effective_star_schema_contract, validate_star_schema_contract

__all__ = ["StarSchemaConfig", "build_star_schema_contract",
           "effective_star_schema_contract", "validate_star_schema_contract"]
