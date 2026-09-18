"""Business-context contracts for human-in-the-loop BI modeling."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ContextProvenance(str, Enum):
    INFERRED = "INFERRED"
    AUTO_ACCEPTED = "AUTO_ACCEPTED"
    USER_CONFIRMED = "USER_CONFIRMED"
    USER_CORRECTED = "USER_CORRECTED"
    IMPORTED = "IMPORTED"


class BusinessContextStatus(str, Enum):
    DRAFT = "DRAFT"
    NEEDS_VALIDATION = "NEEDS_VALIDATION"
    VALIDATED = "VALIDATED"


class ContextValue(BaseModel):
    value: Any = None
    provenance: ContextProvenance = ContextProvenance.INFERRED
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


class BusinessMeasure(BaseModel):
    field_id: str
    business_name: str | None = None
    meaning: str | None = None
    additive: bool | None = None
    provenance: ContextProvenance = ContextProvenance.INFERRED


class AnalyticalPerspective(BaseModel):
    name: str
    field_ids: list[str] = Field(default_factory=list)
    provenance: ContextProvenance = ContextProvenance.INFERRED


class TemporalRole(BaseModel):
    field_id: str
    role: str
    provenance: ContextProvenance = ContextProvenance.INFERRED


class BusinessRule(BaseModel):
    rule_id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    affected_fields: list[str] = Field(default_factory=list)
    provenance: ContextProvenance = ContextProvenance.USER_CONFIRMED


class BusinessContext(BaseModel):
    business_context_id: str = Field(default_factory=lambda: str(uuid4()))
    source_document_id: str
    analysis_id: str
    prepared_dataset_id: str
    prepared_dataset_version: int
    prepared_dataset_fingerprint: str
    version: int = 0
    fingerprint: str = ""
    status: BusinessContextStatus = BusinessContextStatus.DRAFT
    analytical_objective: ContextValue = Field(default_factory=ContextValue)
    business_domain: ContextValue = Field(default_factory=ContextValue)
    business_process: ContextValue = Field(default_factory=ContextValue)
    business_event: ContextValue = Field(default_factory=ContextValue)
    grain_meaning: ContextValue = Field(default_factory=ContextValue)
    measures: list[BusinessMeasure] = Field(default_factory=list)
    analytical_perspectives: list[AnalyticalPerspective] = Field(default_factory=list)
    transaction_identifiers: list[str] = Field(default_factory=list)
    temporal_roles: list[TemporalRole] = Field(default_factory=list)
    business_rules: list[BusinessRule] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BusinessContextRecord(BaseModel):
    business_context_id: str
    source_document_id: str
    analysis_id: str
    prepared_dataset_id: str
    version: int
    fingerprint: str
    status: BusinessContextStatus
    created_at: datetime
    context: BusinessContext
