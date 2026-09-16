"""Export and current-reanalysis contracts for Sprint 2.1.2."""

import csv
import io
import json
from datetime import datetime, timedelta, timezone

from app.components import data_quality_view
from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.profiling.models import SemanticRole
from core.profiling.workbook_profiler import profile_workbook
from core.quality.export import (
    export_field_summary_csv, export_quality_report_json, quality_report_id,
)
from core.quality.models import (
    DataQualityReport, FieldApplicability, FieldQualityStatus, FieldQualitySummary,
    FieldRequirement, QualityIssue, QualityIssueType, QualitySeverity, QualityStatus,
    ReconciliationCandidate,
)
from tests.golden.fixtures import golden_loaded_workbook


def _report(analysis_id: str, created_at: datetime) -> DataQualityReport:
    return DataQualityReport(
        analysis_id=analysis_id, status=QualityStatus.COMPLETED_WITH_ISSUES,
        created_at=created_at, total_rows=10, total_fields=2, evaluated_fields=1,
        not_evaluated_fields=1, eligible_cells=10, score=91.25,
        observed_completeness=50, issues_count=1, info_count=1,
        field_summaries=[
            FieldQualitySummary(
                source_field_id="Dados::avaliado", sheet_name="Dados",
                field_name="Avaliado", semantic_role=SemanticRole.IDENTIFIER,
                effective_semantic_role=SemanticRole.IDENTIFIER,
                requirement=FieldRequirement.REQUIRED,
                applicability=FieldApplicability.APPLICABLE,
                quality_status=FieldQualityStatus.EVALUATED,
                score=91.25, quality_score=91.25, missing_count=1,
                missing_percentage=10, placeholder_count=0,
                placeholder_percentage=0, observed_completeness=90,
                issues_count=1, affected_count=1, affected_percentage=10,
                maximum_severity=QualitySeverity.INFO,
            ),
            FieldQualitySummary(
                source_field_id="Dados::sem_evidencia", sheet_name="Dados",
                field_name="Sem Evidência", semantic_role=SemanticRole.UNKNOWN,
                effective_semantic_role=SemanticRole.UNKNOWN,
                requirement=FieldRequirement.UNKNOWN,
                applicability=FieldApplicability.UNKNOWN,
                quality_status=FieldQualityStatus.NOT_EVALUATED,
                score=None, quality_score=None, missing_count=10,
                missing_percentage=100, observed_completeness=0,
                issues_count=0, affected_count=0, affected_percentage=0,
            ),
        ],
        issues=[QualityIssue(
            issue_id="qi:export", analysis_id=analysis_id,
            source_field_id="Dados::avaliado", sheet_name="Dados",
            field_name="Avaliado", issue_type=QualityIssueType.MISSING_VALUE,
            severity=QualitySeverity.INFO, affected_count=1,
            affected_percentage=10, examples=[None], row_numbers=[2],
            reason="Ausência observada.", evidence={"quality_defect": False},
            suggested_action="Validar a regra de negócio.",
        )],
        reconciliation_candidates=[ReconciliationCandidate(
            candidate_id="rc:export", analysis_id=analysis_id,
            source_field_id="Dados::avaliado", source_value="001",
            candidate_value="01", reason="Candidato para auditoria.",
        )],
    )


def test_exported_json_matches_persisted_report(tmp_path):
    repository = SQLiteAnalysisRepository(tmp_path / "export.sqlite3")
    workbook = golden_loaded_workbook()
    document = repository.register_document(b"quality-export", "quality.csv")
    analysis = repository.create_analysis(
        document.source_document_id, profile_workbook(workbook))
    repository.save_quality_report(
        _report(analysis.analysis_id, datetime(2026, 8, 18, 12, tzinfo=timezone.utc)))
    persisted = repository.get_quality_report(analysis.analysis_id)

    payload = json.loads(export_quality_report_json(
        persisted, document.source_document_id))
    persisted_payload = persisted.model_dump(mode="json")
    assert all(payload[key] == value for key, value in persisted_payload.items())
    assert payload["source_document_id"] == document.source_document_id
    assert payload["analysis_id"] == analysis.analysis_id
    assert payload["quality_score"] == persisted.score
    assert payload["quality_analysis"]["status"] == persisted.status.value
    assert payload["issues"][0]["evidence"] == {"quality_defect": False}
    assert payload["reconciliation_candidates"][0]["candidate_id"] == "rc:export"


def test_csv_has_one_complete_row_per_field_and_preserves_na():
    report = _report("analysis-csv", datetime(2026, 8, 18, tzinfo=timezone.utc))
    rows = list(csv.DictReader(io.StringIO(
        export_field_summary_csv(report, "sha256:csv").decode("utf-8-sig"))))
    assert len(rows) == len(report.field_summaries) == 2
    assert all(row["analysis_id"] == report.analysis_id for row in rows)
    assert all(row["quality_report_id"] == quality_report_id(report) for row in rows)
    assert rows[0]["effective_semantic_role"] == "identifier"
    assert rows[0]["requirement"] == "required"
    assert rows[0]["applicability"] == "applicable"
    deferred = rows[1]
    assert deferred["quality_status"] == "not_evaluated"
    assert deferred["quality_score"] == "N/A"
    assert deferred["quality_score"] != "0"


def test_reanalysis_exports_current_persisted_version(monkeypatch):
    old = _report("analysis-current", datetime(2026, 8, 18, tzinfo=timezone.utc))
    new = _report(
        "analysis-current",
        old.created_at + timedelta(minutes=5),
    )
    new.score = 77.5

    class Repository:
        def save_quality_report(self, report):
            assert report is new
            return report.model_copy(deep=True)

    monkeypatch.setattr(data_quality_view, "analyze_data_quality",
                        lambda workbook, semantic: new)
    state = {
        "current_quality_report": old,
        "current_workbook": object(),
        "current_validation_report": object(),
        "repository": Repository(),
    }
    current = data_quality_view.reanalyze_quality(state)
    payload = json.loads(export_quality_report_json(current, "sha256:current"))
    csv_rows = list(csv.DictReader(io.StringIO(
        export_field_summary_csv(current, "sha256:current").decode("utf-8-sig"))))
    assert state["current_quality_report"] is current
    assert payload["quality_report_id"] == quality_report_id(new)
    assert payload["quality_report_id"] != quality_report_id(old)
    assert payload["quality_score"] == 77.5
    assert all(row["quality_report_id"] == quality_report_id(new) for row in csv_rows)
