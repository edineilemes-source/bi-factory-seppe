from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from app.main import history_actions
from app.session_state import resume_persistent_analysis, select_analysis
from core.persistence.models import AnalysisHistoryItem, AnalysisStage
from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.quality.models import DataQualityReport, QualityStatus
from core.semantic.models import AnalysisStatus, QuestionStatus
from core.semantic.question_generator import ROLE_LABELS
from tests.test_persistence import _profile


def _complete_semantic(repository, record):
    for question in record.report.questions:
        record = repository.save_answer(
            record.analysis_id, question.question_id,
            ROLE_LABELS[question.current_hypothesis],
        )
    return record


def _quality_complete(repository, record):
    repository.save_quality_report(DataQualityReport(
        analysis_id=record.analysis_id, status=QualityStatus.COMPLETED,
    ))


def test_one_analysis_is_explicit_and_resumes_exact_id(tmp_path):
    repository = SQLiteAnalysisRepository(tmp_path / "history.sqlite3")
    document = repository.register_document(b"one", "one.csv")
    record = repository.create_analysis(document.source_document_id, _profile())
    history = repository.list_analyses_for_document(document.source_document_id)
    assert [item.analysis_id for item in history] == [record.analysis_id]
    state = {}
    select_analysis(state, record.analysis_id, document.source_document_id)
    resume_persistent_analysis(state, repository, record.analysis_id)
    assert state["selected_analysis_id"] == state["current_analysis_id"] == record.analysis_id


def test_six_analyses_all_visible_latest_only_badge_and_no_auto_selection(tmp_path):
    database = tmp_path / "history.sqlite3"
    repository = SQLiteAnalysisRepository(database)
    document = repository.register_document(b"six", "six.csv")
    records = [repository.create_analysis(document.source_document_id, _profile()) for _ in range(6)]
    base = datetime(2026, 8, 24, tzinfo=timezone.utc)
    with sqlite3.connect(database) as connection:
        for index, record in enumerate(records):
            stamp = (base + timedelta(minutes=index)).isoformat()
            connection.execute("UPDATE analyses SET created_at=?,updated_at=? WHERE analysis_id=?",
                               (stamp, stamp, record.analysis_id))
    history = repository.list_analyses_for_document(document.source_document_id)
    assert len(history) == 6
    assert [item.analysis_id for item in history] == [r.analysis_id for r in reversed(records)]
    assert [item.is_latest for item in history] == [True, False, False, False, False, False]
    state = {}
    assert state.get("selected_analysis_id") is None
    assert sum(item.has_unfinished_work for item in history) == 6


def test_quality_complete_prepared_interrupted_stage_detection(tmp_path):
    repository = SQLiteAnalysisRepository(tmp_path / "history.sqlite3")
    document = repository.register_document(b"interrupted", "data.csv")
    recent = _complete_semantic(repository, repository.create_analysis(
        document.source_document_id, _profile()))
    _quality_complete(repository, recent)
    item = repository.list_analyses_for_document(document.source_document_id)[0]
    assert item.current_stage == AnalysisStage.PREPARED_DATASET
    assert item.last_successful_stage == AnalysisStage.QUALITY
    assert item.is_resumable


def test_realistic_recent_prepared_and_old_partial_resume_without_mixing(tmp_path):
    repository = SQLiteAnalysisRepository(tmp_path / "history.sqlite3")
    document = repository.register_document(b"realistic", "data.csv")
    old = repository.create_analysis(document.source_document_id, _profile())
    report = old.report.model_copy(deep=True)
    template = report.questions[0]
    report.questions = [template.model_copy(update={"question_id": f"q-{i}",
                                                       "status": QuestionStatus.PENDING})
                        for i in range(15)]
    report.analysis_status = AnalysisStatus.IN_PROGRESS
    old = repository.save_report(report)
    for question in old.report.questions[:3]:
        repository.save_answer(old.analysis_id, question.question_id,
                               ROLE_LABELS[question.current_hypothesis])
    recent = _complete_semantic(repository, repository.create_analysis(
        document.source_document_id, _profile()))
    _quality_complete(repository, recent)

    recent_result = repository.resume_analysis(recent.analysis_id, document.source_document_id)
    old_result = repository.resume_analysis(old.analysis_id, document.source_document_id)
    assert recent_result.analysis_id == recent.analysis_id
    assert recent_result.current_stage == AnalysisStage.PREPARED_DATASET
    assert old_result.analysis_id == old.analysis_id
    assert old_result.current_stage == AnalysisStage.SEMANTIC_VALIDATION
    state = {}
    select_analysis(state, old.analysis_id, document.source_document_id)
    resume_persistent_analysis(state, repository, old.analysis_id)
    assert state["current_question_index"] == 3
    assert len(state["semantic_questions"]) == 15


def test_wrong_document_and_corrupt_ownership_never_fall_back(tmp_path):
    database = tmp_path / "history.sqlite3"
    repository = SQLiteAnalysisRepository(database)
    first_doc = repository.register_document(b"first", "first.csv")
    second_doc = repository.register_document(b"second", "second.csv")
    first = repository.create_analysis(first_doc.source_document_id, _profile())
    second = repository.create_analysis(second_doc.source_document_id, _profile())
    with pytest.raises(ValueError, match="não pertence"):
        repository.resume_analysis(first.analysis_id, second_doc.source_document_id)
    state = {}
    select_analysis(state, first.analysis_id, first_doc.source_document_id)
    with pytest.raises(ValueError, match="divergem"):
        resume_persistent_analysis(state, repository, second.analysis_id)
    assert state.get("current_analysis_id") is None


def test_completed_action_policy_has_no_continue():
    item = AnalysisHistoryItem(
        analysis_id="complete", source_document_id="sha256:x",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        status="completed", semantic_status="completed",
        current_stage=AnalysisStage.COMPLETED,
        last_successful_stage=AnalysisStage.COMPLETED,
        has_unfinished_work=False, is_completed=True, is_resumable=False,
    )
    assert "continue" not in history_actions(item)
    assert history_actions(item) == ("view", "artifacts")


def test_corrupt_selected_analysis_does_not_resume_another(tmp_path):
    repository = SQLiteAnalysisRepository(tmp_path / "history.sqlite3")
    document = repository.register_document(b"fallback", "fallback.csv")
    healthy = repository.create_analysis(document.source_document_id, _profile())
    missing_id = "analysis-corrupted-or-missing"
    with pytest.raises(ValueError, match=missing_id):
        repository.resume_analysis(missing_id, document.source_document_id)
    assert repository.get_analysis(healthy.analysis_id) is not None


def test_quality_artifact_payload_ownership_is_enforced(tmp_path):
    database = tmp_path / "history.sqlite3"
    repository = SQLiteAnalysisRepository(database)
    document = repository.register_document(b"ownership", "ownership.csv")
    owner = _complete_semantic(repository, repository.create_analysis(
        document.source_document_id, _profile()))
    other = repository.create_analysis(document.source_document_id, _profile())
    _quality_complete(repository, owner)
    with sqlite3.connect(database) as connection:
        payload = DataQualityReport(
            analysis_id=other.analysis_id, status=QualityStatus.COMPLETED,
        ).model_dump_json()
        connection.execute("UPDATE data_quality_reports SET report_json=? WHERE analysis_id=?",
                           (payload, owner.analysis_id))
    with pytest.raises(ValueError, match="quality report pertence a outra análise"):
        repository.resume_analysis(owner.analysis_id, document.source_document_id)
    assert repository.get_analysis(other.analysis_id).analysis_id == other.analysis_id
