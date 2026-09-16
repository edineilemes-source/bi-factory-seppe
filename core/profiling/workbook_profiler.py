"""Workbook and sheet profiling orchestration."""

from collections import Counter
from typing import Any

from core.ingestion.file_loader import LoadedSheet, LoadedWorkbook
from core.profiling.field_profiler import profile_field
from core.profiling.heuristics import (
    classify_sheet,
    detect_header_row,
    is_empty,
    make_unique_names,
    normalize_name,
)
from core.profiling.models import (
    ProjectContext,
    SheetProfile,
    StructuralWarning,
    WorkbookProfile,
    WorkbookSummary,
)


def _row_is_empty(row: list[Any], width: int) -> bool:
    return all(is_empty(row[index] if index < len(row) else None) for index in range(width))


def _profile_sheet(sheet: LoadedSheet) -> SheetProfile:
    width = max(
        sheet.approximate_column_count,
        max((len(row) for row in sheet.rows), default=0),
    )
    warnings: list[StructuralWarning] = []
    empty_rows = [
        index + 1 for index, row in enumerate(sheet.rows) if _row_is_empty(row, width)
    ]
    empty_columns = [
        index + 1
        for index in range(width)
        if all(is_empty(row[index] if index < len(row) else None) for row in sheet.rows)
    ]
    if empty_rows:
        warnings.append(
            StructuralWarning(
                code="fully_empty_rows",
                message=f"{len(empty_rows)} linha(s) totalmente vazia(s) na amostra.",
                sheet_name=sheet.name,
            )
        )
    if empty_columns:
        warnings.append(
            StructuralWarning(
                code="fully_empty_columns",
                message=f"{len(empty_columns)} coluna(s) totalmente vazia(s) na amostra.",
                sheet_name=sheet.name,
            )
        )

    header_index = detect_header_row(sheet.rows)
    if header_index is None:
        warnings.append(
            StructuralWarning(
                code="missing_probable_header",
                message="Não foi possível identificar um cabeçalho provável.",
                sheet_name=sheet.name,
            )
        )
        raw_headers = [f"campo_{index + 1}" for index in range(width)]
        data_rows = sheet.rows
    else:
        header = sheet.rows[header_index]
        raw_headers = [
            "" if index >= len(header) or is_empty(header[index]) else str(header[index]).strip()
            for index in range(width)
        ]
        data_rows = sheet.rows[header_index + 1 :]

    missing_indexes = [index + 1 for index, name in enumerate(raw_headers) if not name]
    for index in missing_indexes:
        warnings.append(
            StructuralWarning(
                code="unnamed_field",
                message=f"Campo sem nome na coluna {index}.",
                sheet_name=sheet.name,
            )
        )
        raw_headers[index - 1] = f"campo_{index}"

    header_counts = Counter(name.casefold() for name in raw_headers)
    duplicate_names = sorted(name for name, count in header_counts.items() if count > 1)
    if duplicate_names:
        warnings.append(
            StructuralWarning(
                code="duplicate_headers",
                message="Cabeçalhos duplicados: " + ", ".join(duplicate_names),
                sheet_name=sheet.name,
            )
        )

    technical_names = make_unique_names(
        [normalize_name(name, fallback=f"campo_{index + 1}") for index, name in enumerate(raw_headers)]
    )
    fields = []
    for index, (original_name, technical_name) in enumerate(zip(raw_headers, technical_names)):
        values = [row[index] if index < len(row) else None for row in data_rows]
        field = profile_field(
            original_name, technical_name, values, sheet_name=sheet.name
        )
        fields.append(field)
        warnings.extend(field.warnings)

    approximate_data_rows = max(
        0,
        sheet.approximate_row_count - (header_index + 1 if header_index is not None else 0),
    )
    return SheetProfile(
        name=sheet.name,
        role_hypothesis=classify_sheet(sheet.name, approximate_data_rows, width),
        approximate_row_count=approximate_data_rows,
        column_count=width,
        sampled_data_row_count=len(data_rows),
        sampling_strategy=sheet.sampling_strategy,
        probable_header_row=header_index + 1 if header_index is not None else None,
        fully_empty_rows=empty_rows,
        fully_empty_columns=empty_columns,
        fields=fields,
        warnings=warnings,
    )


def profile_workbook(
    workbook: LoadedWorkbook, context: ProjectContext | None = None
) -> WorkbookProfile:
    """Generate the complete technical diagnosis for a loaded workbook."""
    sheets = [_profile_sheet(sheet) for sheet in workbook.sheets]
    warnings = [warning for sheet in sheets for warning in sheet.warnings]
    summary = WorkbookSummary(
        sheet_count=len(sheets),
        total_approximate_rows=sum(sheet.approximate_row_count for sheet in sheets),
        total_columns=sum(sheet.column_count for sheet in sheets),
        warning_count=len(warnings),
    )
    return WorkbookProfile(
        context=context or ProjectContext(),
        original_name=workbook.original_name,
        source_type=workbook.source_type,
        size_bytes=workbook.size_bytes,
        file_type=workbook.file_type,
        summary=summary,
        sheets=sheets,
        warnings=warnings,
    )
