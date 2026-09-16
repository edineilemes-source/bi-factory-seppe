"""Stable JSON exports with complete lineage."""

import json

from core.dimensional.models import DimensionalDiscoveryReport, ValidatedDimensionalDiscovery


def _dump(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def export_dimensional_discovery_json(report: DimensionalDiscoveryReport) -> bytes:
    payload = report.model_dump(mode="json")
    payload["lineage"] = {
        "source_document_id": report.source_document_id, "analysis_id": report.analysis_id,
        "prepared_dataset_id": report.prepared_dataset_id,
        "prepared_dataset_version": report.prepared_dataset_version,
        "grain_definition_id": report.grain_definition_id, "grain_version": report.grain_version,
        "dimensional_discovery_report_id": report.report_id,
    }
    return _dump(payload)


def export_validated_dimensional_json(validation: ValidatedDimensionalDiscovery) -> bytes:
    payload = validation.model_dump(mode="json")
    payload["lineage"] = {
        "source_document_id": validation.source_document_id, "analysis_id": validation.analysis_id,
        "prepared_dataset_id": validation.prepared_dataset_id,
        "prepared_dataset_version": validation.prepared_dataset_version,
        "grain_definition_id": validation.grain_definition_id,
        "grain_version": validation.grain_version, "report_id": validation.report_id,
        "validation_id": validation.validation_id,
    }
    payload["validation"] = {"validated_by": validation.validated_by,
                             "validated_at": validation.validated_at.isoformat(),
                             "version": validation.version, "status": validation.status.value}
    return _dump(payload)
