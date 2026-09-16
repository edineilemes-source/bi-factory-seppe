"""Arrow-safe dataframe preparation for Streamlit presentation tables."""

from collections.abc import Iterable
from typing import Any

import pandas as pd


def _is_missing(value: Any) -> bool:
    if value is None or value is pd.NA:
        return True
    missing = pd.isna(value)
    return bool(missing) if isinstance(missing, bool) else False


def arrow_compatible_dataframe(
    data: Any, *, numeric_columns: Iterable[str] = (),
    integer_columns: Iterable[str] = (), datetime_columns: Iterable[str] = (),
) -> pd.DataFrame:
    """Build a DataFrame whose nullable columns have deterministic Arrow types.

    Declared numeric values stay numeric and missing values stay ``pd.NA``. For
    untyped source previews only, heterogeneous object columns are represented as
    text instead of relying on PyArrow's unsafe type inference.
    """
    frame = data.copy() if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    numeric = set(numeric_columns)
    integers = set(integer_columns)
    datetimes = set(datetime_columns)
    for column in numeric | integers | datetimes:
        if column not in frame.columns:
            continue
        original = frame[column]
        if column in datetimes:
            converted = pd.to_datetime(original, errors="coerce", utc=True)
            invalid = original.notna() & converted.isna()
            if invalid.any():
                raise ValueError(f"Coluna temporal contém valor inválido: {column}")
            frame[column] = converted
            continue
        converted = pd.to_numeric(original, errors="coerce")
        invalid = original.notna() & converted.isna()
        if invalid.any():
            raise ValueError(f"Coluna numérica contém valor não numérico: {column}")
        frame[column] = converted.astype("Int64" if column in integers else "Float64")

    declared = numeric | integers | datetimes
    for column in frame.columns:
        if column in declared or frame[column].dtype != object:
            continue
        non_null = frame[column].dropna()
        value_types = {type(value) for value in non_null}
        if len(value_types) > 1:
            frame[column] = frame[column].map(
                lambda value: pd.NA if _is_missing(value) else str(value)
            ).astype("string")
    return frame
