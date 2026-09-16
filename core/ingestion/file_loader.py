"""Safe in-memory loading for supported tabular files."""

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterator
from typing import Any, Literal

from python_calamine import CalamineWorkbook


SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm", ".csv"}
DEFAULT_SAMPLE_ROWS = 10_000
DEFAULT_ORIGINALS_DIRECTORY = Path("storage/originals")
SourceType = Literal["browser_upload", "workspace"]
SAMPLING_STRATEGY = "distributed_deterministic"


@dataclass(frozen=True)
class LoadedSheet:
    """Raw sampled values plus source dimensions for one table."""

    name: str
    rows: list[list[Any]]
    approximate_row_count: int
    approximate_column_count: int
    sampling_strategy: str = SAMPLING_STRATEGY


def distributed_sample_rows(rows: Any, total_rows: int, limit: int) -> list[list[Any]]:
    """Select deterministic rows across the source, retaining header candidates."""
    if total_rows <= limit:
        return [list(row) for row in rows]
    prefix_count = min(25, limit, total_rows)
    selected = set(range(prefix_count))
    remaining = limit - prefix_count
    available = total_rows - prefix_count
    if remaining > 0:
        # Midpoint selection per equal-width bucket covers middle and final regions.
        for bucket in range(remaining):
            index = prefix_count + ((2 * bucket + 1) * available // (2 * remaining))
            selected.add(min(index, total_rows - 1))
        selected.add(total_rows - 1)
        while len(selected) > limit:
            selected.remove(max(index for index in selected if index != total_rows - 1))
    return [list(row) for index, row in enumerate(rows) if index in selected]


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
    file_name: str, data: bytes, source_type: SourceType, sample_rows: int | None
) -> LoadedWorkbook:
    text = _decode_csv(data)
    stream = io.StringIO(text, newline="")
    preview = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(preview, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(stream, dialect)
    total_rows = 0
    max_columns = 0
    for row in reader:
        total_rows += 1
        max_columns = max(max_columns, len(row))
    stream.seek(0)
    reader = csv.reader(stream, dialect)
    rows = distributed_sample_rows(reader, total_rows, sample_rows or total_rows)
    return LoadedWorkbook(
        original_name=file_name,
        source_type=source_type,
        size_bytes=len(data),
        file_type="csv",
        sheets=[LoadedSheet(Path(file_name).stem, rows, total_rows, max_columns)],
    )


def _load_excel(
    file_name: str, data: bytes, source_type: SourceType, sample_rows: int | None
) -> LoadedWorkbook:
    sheets: list[LoadedSheet] = []
    with CalamineWorkbook.from_filelike(io.BytesIO(data)) as workbook:
        for sheet_name in workbook.sheet_names:
            sheet = workbook.get_sheet_by_name(sheet_name)
            rows = distributed_sample_rows(
                sheet.iter_rows(), sheet.total_height, sample_rows or sheet.total_height
            )
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
    sample_rows: int | None = DEFAULT_SAMPLE_ROWS,
    source_type: SourceType = "browser_upload",
) -> LoadedWorkbook:
    """Validate and load a supported upload without modifying or persisting it."""
    extension = Path(file_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Formato não suportado. Envie um arquivo XLSX, XLSM ou CSV.")
    if not data:
        raise ValueError("O arquivo enviado está vazio.")
    if sample_rows is not None and sample_rows < 2:
        raise ValueError("A amostra deve permitir ao menos duas linhas.")
    if extension == ".csv":
        return _load_csv(file_name, data, source_type, sample_rows)
    return _load_excel(file_name, data, source_type, sample_rows)


def load_complete_tabular_file(
    file_name: str, data: bytes, source_type: SourceType = "browser_upload",
) -> LoadedWorkbook:
    """Load every source row for final preparation (profiling may remain sampled)."""
    return load_tabular_file(file_name, data, sample_rows=None, source_type=source_type)


@dataclass(frozen=True)
class TabularChunk:
    sheet_name: str
    rows: list[list[Any]]
    start_row_index: int
    total_rows: int | None
    total_columns: int


def iter_tabular_chunks(file_name: str, data: bytes, *, chunk_size: int) -> Iterator[TabularChunk]:
    """Yield source rows once without materializing the complete workbook."""
    if chunk_size < 1:
        raise ValueError("chunk_size deve ser positivo")
    extension = Path(file_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS or not data:
        raise ValueError("Fonte vazia ou formato não suportado.")
    if extension == ".csv":
        text = _decode_csv(data)
        try:
            dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(io.StringIO(text, newline=""), dialect)
        chunk: list[list[Any]] = []
        start = 0
        width = 0
        for row in reader:
            values = list(row); width = max(width, len(values)); chunk.append(values)
            if len(chunk) == chunk_size:
                yield TabularChunk(Path(file_name).stem, chunk, start, None, width)
                start += len(chunk); chunk = []
        if chunk:
            yield TabularChunk(Path(file_name).stem, chunk, start, None, width)
        return
    with CalamineWorkbook.from_filelike(io.BytesIO(data)) as workbook:
        for sheet_name in workbook.sheet_names:
            sheet = workbook.get_sheet_by_name(sheet_name)
            chunk = []
            start = 0
            for row_index, row in enumerate(sheet.iter_rows()):
                # Calamine may yield a trailing row beyond its declared dimension.
                # The declared height is the deterministic source contract used by profiling.
                if row_index >= sheet.total_height:
                    break
                chunk.append(list(row))
                if len(chunk) == chunk_size:
                    yield TabularChunk(sheet_name, chunk, start, sheet.total_height, sheet.total_width)
                    start += len(chunk); chunk = []
            if chunk:
                yield TabularChunk(sheet_name, chunk, start, sheet.total_height, sheet.total_width)


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
