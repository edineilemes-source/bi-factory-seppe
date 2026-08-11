"""Tests for browser and workspace tabular sources."""

from pathlib import Path

import pytest

from core.ingestion.file_loader import (
    LoadedWorkbook,
    discover_workspace_files,
    load_tabular_file,
    load_workspace_file,
)
from core.profiling.workbook_profiler import profile_workbook


def test_discover_workspace_files_includes_only_supported_extensions(
    tmp_path: Path,
) -> None:
    (tmp_path / "dados.csv").write_text("id,nome\n1,Ana\n", encoding="utf-8")
    (tmp_path / "PLANILHA.XLSX").write_bytes(b"conteudo")
    (tmp_path / "macros.xlsm").write_bytes(b"conteudo")
    (tmp_path / "notas.txt").write_text("ignorar", encoding="utf-8")
    (tmp_path / "arquivo.xls").write_bytes(b"ignorar")
    (tmp_path / "pasta.csv").mkdir()

    discovered = discover_workspace_files(tmp_path)

    assert [path.name for path in discovered] == [
        "dados.csv",
        "macros.xlsm",
        "PLANILHA.XLSX",
    ]


def test_source_metadata_identifies_browser_and_workspace(tmp_path: Path) -> None:
    data = b"id,nome\n1,Ana\n"
    local_file = tmp_path / "dados.csv"
    local_file.write_bytes(data)

    browser = load_tabular_file("upload.csv", data)
    workspace = load_workspace_file(local_file, tmp_path)

    assert (browser.original_name, browser.source_type, browser.size_bytes) == (
        "upload.csv",
        "browser_upload",
        len(data),
    )
    assert (workspace.original_name, workspace.source_type, workspace.size_bytes) == (
        "dados.csv",
        "workspace",
        len(data),
    )


@pytest.mark.parametrize("source_type", ["browser_upload", "workspace"])
def test_profiler_receives_same_loaded_workbook_interface(source_type: str) -> None:
    workbook = load_tabular_file(
        "dados.csv",
        b"id,nome\n1,Ana\n",
        source_type=source_type,
    )

    assert isinstance(workbook, LoadedWorkbook)
    profile = profile_workbook(workbook)
    assert profile.source_type == source_type
    assert profile.original_name == "dados.csv"
