"""Human validation and effective-proposal resolution."""

from copy import deepcopy
from uuid import uuid4

from core.dimensional.models import (
    CandidateStatus, DimensionCandidate, DimensionalDiscoveryReport, FactCandidate,
    FieldModelingDecision, ModelingRole, ProposalStatus, ValidatedDimensionalDiscovery,
)


def validate_dimensional_discovery(
    report: DimensionalDiscoveryReport, *,
    field_role_overrides: dict[str, ModelingRole] | None = None,
    fact_candidates: list[FactCandidate] | None = None,
    dimension_candidates: list[DimensionCandidate] | None = None,
    accepted_unresolved_fields: list[str] | None = None,
    validated_by: str = "user", version: int = 1,
) -> ValidatedDimensionalDiscovery:
    """Create a new validation version without mutating the observed report."""
    overrides = field_role_overrides or {}
    accepted = set(accepted_unresolved_fields or [])
    decisions: list[FieldModelingDecision] = []
    known = {item.source_field_id for item in report.field_decisions}
    if set(overrides) - known:
        raise ValueError("Override contém campo ausente da proposta observada.")
    for observed in report.field_decisions:
        decision = deepcopy(observed)
        if observed.source_field_id in overrides:
            role = ModelingRole(overrides[observed.source_field_id])
            decision.validated_modeling_role = role
            decision.effective_modeling_role = role
            decision.modeling_role = role
            decision.requires_validation = False
            decision.evidence.append("Papel de modelagem corrigido explicitamente pelo usuário.")
        decisions.append(decision)
    unresolved = {d.source_field_id for d in decisions
                  if d.effective_modeling_role == ModelingRole.UNRESOLVED}
    if not accepted <= unresolved:
        raise ValueError("Somente campos ainda UNRESOLVED podem ser aceitos explicitamente.")
    critical_unresolved = {d.source_field_id for d in decisions
                           if d.effective_modeling_role == ModelingRole.UNRESOLVED
                           and d.source_field_id not in accepted
                           and d.effective_semantic_role.value in {"identifier", "measure"}}
    facts = deepcopy(fact_candidates if fact_candidates is not None else report.fact_candidates)
    dimensions = deepcopy(dimension_candidates if dimension_candidates is not None
                          else report.dimension_candidates)
    for item in facts + dimensions:
        item.status = CandidateStatus.CONFIRMED
    status = (ProposalStatus.READY_FOR_STAR_SCHEMA if not critical_unresolved
              else ProposalStatus.VALIDATED)
    return ValidatedDimensionalDiscovery(
        validation_id=str(uuid4()), report_id=report.report_id,
        source_document_id=report.source_document_id, analysis_id=report.analysis_id,
        prepared_dataset_id=report.prepared_dataset_id,
        prepared_dataset_version=report.prepared_dataset_version,
        prepared_dataset_fingerprint=report.prepared_dataset_fingerprint,
        grain_definition_id=report.grain_definition_id, grain_version=report.grain_version,
        status=status, fact_candidates=facts, dimension_candidates=dimensions,
        measure_candidates=deepcopy(report.measure_candidates), field_decisions=decisions,
        accepted_unresolved_fields=sorted(accepted), validated_by=validated_by, version=version)


def effective_dimensional_discovery(
    validation: ValidatedDimensionalDiscovery | None,
) -> ValidatedDimensionalDiscovery | None:
    """Future Star Schema code consumes only explicit human validation."""
    if validation is None or validation.status not in {
        ProposalStatus.VALIDATED, ProposalStatus.READY_FOR_STAR_SCHEMA,
    }:
        return None
    return validation
