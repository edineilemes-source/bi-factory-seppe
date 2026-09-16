"""Human validation and Effective Star Schema Contract resolution."""

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from core.star.models import (
    ContractItemStatus, ContractStatus, ReadinessStatus, SCDStrategyContract,
    StarSchemaContract, StarSchemaContractReport, ValidatedStarSchemaContract,
)


def validate_star_schema_contract(
    report: StarSchemaContractReport, *, contract: StarSchemaContract | None = None,
    scd_overrides: dict[str, SCDStrategyContract] | None = None,
    validated_by: str = "user", version: int = 1,
) -> ValidatedStarSchemaContract:
    """Create a new validated version; the observed report remains unchanged."""
    effective = deepcopy(contract or report.contract)
    if effective.contract_id != report.contract.contract_id:
        raise ValueError("Contrato editado deve preservar o contract_id observado.")
    overrides = scd_overrides or {}
    dimensions = {item.dimension_id: item for item in effective.dimension_tables}
    if set(overrides) - set(dimensions):
        raise ValueError("SCD override referencia dimensão inexistente.")
    for dimension_id, strategy in overrides.items():
        if strategy.dimension_id != dimension_id:
            raise ValueError("SCD strategy incompatível com a dimensão.")
        dimensions[dimension_id].scd_strategy = deepcopy(strategy)
    for fact in effective.fact_tables:
        fact.status = ContractItemStatus.VALIDATED
        for measure in fact.measures:
            measure.validation_status = ContractItemStatus.VALIDATED
        for foreign in fact.foreign_keys:
            foreign.validation_status = ContractItemStatus.VALIDATED
        for degenerate in fact.degenerate_identifiers:
            degenerate.validation_status = ContractItemStatus.VALIDATED
    for dimension in effective.dimension_tables:
        dimension.status = ContractItemStatus.VALIDATED
        if dimension.business_key_fields.fields:
            dimension.business_key_fields.uniqueness_validation_status = "VALIDATED_BY_USER"
            dimension.business_key_fields.requires_validation = False
        for hierarchy in dimension.hierarchies:
            hierarchy.validation_status = ContractItemStatus.VALIDATED
    for relationship in effective.relationships:
        relationship.validation_status = ContractItemStatus.VALIDATED
    blockers = [warning for warning in effective.warnings if warning.blocker]
    missing_business_keys = [dimension.dimension_id for dimension in effective.dimension_tables
                             if not dimension.business_key_fields.fields]
    essential_missing = bool(effective.dimension_tables and any(
        not fact.foreign_keys for fact in effective.fact_tables))
    readiness = (ReadinessStatus.NOT_READY if blockers or missing_business_keys or essential_missing
                 else ReadinessStatus.READY_WITH_WARNINGS if effective.warnings
                 else ReadinessStatus.READY_FOR_DDL)
    # Human confirmation turns non-blocking, reviewed warnings into readiness.
    if readiness == ReadinessStatus.READY_WITH_WARNINGS:
        readiness = ReadinessStatus.READY_FOR_DDL
    effective.status = ContractStatus.VALIDATED
    effective.validated_at = datetime.now(timezone.utc)
    return ValidatedStarSchemaContract(
        validation_id=str(uuid4()), report_id=report.report_id,
        observed_contract_id=report.contract.contract_id, contract=effective,
        readiness=readiness, validated_by=validated_by,
        validated_at=effective.validated_at, version=version)


def effective_star_schema_contract(
    validation: ValidatedStarSchemaContract | None,
) -> StarSchemaContract | None:
    if (validation is None or validation.contract.status != ContractStatus.VALIDATED
            or validation.readiness != ReadinessStatus.READY_FOR_DDL):
        return None
    return validation.contract
