"""Regression coverage for the artifact-backed Prepared -> Grain route."""

import hashlib
from pathlib import Path

import pytest

from app.session_state import (
    initialize_session_state, resolve_render_stage, resume_persistent_analysis,
    select_analysis, transition_prepared_to_grain, validate_grain_prepared_artifact,
)
from core.persistence.models import AnalysisStage
from core.persistence.sqlite_repository import SQLiteAnalysisRepository


REAL_ANALYSIS_ID = "ca5cf2d7-98d8-4404-a5cd-916eda0810db"
REAL_SOURCE = Path("storage/originals/rela de pagos PMCG 10 ago 2026.xlsx")


def _real_state():
    repository = SQLiteAnalysisRepository(Path("storage/bi_factory.sqlite3"))
    record = repository.get_analysis(REAL_ANALYSIS_ID)
    if record is None:
        pytest.skip("real analysis fixture is not present")
    state = {}
    initialize_session_state(state)
    select_analysis(state, record.analysis_id, record.source_document_id)
    resume_persistent_analysis(state, repository, record.analysis_id)
    return state, repository


def test_resume_real_analysis_routes_directly_to_grain_with_v2_artifact():
    state, _ = _real_state()
    artifact = validate_grain_prepared_artifact(state)

    assert state["analysis_id"] == REAL_ANALYSIS_ID
    assert state["current_analysis_stage"] == AnalysisStage.GRAIN_DISCOVERY
    assert state["last_successful_stage"] == AnalysisStage.PREPARED_DATASET
    assert resolve_render_stage(state) == AnalysisStage.GRAIN_DISCOVERY
    assert artifact.version == 2
    assert artifact.row_count == 181476
    assert artifact.field_count == 38
    assert artifact.status.value == "READY_WITH_WARNINGS"


def test_transition_preserves_analysis_and_prepared_version_and_synchronizes_state():
    state, repository = _real_state()
    artifact = state["current_prepared_artifact"]
    before_versions = [(item.prepared_dataset_id, item.version)
                       for item in repository.list_prepared_datasets(REAL_ANALYSIS_ID)]
    state["current_analysis_stage"] = AnalysisStage.PREPARED_DATASET
    state["last_successful_stage"] = AnalysisStage.QUALITY

    assert transition_prepared_to_grain(state) == AnalysisStage.GRAIN_DISCOVERY

    assert state["analysis_id"] == state["current_analysis_id"] == REAL_ANALYSIS_ID
    assert state["selected_analysis_id"] == REAL_ANALYSIS_ID
    assert state["last_successful_stage"] == AnalysisStage.PREPARED_DATASET
    assert state["current_prepared_artifact"] is artifact
    assert artifact.version == 2
    assert before_versions == [(item.prepared_dataset_id, item.version)
                               for item in repository.list_prepared_datasets(REAL_ANALYSIS_ID)]


def test_grain_router_never_silently_falls_back_to_prepared():
    state, _ = _real_state()
    state["current_prepared_artifact"] = None

    assert resolve_render_stage(state) == AnalysisStage.GRAIN_DISCOVERY
    assert state["current_analysis_stage"] == AnalysisStage.GRAIN_DISCOVERY
    assert state["current_prepared_artifact"].version == 2


def test_artifact_ownership_rejects_analysis_document_and_fingerprint_mismatch():
    state, _ = _real_state()
    artifact = state["current_prepared_artifact"]
    original_analysis = artifact.analysis_id
    artifact.analysis_id = "another-analysis"
    with pytest.raises(ValueError, match="outra análise"):
        validate_grain_prepared_artifact(state)
    artifact.analysis_id = original_analysis

    original_source = artifact.source_document_id
    artifact.source_document_id = "sha256:another-document"
    with pytest.raises(ValueError, match="outro documento"):
        validate_grain_prepared_artifact(state)
    artifact.source_document_id = original_source

    original_fingerprint = artifact.fingerprint
    artifact.fingerprint = "0" * 64
    with pytest.raises(ValueError, match="fingerprint incompatível"):
        validate_grain_prepared_artifact(state)
    artifact.fingerprint = original_fingerprint


def test_restart_rehydrates_same_grain_stage_and_source_is_immutable():
    before = hashlib.sha256(REAL_SOURCE.read_bytes()).hexdigest()
    first, repository = _real_state()
    restarted = {}
    initialize_session_state(restarted)
    select_analysis(restarted, first["analysis_id"], first["source_document_id"])
    resume_persistent_analysis(restarted, repository, first["analysis_id"])

    assert resolve_render_stage(restarted) == AnalysisStage.GRAIN_DISCOVERY
    assert restarted["analysis_id"] == REAL_ANALYSIS_ID
    assert restarted["current_prepared_artifact"].version == 2
    assert hashlib.sha256(REAL_SOURCE.read_bytes()).hexdigest() == before
