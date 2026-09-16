"""Single source of truth for semantic roles consumed by downstream modules."""

from core.profiling.models import SemanticRole
from core.semantic.models import SemanticValidation, SemanticValidationReport, ValidationStatus


ACCEPTED_STATUSES = {
    ValidationStatus.AUTO_ACCEPTED,
    ValidationStatus.USER_CONFIRMED,
    ValidationStatus.USER_CORRECTED,
}


def effective_semantic_role(validation: SemanticValidation) -> SemanticRole:
    """Resolve validated > accepted > observed without re-profiling a field."""
    if validation.validated_role is not None:
        return validation.validated_role
    if validation.validation_status in ACCEPTED_STATUSES:
        # Old persisted reports may omit validated_role for an accepted decision.
        return validation.original_hypothesis
    return validation.original_hypothesis


def effective_semantic_roles(report: SemanticValidationReport) -> dict[str, SemanticRole]:
    return {
        item.source_field_id: effective_semantic_role(item)
        for item in report.validated_semantics
    }
