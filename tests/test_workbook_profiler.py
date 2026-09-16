"""Tests for workbook loading and structural warnings."""

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from core.ingestion.file_loader import LoadedSheet, LoadedWorkbook, load_tabular_file
from core.ingestion.file_loader import distributed_sample_rows
from core.profiling.workbook_profiler import profile_workbook


def _small_xlsx() -> bytes:
    """Build a minimal OOXML workbook without adding a test-only dependency."""
    files = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Base" sheetId="1" r:id="rId1"/></sheets></workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:C3"/><sheetData>
<row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c><c r="B1" t="inlineStr"><is><t>Nome</t></is></c><c r="C1" t="inlineStr"><is><t>Valor</t></is></c></row>
<row r="2"><c r="A2"><v>1</v></c><c r="B2" t="inlineStr"><is><t>Ana</t></is></c><c r="C2"><v>10.5</v></c></row>
<row r="3"><c r="A3"><v>2</v></c><c r="B3" t="inlineStr"><is><t>Bruno</t></is></c><c r="C3"><v>20</v></c></row>
</sheetData></worksheet>""",
    }
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return output.getvalue()


def test_load_and_profile_small_workbook() -> None:
    workbook = load_tabular_file("amostra.xlsx", _small_xlsx())
    profile = profile_workbook(workbook)

    assert workbook.sheets[0].name == "Base"
    assert profile.summary.sheet_count == 1
    assert profile.sheets[0].probable_header_row == 1
    assert [field.technical_name for field in profile.sheets[0].fields] == [
        "id",
        "nome",
        "valor",
    ]


def test_structural_warnings_are_aggregated() -> None:
    workbook = LoadedWorkbook(
        original_name="alertas.csv",
        source_type="browser_upload",
        size_bytes=20,
        file_type="csv",
        sheets=[
            LoadedSheet(
                name="Dados",
                rows=[
                    ["Código", "Código", "", "Observação"],
                    [1, 1, None, None],
                    [None, None, None, None],
                    [2, 2, None, "texto"],
                ],
                approximate_row_count=4,
                approximate_column_count=4,
            )
        ],
    )

    profile = profile_workbook(workbook)
    codes = {warning.code for warning in profile.warnings}

    assert "fully_empty_rows" in codes
    assert "fully_empty_columns" in codes
    assert "duplicate_headers" in codes
    assert "unnamed_field" in codes


def test_distributed_sampling_covers_source_and_is_deterministic() -> None:
    rows = [[index] for index in range(50_000)]
    first = distributed_sample_rows(iter(rows), len(rows), 10_000)
    second = distributed_sample_rows(iter(rows), len(rows), 10_000)
    sampled = {row[0] for row in first}
    assert first == second
    assert len(first) == 10_000
    assert 0 in sampled and 49_999 in sampled
    assert any(20_000 <= value <= 30_000 for value in sampled)
