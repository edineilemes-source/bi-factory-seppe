from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MVPStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"


class DimensionSpec(BaseModel):
    name: str
    source_fields: list[str]
    business_key_fields: list[str]


class MeasureSpec(BaseModel):
    source_field: str
    name: str
    postgres_type: str = "NUMERIC"
    additive_confirmed: bool = False


class MVPModel(BaseModel):
    model_id: str
    version: int = 1
    status: MVPStatus
    analysis_id: str
    source_document_id: str
    prepared_dataset_id: str
    prepared_version: int
    prepared_fingerprint: str
    prepared_artifact_sha256: str
    grain_definition_id: str
    grain_description: str
    fact_name: str = "fato_despesa_registro"
    dimensions: list[DimensionSpec]
    measures: list[MeasureSpec]
    preserved_identifiers: list[str]
    source_fields: dict[str, str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LoadMetrics(BaseModel):
    run_id: str
    analysis_id: str
    prepared_dataset_id: str
    prepared_version: int
    rows_read: int = 0
    rows_loaded: int = 0
    rows_already_loaded: int = 0
    database_row_count: int = 0
    chunk_count: int = 0
    source_totals: dict[str, str] = Field(default_factory=dict)
    database_totals: dict[str, str] = Field(default_factory=dict)
    reconciliation_status: str = "PENDING"
    rss_start_mb: float = 0
    rss_peak_mb: float = 0
    rss_end_mb: float = 0
    elapsed_seconds: float = 0
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
