"""Safe in-memory loading for supported tabular files."""

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from python_calamine import CalamineWorkbook


SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm", ".csv"}
DEFAULT_SAMPLE_ROWS = 10_000
DEFAULT_ORIGINALS_DIRECTORY = Path("storage/originals")
SourceType = Literal["browser_upload", "workspace"]


@dataclass(frozen=True)
class LoadedSheet:
    """Raw sampled values plus source dimensions for one table."""

    name: str
    rows: list[list[Any]]
    approximate_row_count: int
    approximate_column_count: int


@dataclass(frozen=True)
class LoadedWorkbook:
    """In-memory representation consumed by the profiler."""

    original_name: str
    source_type: SourceType
    size_bytes: int
    file_type: str
    sheets: list[LoadedSheet]


def _decode_csv(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Não foi possível identificar a codificação do CSV.")


def _load_csv(
    file_name: str, data: bytes, source_type: SourceType, sample_rows: int
) -> LoadedWorkbook:
    text = _decode_csv(data)
    stream = io.StringIO(text, newline="")
    preview = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(preview, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(stream, dialect)
    rows: list[list[str]] = []
    total_rows = 0
    max_columns = 0
    for row in reader:
        total_rows += 1
        max_columns = max(max_columns, len(row))
        if len(rows) < sample_rows:
            rows.append(row)
    return LoadedWorkbook(
        original_name=file_name,
        source_type=source_type,
        size_bytes=len(data),
        file_type="csv",
        sheets=[LoadedSheet(Path(file_name).stem, rows, total_rows, max_columns)],
    )


def _load_excel(
    file_name: str, data: bytes, source_type: SourceType, sample_rows: int
) -> LoadedWorkbook:
    sheets: list[LoadedSheet] = []
    with CalamineWorkbook.from_filelike(io.BytesIO(data)) as workbook:
        for sheet_name in workbook.sheet_names:
            sheet = workbook.get_sheet_by_name(sheet_name)
            rows = sheet.to_python(skip_empty_area=False, nrows=sample_rows)
            sheets.append(
                LoadedSheet(
                    name=sheet_name,
                    rows=[list(row) for row in rows],
                    approximate_row_count=sheet.total_height,
                    approximate_column_count=sheet.total_width,
                )
            )
    return LoadedWorkbook(
        original_name=file_name,
        source_type=source_type,
        size_bytes=len(data),
        file_type=Path(file_name).suffix.lower().lstrip("."),
        sheets=sheets,
    )


def load_tabular_file(
    file_name: str,
    data: bytes,
    sample_rows: int = DEFAULT_SAMPLE_ROWS,
    source_type: SourceType = "browser_upload",
) -> LoadedWorkbook:
    """Validate and load a supported upload without modifying or persisting it."""
    extension = Path(file_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Formato não suportado. Envie um arquivo XLSX, XLSM ou CSV.")
    if not data:
        raise ValueError("O arquivo enviado está vazio.")
    if sample_rows < 2:
        raise ValueError("A amostra deve permitir ao menos duas linhas.")
    if extension == ".csv":
        return _load_csv(file_name, data, source_type, sample_rows)
    return _load_excel(file_name, data, source_type, sample_rows)


def discover_workspace_files(
    directory: Path = DEFAULT_ORIGINALS_DIRECTORY,
) -> list[Path]:
    """List supported regular files available in the originals directory."""
    if not directory.is_dir():
        return []
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ),
        key=lambda path: path.name.casefold(),
    )


def load_workspace_file(
    path: Path, directory: Path = DEFAULT_ORIGINALS_DIRECTORY
) -> LoadedWorkbook:
    """Read a supported originals file without modifying it."""
    root = directory.resolve()
    candidate = path.resolve()
    if candidate.parent != root:
        raise ValueError("O arquivo deve estar diretamente em storage/originals.")
    if not candidate.is_file() or candidate.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("Formato não suportado. Selecione um arquivo XLSX, XLSM ou CSV.")
    with candidate.open("rb") as source:
        data = source.read()
    return load_tabular_file(candidate.name, data, source_type="workspace")
