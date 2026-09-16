"""Lossless exports of an already-created data-quality report."""

import csv
import hashlib
import io
import json

from core.quality.models import DataQualityReport


def quality_report_id(report: DataQualityReport) -> str:
    """Stable execution identity; no quality metric is recalculated."""
    if report.quality_report_id:
        return report.quality_report_id
    identity = f"{report.analysis_id}|{report.created_at.isoformat()}"
    return "quality:" + hashlib.sha256(identity.encode()).hexdigest()[:20]


def quality_report_export_payload(
    report: DataQualityReport, source_document_id: str,
) -> dict:
    """Return the persisted model verbatim plus explicit export identities/aliases."""
    payload = report.model_dump(mode="json")
    timestamp = report.created_at.isoformat()
    report_id = quality_report_id(report)
    payload.update({
        "source_document_id": source_document_id,
        "quality_report_id": report_id,
        "quality_score": report.score,
        "updated_at": timestamp,
        "quality_analysis": {
            "status": report.status.value,
            "quality_report_id": report_id,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    })
    return payload


def export_quality_report_json(
    report: DataQualityReport, source_document_id: str,
) -> bytes:
    payload = quality_report_export_payload(report, source_document_id)
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


CSV_COLUMNS = [
    "source_document_id", "analysis_id", "quality_report_id",
    "quality_analysis_timestamp", "source_field_id", "sheet_name", "field_name",
    "effective_semantic_role", "requirement", "applicability", "quality_status",
    "quality_score", "observed_completeness", "missing_count", "missing_percentage",
    "placeholder_count", "placeholder_percentage", "issues_count", "max_severity",
    "affected_count", "affected_percentage",
]


def export_field_summary_csv(
    report: DataQualityReport, source_document_id: str,
) -> bytes:
    """Export exactly one row per persisted field summary."""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    report_id = quality_report_id(report)
    timestamp = report.created_at.isoformat()
    for field in report.field_summaries:
        writer.writerow({
            "source_document_id": source_document_id,
            "analysis_id": report.analysis_id,
            "quality_report_id": report_id,
            "quality_analysis_timestamp": timestamp,
            "source_field_id": field.source_field_id,
            "sheet_name": field.sheet_name,
            "field_name": field.field_name,
            "effective_semantic_role": field.effective_semantic_role.value,
            "requirement": field.requirement.value,
            "applicability": field.applicability.value,
            "quality_status": field.quality_status.value,
            "quality_score": "N/A" if field.quality_score is None else field.quality_score,
            "observed_completeness": field.observed_completeness,
            "missing_count": field.missing_count,
            "missing_percentage": field.missing_percentage,
            "placeholder_count": field.placeholder_count,
            "placeholder_percentage": field.placeholder_percentage,
            "issues_count": field.issues_count,
            "max_severity": field.maximum_severity.value if field.maximum_severity else "",
            "affected_count": field.affected_count,
            "affected_percentage": field.affected_percentage,
        })
    return output.getvalue().encode("utf-8-sig")
