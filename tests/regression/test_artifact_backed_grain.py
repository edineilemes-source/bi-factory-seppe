"""Sprint 4.4.7 regressions for cold, artifact-backed Grain resume."""

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from app.components.grain_discovery_view import render_grain_discovery, run_grain_discovery
from app.session_state import (initialize_session_state, resolve_render_stage,
                               resume_persistent_analysis, select_analysis,
                               resolve_prepared_artifact_for_analysis)
from core.grain.artifact_discovery import GRAIN_ENGINE_VERSION
from core.persistence.models import AnalysisStage
from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.prepared.artifact_reader import PreparedDatasetArtifactReader


ANALYSIS_ID = "ca5cf2d7-98d8-4404-a5cd-916eda0810db"
DATABASE = Path("storage/bi_factory.sqlite3")


def cold_state():
    repository = SQLiteAnalysisRepository(DATABASE)
    record = repository.get_analysis(ANALYSIS_ID)
    if record is None:
        pytest.skip("real homologation analysis unavailable")
    state = {}
    initialize_session_state(state)
    select_analysis(state, ANALYSIS_ID, record.source_document_id)
    resume_persistent_analysis(state, repository, ANALYSIS_ID)
    return state, repository


def reader_for(state):
    artifact = state["current_prepared_artifact"]
    return PreparedDatasetArtifactReader(
        artifact, analysis_id=state["analysis_id"],
        prepared_dataset_id=state["current_prepared_dataset_id"],
        source_document_id=state["source_document_id"], version=2,
        fingerprint=artifact.fingerprint)


def test_cold_resume_has_only_v2_reference_and_can_reuse_grain_without_xlsx():
    state, repository = cold_state()
    versions_before = len(repository.list_prepared_datasets(ANALYSIS_ID))
    assert state["current_prepared_dataset"] is None
    with patch("core.ingestion.file_loader.load_workspace_file",
               side_effect=AssertionError("XLSX fallback forbidden")):
        report = run_grain_discovery(state)
    assert resolve_render_stage(state) == AnalysisStage.GRAIN_DISCOVERY
    assert state["current_prepared_artifact"].version == 2
    assert report.engine_version == GRAIN_ENGINE_VERSION
    assert state["grain_report_reused"] is True
    assert len(repository.list_prepared_datasets(ANALYSIS_ID)) == versions_before


def test_reader_streams_metadata_selected_chunks_without_materializing_rows():
    state, _ = cold_state()
    reader = reader_for(state)
    chunks = reader.iter_chunks(chunk_size=17, columns={"source_row_id", "Nº Empenho"})
    first = next(chunks)
    assert len(first) == 17
    assert set(first[0]) == {"source_row_id", "Nº Empenho"}
    assert not hasattr(reader, "rows")


def test_reader_rejects_wrong_ownership_version_and_fingerprint():
    state, _ = cold_state()
    artifact = state["current_prepared_artifact"]
    common = dict(artifact=artifact, analysis_id=ANALYSIS_ID,
                  prepared_dataset_id=artifact.prepared_dataset_id,
                  source_document_id=artifact.source_document_id,
                  version=artifact.version, fingerprint=artifact.fingerprint)
    for changed in ({"analysis_id": "other"}, {"version": 1}, {"fingerprint": "0" * 64}):
        with pytest.raises(ValueError, match="ownership/version/fingerprint"):
            PreparedDatasetArtifactReader(**(common | changed))


def test_reader_rejects_corrupt_csv(tmp_path):
    state, _ = cold_state()
    artifact = state["current_prepared_artifact"]
    corrupt = tmp_path / "prepared.csv"
    corrupt.write_bytes(Path(artifact.artifact_location).read_bytes()[:1024])
    changed = artifact.model_copy(update={"artifact_location": str(corrupt)})
    with pytest.raises(ValueError, match="tamanho do artefato"):
        PreparedDatasetArtifactReader(
            changed, analysis_id=artifact.analysis_id,
            prepared_dataset_id=artifact.prepared_dataset_id,
            source_document_id=artifact.source_document_id, version=artifact.version,
            fingerprint=artifact.fingerprint)


def test_real_component_renders_grain_in_cold_session(monkeypatch):
    state, _ = cold_state()
    rendered = []
    monkeypatch.setattr("app.components.grain_discovery_view.st.markdown", rendered.append)
    monkeypatch.setattr("app.components.grain_discovery_view.st.write", lambda *a, **k: None)
    monkeypatch.setattr("app.components.grain_discovery_view.st.info", lambda *a, **k: None)
    monkeypatch.setattr("app.components.grain_discovery_view.st.metric", lambda *a, **k: None)
    monkeypatch.setattr("app.components.grain_discovery_view.st.caption", lambda *a, **k: None)
    monkeypatch.setattr("app.components.grain_discovery_view.st.warning", lambda *a, **k: None)
    monkeypatch.setattr("app.components.grain_discovery_view.st.button", lambda *a, **k: False)
    monkeypatch.setattr("app.components.grain_discovery_view.st.columns",
                        lambda n: [type("C", (), {"metric": lambda *a, **k: None,
                                                  "button": lambda *a, **k: False})() for _ in range(n)])
    monkeypatch.setattr("app.components.grain_discovery_view.st.selectbox",
                        lambda label, values: values[0] if values else None)
    monkeypatch.setattr("app.components.grain_discovery_view.st.text_area", lambda *a, **k: "")
    monkeypatch.setattr("app.components.grain_discovery_view.st.text_input", lambda *a, **k: "")
    monkeypatch.setattr("app.components.grain_discovery_view.st.download_button", lambda *a, **k: False)
    class Expander:
        def __enter__(self): return self
        def __exit__(self, *args): return False
    monkeypatch.setattr("app.components.grain_discovery_view.st.expander", lambda *a, **k: Expander())
    render_grain_discovery(state)
    assert "## GRÃO ANALÍTICO" in rendered
    assert state["current_prepared_dataset"] is None


def test_source_sha_and_artifact_identity_are_stable():
    state, _ = cold_state()
    source = Path("storage/originals/rela de pagos PMCG 10 ago 2026.xlsx")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    assert reader_for(state).artifact.prepared_dataset_id == "8d60c32c-2363-4f48-80be-d108f8bcae80"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_compatible_report_reuse_is_deterministic_and_immutable():
    state, repository = cold_state()
    before = len(repository.list_grain_discovery_reports(
        state["current_prepared_dataset_id"]))
    first = run_grain_discovery(state)
    state["current_grain_report"] = None
    second = run_grain_discovery(state)
    after = len(repository.list_grain_discovery_reports(
        state["current_prepared_dataset_id"]))
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert before == after
    assert state["grain_report_reused"] is True


def test_persistence_resolver_recovers_when_session_artifact_cache_is_empty():
    state, _ = cold_state()
    state["current_prepared_artifact"] = None
    state["current_prepared_dataset_id"] = None
    artifact = resolve_prepared_artifact_for_analysis(state)
    assert artifact.prepared_dataset_id == "8d60c32c-2363-4f48-80be-d108f8bcae80"
    assert artifact.version == 2
    assert state["current_prepared_artifact"] is artifact


def test_real_streamlit_history_button_resolves_and_renders_grain_without_error_banner():
    """Exercise the same app/main.py widget callback used in manual homologation."""
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file("streamlit_app.py", default_timeout=240).run(timeout=240)
    button = next(item for item in app.button
                  if item.key == f"continue_workspace_{ANALYSIS_ID}")
    button.click().run(timeout=240)

    assert not app.exception
    assert not app.error
    assert any(item.value == "## GRÃO ANALÍTICO" for item in app.markdown)
    assert app.session_state["current_analysis_stage"] == AnalysisStage.GRAIN_DISCOVERY
    assert app.session_state["current_prepared_artifact"].version == 2
    assert app.session_state["current_grain_report"].engine_version == GRAIN_ENGINE_VERSION
