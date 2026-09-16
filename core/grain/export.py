"""Stable JSON exports for discovery and validated contracts."""

import json

from core.grain.models import GrainDefinition, GrainDiscoveryReport


def export_grain_discovery_json(report: GrainDiscoveryReport) -> bytes:
    return json.dumps(report.model_dump(mode="json"), ensure_ascii=False,
                      indent=2, sort_keys=True).encode("utf-8")


def export_grain_definition_json(definition: GrainDefinition) -> bytes:
    payload = definition.model_dump(mode="json")
    payload["effective_process"] = definition.effective_process
    payload["effective_event"] = definition.effective_event
    payload["effective_grain_description"] = definition.effective_grain_description
    payload["lineage"] = {
        "source_document_id": definition.source_document_id,
        "analysis_id": definition.analysis_id,
        "prepared_dataset_id": definition.prepared_dataset_id,
        "prepared_dataset_version": definition.prepared_dataset_version,
        "grain_discovery_report_id": definition.grain_discovery_report_id,
        "grain_id": definition.grain_id,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
