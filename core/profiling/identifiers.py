"""Canonical technical representations for identifier analysis only."""

import math
import re
from decimal import Decimal
from numbers import Integral, Real
from typing import Any


def canonicalize_identifier(value: Any) -> str:
    """Represent identifiers consistently without ever changing the source value.

    Text remains text (including leading zeroes and letters). Integral numeric
    values lose only a technical decimal suffix introduced by their container.
    """
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, Integral):
        return str(value)
    if isinstance(value, Decimal):
        if value.is_finite() and value == value.to_integral_value():
            return format(value, "f").split(".", 1)[0]
        return format(value, "f")
    if isinstance(value, Real):
        number = float(value)
        if math.isfinite(number) and number.is_integer():
            return str(int(number))
    return str(value).strip()


def identifier_pattern(value: Any) -> str:
    """Return the structural pattern of the canonical identifier."""
    canonical = canonicalize_identifier(value)
    return re.sub(r"[A-Za-z]", "A", re.sub(r"\d", "9", canonical))
