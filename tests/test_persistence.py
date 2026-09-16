"""Persistence and restart behavior for Sprint 1.4."""

import sqlite3
from pathlib import Path

from app.session_state import resume_persistent_analysis, save_semantic_answer, start_persistent_analysis
from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.profiling.field_profiler import profile_field
from core.profiling.models import ProjectContext, SheetProfile, WorkbookProfile, WorkbookSummary
from core.quality.models import (DataQualityReport, FieldIdentity, QualityIssue,
                                 QualityIssueType, QualitySeverity, QualityStatus,
                                 ReconciliationCandidate, ValueLayer)
from core.semantic.models import AnalysisStatus, QuestionStatus
from core.semantic.question_generator import ROLE_LABELS, UNKNOWN_OPTION


def _profile() -> WorkbookProfile:
    fields = [
        profile_field("Identificador", "identificador", [1, 1, 1, 2, 2, 2]),
        profile_field("Campo X", "campo_x", ["abc", "def", "ghi"]),
    ]
    return WorkbookProfile(
        context=ProjectContext(), original_name="persistente.csv",
        source_type="browser_upload", size_bytes=20, file_type="csv",
        summary=WorkbookSummary(
            sheet_count=1, total_approximate_rows=4,
            total_columns=len(fields), warning_count=0,
        ),
        sheets=[SheetProfile(
            name="Dados", role_hypothesis="A validar", approximate_row_count=4,
            column_count=len(fields), sampled_data_row_count=4, fields=fields,
        )],
    )


def test_document_identity_uses_content_hash_not_filename(tmp_path: Path) -> None:
    repository = SQLiteAnalysisRepository(tmp_path / "analysis.sqlite3")
    first = repository.register_document(b"same content", "first.csv")
    renamed = repository.register_document(b"same content", "renamed.csv")
    different = repository.register_document(b"different content", "first.csv")
    assert first.source_document_id.startswith("sha256:")
    assert renamed.source_document_id == first.source_document_id
    assert different.source_document_id != first.source_document_id


def test_document_supports_multiple_analysis_ids(tmp_path: Path) -> None:
    repository = SQLiteAnalysisRepository(tmp_path / "analysis.sqlite3")
    document = repository.register_document(b"content", "data.csv")
    first = repository.create_analysis(document.source_document_id, _profile())
    second = repository.create_analysis(document.source_document_id, _profile())
    assert first.analysis_id != second.analysis_id
    assert len(repository.list_analyses(document.source_document_id)) == 2


def test_answer_survives_repository_and_ui_restart(tmp_path: Path) -> None:
    database = tmp_path / "analysis.sqlite3"
    repository = SQLiteAnalysisRepository(database)
    document = repository.register_document(b"content", "data.csv")
    record = repository.create_analysis(document.source_document_id, _profile())
    question = record.report.questions[0]
    repository.save_answer(
        record.analysis_id, question.question_id,
        ROLE_LABELS[question.current_hypothesis],
    )

    restarted_repository = SQLiteAnalysisRepository(database)
    restarted_state: dict = {}
    resumed = resume_persistent_analysis(
        restarted_state, restarted_repository, record.analysis_id,
    )
    restored_question = next(
        q for q in resumed.report.questions if q.question_id == question.question_id
    )
    assert restored_question.status == QuestionStatus.ANSWERED
    assert question.question_id in restarted_state["semantic_answers"]
    current = resumed.report.questions[restarted_state["current_question_index"]]
    assert current.status == QuestionStatus.PENDING


def test_last_answer_completes_and_unresolved_is_explicit(tmp_path: Path) -> None:
    repository = SQLiteAnalysisRepository(tmp_path / "analysis.sqlite3")
    state: dict = {}
    record = start_persistent_analysis(
        state, repository, b"content", "data.csv", _profile,
    )
    first, second = record.report.questions
    save_semantic_answer(state, first.question_id, ROLE_LABELS[first.current_hypothesis])
    save_semantic_answer(state, second.question_id, UNKNOWN_OPTION)
    persisted = repository.get_analysis(record.analysis_id)
    assert persisted is not None
    assert persisted.status == AnalysisStatus.COMPLETED_WITH_UNRESOLVED
    assert all(q.status != QuestionStatus.PENDING for q in persisted.report.questions)


def test_sqlite_has_normalized_analysis_question_and_answer_tables(tmp_path: Path) -> None:
    database = tmp_path / "analysis.sqlite3"
    SQLiteAnalysisRepository(database)
    with sqlite3.connect(database) as connection:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert {"source_documents", "analyses", "semantic_questions", "semantic_answers"} <= tables


def test_future_value_lineage_preserves_source_and_separates_identifiers() -> None:
    values = ValueLayer(source_value=" 001 ", normalized_value="001", validated_value="1")
    identity = FieldIdentity(
        source_document_id="sha256:x", analysis_id="analysis-x",
        source_field_id="Dados::codigo", technical_key="row-1",
        business_identifier="001", business_key=None,
    )
    candidate = ReconciliationCandidate(
        candidate_id="candidate-x", analysis_id=identity.analysis_id,
        source_field_id=identity.source_field_id, source_value=values.source_value,
        normalized_value=values.normalized_value,
    )
    assert values.source_value == " 001 "
    assert identity.technical_key != identity.business_identifier
    assert identity.business_key is None
    assert candidate.proposed_validated_value is None


def test_quality_report_survives_repository_restart(tmp_path: Path) -> None:
    database = tmp_path / "analysis.sqlite3"
    repository = SQLiteAnalysisRepository(database)
    document = repository.register_document(b"quality-content", "quality.csv")
    analysis = repository.create_analysis(document.source_document_id, _profile())
    report = DataQualityReport(
        analysis_id=analysis.analysis_id, status=QualityStatus.COMPLETED_WITH_ISSUES,
        total_rows=4, total_fields=2, score=87.5, issues_count=1,
        warning_count=1, affected_rows=1,
        issues=[QualityIssue(
            issue_id="qi:persisted", analysis_id=analysis.analysis_id,
            source_field_id="Dados::campo_x", issue_type=QualityIssueType.PLACEHOLDER_VALUE,
            severity=QualitySeverity.WARNING, source_value="-", examples=["-"],
            reason="Placeholder agrupado.")],
    )
    repository.save_quality_report(report)
    restarted = SQLiteAnalysisRepository(database)
    restored = restarted.get_quality_report(analysis.analysis_id)
    assert restored is not None
    assert restored.score == 87.5
    assert restored.issues[0].source_value == "-"

    state: dict = {}
    resume_persistent_analysis(state, restarted, analysis.analysis_id)
    assert state["current_quality_report"] == restored
