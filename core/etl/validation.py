"""Human validation and Effective ETL Plan resolution."""

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from core.etl.models import DimensionalETLPlan, ETLPlanStatus, ValidatedDimensionalETLPlan


def validate_dimensional_etl_plan(plan: DimensionalETLPlan, *, validated_by: str = "user",
                                  version: int = 1) -> ValidatedDimensionalETLPlan:
    if plan.status == ETLPlanStatus.BLOCKED or plan.blockers:
        raise ValueError("ETL Plan BLOCKED não pode ser validado.")
    return ValidatedDimensionalETLPlan(validation_id=str(uuid4()), etl_plan_id=plan.etl_plan_id,
                                       plan=deepcopy(plan), validated_by=validated_by,
                                       validated_at=datetime.now(timezone.utc), version=version)


def effective_dimensional_etl_plan(validation: ValidatedDimensionalETLPlan | None) -> DimensionalETLPlan | None:
    return validation.plan if validation and validation.plan.status != ETLPlanStatus.BLOCKED else None
