"""Regression coverage for Streamlit/PyArrow presentation tables."""

import pandas as pd
import pyarrow as pa
import pytest

from app.dataframe_compat import arrow_compatible_dataframe


def test_nullable_quality_score_serializes_to_arrow_as_numeric():
    frame = arrow_compatible_dataframe(
        {"Quality Score": [100.0, 99.5, None, 92.0]},
        numeric_columns=("Quality Score",),
    )
    table = pa.Table.from_pandas(frame, preserve_index=False)
    assert str(frame["Quality Score"].dtype) == "Float64"
    assert pa.types.is_floating(table.schema.field("Quality Score").type)
    assert table.column("Quality Score").to_pylist() == [100.0, 99.5, None, 92.0]


def test_numeric_ui_column_rejects_mixed_number_and_na_label():
    with pytest.raises(ValueError, match="Quality Score"):
        arrow_compatible_dataframe(
            {"Quality Score": [100.0, "N/A", 92.0]},
            numeric_columns=("Quality Score",),
        )


def test_nullable_counts_percentages_and_timestamps_are_arrow_safe():
    frame = arrow_compatible_dataframe(
        {"Count": [1, None, 3], "Percentage": [50.0, None, 99.5],
         "Updated At": ["2026-08-24T10:00:00Z", None, "2026-08-24T12:00:00Z"]},
        integer_columns=("Count",), numeric_columns=("Percentage",),
        datetime_columns=("Updated At",),
    )
    table = pa.Table.from_pandas(frame, preserve_index=False)
    assert pa.types.is_integer(table.schema.field("Count").type)
    assert pa.types.is_floating(table.schema.field("Percentage").type)
    assert pa.types.is_timestamp(table.schema.field("Updated At").type)


def test_untyped_mixed_preview_column_becomes_nullable_text():
    frame = arrow_compatible_dataframe(pd.DataFrame({"Value": [1.0, "N/A", None]}))
    table = pa.Table.from_pandas(frame, preserve_index=False)
    assert str(frame["Value"].dtype) == "string"
    assert pa.types.is_string(table.schema.field("Value").type)
