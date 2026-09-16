import csv
import hashlib
import io
from pathlib import Path

import pandas as pd
import pytest

from app.session_state import initialize_session_state
from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.prepared.generation import generate_prepared_dataset_artifact, verify_prepared_artifact
from core.prepared.models import PreparedGenerationStatus
from core.profiling.field_profiler import profile_field
from core.profiling.models import ProjectContext, SheetProfile, WorkbookProfile, WorkbookSummary
from core.semantic.validation_service import create_validation_report


def _source(rows: int, columns: int = 40) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow([f"F{i}" for i in range(columns)])
    patterns = (
        lambda r: r, lambda r: f"{r}.25", lambda r: f" text {r % 10} ",
        lambda r: f"{r % 1000:05d}", lambda r: "24/08/2026",
        lambda r: "sim" if r % 2 else "não", lambda r: "-" if r % 7 == 0 else "ok",
        lambda r: "" if r % 11 == 0 else "value", lambda r: -r,
        lambda r: f"code-{r % 20}",
    )
    for row in range(rows):
        writer.writerow([patterns[column % len(patterns)](row) for column in range(columns)])
    return stream.getvalue().encode()


def _semantics(rows: int, columns: int = 40, analysis_id: str = "analysis-large"):
    fields = [profile_field(f"F{i}", f"f{i}", [str(i), str(i + 1), str(i + 2)])
              for i in range(columns)]
    profile = WorkbookProfile(
        context=ProjectContext(), original_name="large.csv", source_type="browser_upload",
        size_bytes=1, file_type="csv",
        summary=WorkbookSummary(sheet_count=1, total_approximate_rows=rows,
                                total_columns=columns, warning_count=0),
        sheets=[SheetProfile(name="large", role_hypothesis="A validar",
            approximate_row_count=rows + 1, column_count=columns,
            probable_header_row=1, sampled_data_row_count=min(rows, 100), fields=fields)],
    )
    report = create_validation_report(profile)
    report.analysis_id = analysis_id
    report.source_document_id = "sha256:" + "a" * 64
    return report


def _generate(tmp_path: Path, content: bytes, rows: int, chunk_size: int,
              *, analysis_id="analysis-large", fail_after_chunks=None):
    return generate_prepared_dataset_artifact(
        "large.csv", content, _semantics(rows, analysis_id=analysis_id),
        artifact_root=tmp_path, chunk_size=chunk_size, preview_rows=10,
        fail_after_chunks=fail_after_chunks,
    )


@pytest.mark.slow
def test_200k_generation_row_field_source_and_sparse_lineage(tmp_path):
    content = _source(200_000)
    before = hashlib.sha256(content).hexdigest()
    artifact = _generate(tmp_path, content, 200_000, 10_000)
    assert artifact.generation_status == PreparedGenerationStatus.COMPLETED
    assert artifact.row_count == artifact.statistics["source_row_count"] == 200_000
    assert artifact.field_count == artifact.statistics["source_field_count"] == 40
    assert hashlib.sha256(content).hexdigest() == before
    assert artifact.total_transformations < artifact.row_count * artifact.field_count
    assert Path(artifact.artifact_location).is_file()
    verify_prepared_artifact(artifact)


def test_chunk_size_independence_ids_values_transformations_and_fingerprint(tmp_path):
    content = _source(2_050)
    artifacts = [_generate(tmp_path / str(size), content, 2_050, size)
                 for size in (1_000, 10_000, 20_000)]
    assert len({item.row_count for item in artifacts}) == 1
    assert len({item.field_count for item in artifacts}) == 1
    assert len({item.total_transformations for item in artifacts}) == 1
    assert len({item.fingerprint for item in artifacts}) == 1
    for index in range(10):
        assert len({item.preview[index]["source_row_id"] for item in artifacts}) == 1
        assert len({tuple(item.preview[index].items()) for item in artifacts}) == 1


def test_partial_failure_is_not_final_and_second_run_recovers(tmp_path):
    content = _source(350)
    statuses = []
    with pytest.raises(RuntimeError, match="chunk 3"):
        generate_prepared_dataset_artifact(
            "large.csv", content, _semantics(350), artifact_root=tmp_path,
            chunk_size=100, fail_after_chunks=3,
            status_callback=lambda status, stage, reason: statuses.append(status),
        )
    assert statuses[-1] == PreparedGenerationStatus.FAILED
    assert list(tmp_path.glob("*.partial"))
    assert not list(tmp_path.glob("*.csv"))
    completed = _generate(tmp_path, content, 350, 100)
    assert completed.generation_status == PreparedGenerationStatus.COMPLETED
    verify_prepared_artifact(completed)


def test_session_contains_only_lightweight_artifact_metadata(tmp_path):
    artifact = _generate(tmp_path, _source(250), 250, 100)
    state = {}; initialize_session_state(state)
    state["current_prepared_dataset"] = None
    state["current_prepared_dataset_id"] = artifact.prepared_dataset_id
    state["current_prepared_artifact"] = artifact
    assert state["current_prepared_dataset"] is None
    assert len(state["current_prepared_artifact"].preview) == 10
    assert not hasattr(state["current_prepared_artifact"], "rows")
    assert not hasattr(state["current_prepared_artifact"], "transformations")


def test_main_generation_never_materializes_dataframe_records(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("full_dataframe.to_dict() proibido")
    monkeypatch.setattr(pd.DataFrame, "to_dict", forbidden)
    artifact = _generate(tmp_path, _source(120), 120, 50)
    assert artifact.row_count == 120


def test_completed_artifact_persistence_reuse_and_interrupted_state(tmp_path):
    database = tmp_path / "state.sqlite3"
    repository = SQLiteAnalysisRepository(database)
    content = _source(50)
    document = repository.register_document(content, "large.csv")
    record = repository.create_analysis(document.source_document_id, _semantics(50).observed_profile)
    artifact = generate_prepared_dataset_artifact(
        "large.csv", content, record.report, artifact_root=tmp_path / "artifacts",
        chunk_size=20, prepared_dataset_id="prepared-reuse")
    repository.update_prepared_generation(
        artifact.prepared_dataset_id, record.analysis_id, artifact.version,
        PreparedGenerationStatus.RUNNING, "WRITE")
    repository.save_prepared_artifact(artifact)
    restored = repository.get_prepared_artifact(artifact.prepared_dataset_id)
    assert restored is not None and restored.fingerprint == artifact.fingerprint
    verify_prepared_artifact(restored)
    repository.update_prepared_generation(
        "stale", record.analysis_id, 2, PreparedGenerationStatus.RUNNING, "WRITE")
    assert repository.mark_stale_prepared_generations_interrupted() == 1


def test_corrupt_artifact_is_detected(tmp_path):
    artifact = _generate(tmp_path, _source(80), 80, 25)
    with Path(artifact.artifact_location).open("a", encoding="utf-8") as stream:
        stream.write("corrupt")
    with pytest.raises(ValueError, match="artefato Prepared diverge"):
        verify_prepared_artifact(artifact)
