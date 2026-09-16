"""Small complete Prepared Datasets covering grain behavior generically."""

import hashlib
from typing import Any

from core.prepared.models import (
    PreparedDataset, PreparedDatasetStatus, PreparedField, PreparedRow,
)
from core.profiling.models import SemanticRole
from core.quality.models import (
    FieldApplicability, FieldQualityStatus, FieldRequirement, QualityIssue,
    QualityIssueType, QualitySeverity,
)


def prepared(name: str, columns: list[tuple[str, SemanticRole]], data: list[list[Any]],
             *, optional: set[str] | None = None,
             issues: list[QualityIssue] | None = None) -> PreparedDataset:
    optional = optional or set()
    schema = [PreparedField(
        source_field_id=f"{name}::{column}", sheet_name=name, source_name=column,
        technical_name=column, effective_semantic_role=role,
        recommended_type="number" if role == SemanticRole.MEASURE else "text",
        prepared_type="number" if role == SemanticRole.MEASURE else "text",
        requirement=(FieldRequirement.OPTIONAL if column in optional else FieldRequirement.UNKNOWN),
        applicability=FieldApplicability.UNKNOWN,
        quality_status=(FieldQualityStatus.NEEDS_BUSINESS_RULE if column in optional
                        else FieldQualityStatus.EVALUATED),
    ) for column, role in columns]
    rows = [PreparedRow(
        source_row_id=f"sr:{name}:{index}", sheet_name=name, source_row_number=index + 1,
        values={field.source_field_id: value for field, value in zip(schema, values)},
    ) for index, values in enumerate(data)]
    fingerprint = hashlib.sha256(repr((name, columns, data)).encode()).hexdigest()
    return PreparedDataset(
        prepared_dataset_id=f"pd:{name}", source_document_id=f"source:{name}",
        analysis_id=f"analysis:{name}", version=1, ruleset_version="golden",
        row_count=len(rows), field_count=len(schema), status=PreparedDatasetStatus.READY,
        schema=schema, rows=rows, transformations=[],
        unresolved_quality_issues=issues or [], fingerprint=fingerprint,
    )


ORDER_COLUMNS = [
    ("order_id", SemanticRole.IDENTIFIER), ("item_id", SemanticRole.IDENTIFIER),
    ("product", SemanticRole.CATEGORY), ("quantity", SemanticRole.MEASURE),
    ("value", SemanticRole.MEASURE),
]
ORDER_DATA = [
    ["O1", "1", "A", 1, 10], ["O1", "2", "B", 2, 20],
    ["O2", "1", "A", 1, 10], ["O2", "2", "C", 1, 30],
]


def single_grain_dataset() -> PreparedDataset:
    return prepared("orders", ORDER_COLUMNS, ORDER_DATA)


def technical_key_dataset() -> PreparedDataset:
    columns = [("source_row_id", SemanticRole.IDENTIFIER)] + ORDER_COLUMNS
    return prepared("orders", columns,
                    [[f"internal-{i}"] + row for i, row in enumerate(ORDER_DATA)])


def aggregation_dataset() -> PreparedDataset:
    return prepared("invoice", [
        ("invoice_id", SemanticRole.IDENTIFIER), ("item_id", SemanticRole.IDENTIFIER),
        ("invoice_total", SemanticRole.MEASURE),
    ], [["I1", "1", 100], ["I1", "2", 100],
        ["I2", "1", 80], ["I2", "2", 80]])


def multi_grain_dataset() -> PreparedDataset:
    return prepared("events", [
        ("order_id", SemanticRole.IDENTIFIER), ("ticket_id", SemanticRole.IDENTIFIER),
        ("order_amount", SemanticRole.MEASURE), ("service_time", SemanticRole.MEASURE),
    ], [["O1", None, 10, None], ["O2", None, 20, None],
        [None, "T1", None, 5], [None, "T2", None, 7]])


def ambiguous_dataset() -> PreparedDataset:
    return prepared("references", [
        ("external_id", SemanticRole.IDENTIFIER),
        ("reference_id", SemanticRole.IDENTIFIER),
        ("amount", SemanticRole.MEASURE),
    ], [["E1", "R9", 1], ["E2", "R8", 2], ["E3", "R7", 3], ["E4", "R6", 4]])


def insufficient_dataset() -> PreparedDataset:
    return prepared("notes", [("description", SemanticRole.DESCRIPTION),
                               ("amount", SemanticRole.MEASURE)],
                    [["a", 1], ["b", 2], ["c", 3]])


def quality_dependency_dataset() -> PreparedDataset:
    issue = QualityIssue(
        issue_id="qi:identifier", analysis_id="analysis:quality",
        source_field_id="quality::item_id", sheet_name="quality", field_name="item_id",
        issue_type=QualityIssueType.IDENTIFIER_INCONSISTENCY,
        severity=QualitySeverity.ERROR, affected_count=1, affected_percentage=25,
        examples=["01-A"], row_numbers=[2], reason="Formato inconsistente não resolvido.")
    return prepared("quality", [("order_id", SemanticRole.IDENTIFIER),
                                ("item_id", SemanticRole.IDENTIFIER)],
                    [["O1", "1"], ["O1", "01-A"], ["O2", "1"], ["O2", "2"]],
                    issues=[issue])


def optional_dataset() -> PreparedDataset:
    return prepared("optional", [("order_id", SemanticRole.IDENTIFIER),
                                 ("item_id", SemanticRole.IDENTIFIER),
                                 ("note", SemanticRole.CATEGORY)],
                    [["O1", "1", None], ["O1", "2", "x"],
                     ["O2", "1", None], ["O2", "2", "y"]], optional={"note"})
