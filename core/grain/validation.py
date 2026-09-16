"""Explicit human validation and Effective Grain resolution."""

from datetime import datetime, timezone
from uuid import uuid4

from core.grain.models import (
    GrainClassification, GrainDefinition, GrainDiscoveryReport, GrainReadiness,
    GrainValidationStatus, KnowledgeValidationStatus,
)


def validate_grain(
    report: GrainDiscoveryReport,
    *,
    candidate_id: str | None = None,
    user_grain_description: str | None = None,
    grain_fields: list[str] | None = None,
    validated_process: str | None = None,
    validated_event: str | None = None,
    validated_by: str = "user",
    version: int = 1,
    source_record_grain: bool = False,
) -> GrainDefinition:
    """Create an immutable new validated definition; never mutate prior versions."""
    candidate = next((item for item in report.grain_candidates
                      if item.candidate_id == candidate_id), None)
    if candidate_id and candidate is None:
        raise ValueError(f"Candidato de grão não encontrado: {candidate_id}")
    selected_fields = list(grain_fields if grain_fields is not None else
                           candidate.candidate_fields if candidate else [])
    if source_record_grain:
        selected_fields = ["source_row_id"]
        user_grain_description = (user_grain_description or
            "Um registro de despesa/pagamento conforme a granularidade original da fonte.")
    description = (candidate.human_readable_description if candidate else
                   user_grain_description or "Grão descrito manualmente pelo usuário.")
    if not user_grain_description and candidate is None:
        raise ValueError("Selecione um candidato ou descreva manualmente o grão.")
    observed_process = candidate.inferred_process if candidate else (
        report.process_candidates[0].name if report.process_candidates else None)
    observed_event = candidate.inferred_event if candidate else (
        report.event_candidates[0].name if report.event_candidates else None)
    process_status = (KnowledgeValidationStatus.CORRECTED
                      if validated_process and validated_process != observed_process
                      else KnowledgeValidationStatus.CONFIRMED if validated_process
                      else KnowledgeValidationStatus.UNKNOWN)
    event_status = (KnowledgeValidationStatus.CORRECTED
                    if validated_event and validated_event != observed_event
                    else KnowledgeValidationStatus.CONFIRMED if validated_event
                    else KnowledgeValidationStatus.UNKNOWN)
    validation_status = (GrainValidationStatus.CORRECTED if user_grain_description
                         else GrainValidationStatus.CONFIRMED)
    evidence = list(candidate.evidence) if candidate else ["Definição fornecida explicitamente pelo usuário."]
    conflicts = list(candidate.counter_evidence) if candidate else []
    return GrainDefinition(
        grain_id=str(uuid4()), grain_discovery_report_id=report.grain_discovery_report_id,
        source_document_id=report.source_document_id,
        prepared_dataset_id=report.prepared_dataset_id,
        prepared_dataset_version=report.prepared_dataset_version,
        prepared_dataset_fingerprint=report.prepared_dataset_fingerprint,
        analysis_id=report.analysis_id, status=GrainReadiness.READY_FOR_DIMENSIONAL_MODELING,
        description=description, user_grain_description=user_grain_description,
        grain_type=(GrainClassification.SINGLE_GRAIN
                    if source_record_grain or user_grain_description and report.grain_classification in {
                        GrainClassification.AMBIGUOUS_GRAIN,
                        GrainClassification.INSUFFICIENT_EVIDENCE,
                    } else report.grain_classification),
        observed_process=observed_process, validated_process=validated_process,
        process_validation_status=process_status,
        observed_event=observed_event, validated_event=validated_event,
        event_validation_status=event_status, grain_fields=selected_fields,
        selected_candidate_id=candidate.candidate_id if candidate else None,
        candidate_business_key=selected_fields,
        uniqueness_percentage=round(100 * candidate.uniqueness_ratio, 4) if candidate else 0,
        duplicate_percentage=round(100 * (1 - candidate.uniqueness_ratio), 4) if candidate else 0,
        confidence=candidate.confidence if candidate else 1,
        evidence=evidence, conflicts=conflicts, validation_status=validation_status,
        validated_by=validated_by, validated_at=datetime.now(timezone.utc), version=version,
    )


def record_unknown_grain(report: GrainDiscoveryReport, *, version: int = 1,
                         validated_by: str = "user") -> GrainDefinition:
    """Persist an explicit lack of knowledge without unlocking downstream modeling."""
    return GrainDefinition(
        grain_id=str(uuid4()), grain_discovery_report_id=report.grain_discovery_report_id,
        source_document_id=report.source_document_id,
        prepared_dataset_id=report.prepared_dataset_id,
        prepared_dataset_version=report.prepared_dataset_version,
        prepared_dataset_fingerprint=report.prepared_dataset_fingerprint,
        analysis_id=report.analysis_id, status=GrainReadiness.NOT_READY,
        description="Não sei / preciso investigar a granularidade da fonte.",
        grain_type=GrainClassification.INSUFFICIENT_EVIDENCE,
        validation_status=GrainValidationStatus.UNKNOWN, validated_by=validated_by,
        validated_at=datetime.now(timezone.utc), version=version,
    )


def effective_grain(definition: GrainDefinition | None) -> GrainDefinition | None:
    """Future modules consume only a validated definition compatible with its dataset."""
    if definition is None or definition.validation_status not in {
        GrainValidationStatus.CONFIRMED, GrainValidationStatus.CORRECTED,
    }:
        return None
    return definition
