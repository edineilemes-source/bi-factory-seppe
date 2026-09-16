"""Structured diagnostic models for tabular workbooks."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


WarningLevel = Literal["info", "warning", "error"]
SourceType = Literal["browser_upload", "workspace"]


class SemanticRole(str, Enum):
    """Generic, preliminary semantic hypothesis for a field."""

    IDENTIFIER = "identifier"
    CODE = "code"
    MEASURE = "measure"
    DATE = "date"
    TIME_COMPONENT = "time_component"
    CATEGORY = "category"
    DESCRIPTION = "description"
    BOOLEAN = "boolean"
    UNKNOWN = "unknown"


class SampleStatus(str, Enum):
    """Observed population status, explicitly limited to the sample."""

    POPULATED = "populated"
    EMPTY_IN_SAMPLE = "empty_in_sample"
    PARTIALLY_POPULATED = "partially_populated"


class StructuralWarning(BaseModel):
    """A structural issue found during profiling."""

    code: str
    message: str
    level: WarningLevel = "warning"
    sheet_name: str | None = None
    field_name: str | None = None


class FieldProfile(BaseModel):
    """Technical profile of one tabular field."""

    original_name: str
    technical_name: str
    detected_type: str
    recommended_type: str
    null_count: int
    null_percentage: float
    placeholder_count: int = 0
    placeholder_percentage: float = 0.0
    distinct_count: int
    non_null_count: int = 0
    distinct_ratio: float = 0.0
    sample_status: SampleStatus = SampleStatus.POPULATED
    semantic_role_candidate: SemanticRole = SemanticRole.UNKNOWN
    semantic_role_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    semantic_evidence: list[str] = Field(default_factory=list)
    examples: list[Any] = Field(default_factory=list)
    average_text_length: float | None = None
    min_text_length: int | None = None
    max_text_length: int | None = None
    numeric_min: float | None = None
    numeric_max: float | None = None
    numeric_mean: float | None = None
    negative_count: int | None = None
    zero_count: int | None = None
    constant_value: Any | None = None
    is_candidate_key: bool = False
    is_possible_date: bool = False
    is_possible_measure: bool = False
    is_possible_category: bool = False
    warnings: list[StructuralWarning] = Field(default_factory=list)


class SheetProfile(BaseModel):
    """Profile and classification hypothesis for a sheet or CSV source."""

    name: str
    role_hypothesis: str
    approximate_row_count: int
    column_count: int
    sampled_data_row_count: int
    sampling_strategy: str = "distributed_deterministic"
    probable_header_row: int | None = None
    fully_empty_rows: list[int] = Field(default_factory=list)
    fully_empty_columns: list[int] = Field(default_factory=list)
    fields: list[FieldProfile] = Field(default_factory=list)
    warnings: list[StructuralWarning] = Field(default_factory=list)


class WorkbookSummary(BaseModel):
    """Aggregated workbook-level counts."""

    sheet_count: int
    total_approximate_rows: int
    total_columns: int
    warning_count: int


class ProjectContext(BaseModel):
    """Business context supplied by the user."""

    project_name: str = ""
    business_domain: str = ""
    purpose: str = ""
    notes: str = ""


class WorkbookProfile(BaseModel):
    """Complete, exportable technical diagnosis."""

    context: ProjectContext
    original_name: str
    source_type: SourceType
    size_bytes: int
    file_type: str
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    summary: WorkbookSummary
    sheets: list[SheetProfile]
    warnings: list[StructuralWarning] = Field(default_factory=list)
