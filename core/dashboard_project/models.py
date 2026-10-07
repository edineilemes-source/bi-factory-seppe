"""Contracts for designing dashboards from validated analytical models."""

from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class AudienceType(str, Enum):
    EXECUTIVE = "EXECUTIVE"
    MANAGERIAL = "MANAGERIAL"
    TECHNICAL = "TECHNICAL"
    PUBLIC = "PUBLIC"


class OutputType(str, Enum):
    WEB = "WEB"
    PDF = "PDF"
    EXCEL = "EXCEL"
    PRINT = "PRINT"


class ComponentType(str, Enum):
    KPI = "KPI"
    LINE = "LINE"
    BAR = "BAR"
    AREA = "AREA"
    DONUT = "DONUT"
    TREEMAP = "TREEMAP"
    TABLE = "TABLE"
    RANKING = "RANKING"
    TEXT = "TEXT"
    ALERT = "ALERT"


class FieldRole(str, Enum):
    METRIC = "METRIC"
    DIMENSION = "DIMENSION"
    TEMPORAL_DIMENSION = "TEMPORAL_DIMENSION"


class DashboardAudience(BaseModel):
    name: str
    audience_type: AudienceType
    objective: str
    decision_horizon: str | None = None


class AnalyticalSource(BaseModel):
    source_id: str
    name: str
    fact_table: str
    description: str | None = None


class MetricBinding(BaseModel):
    field: str
    label: str
    aggregation: Literal["SUM", "MAX", "MIN", "AVG", "COUNT", "NONE"] = "SUM"
    number_format: str | None = None


class DimensionBinding(BaseModel):
    field: str
    label: str
    role: FieldRole = FieldRole.DIMENSION
    granularity: str | None = None


class DashboardFilter(BaseModel):
    filter_id: str = Field(default_factory=lambda: str(uuid4()))
    field: str
    label: str
    role: FieldRole = FieldRole.DIMENSION
    selection: Literal["SINGLE", "MULTIPLE", "RANGE"] = "MULTIPLE"
    required: bool = False
    default: str | int | float | list[str | int | float] | None = None


class GridPosition(BaseModel):
    x: int = Field(ge=0, le=11)
    y: int = Field(ge=0)
    width: int = Field(ge=1, le=12)
    height: int = Field(ge=1)

    @model_validator(mode="after")
    def fits_grid(self):
        if self.x + self.width > 12:
            raise ValueError("component exceeds the 12-column dashboard grid")
        return self


class DashboardComponent(BaseModel):
    component_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    component_type: ComponentType
    source_id: str
    metrics: list[MetricBinding] = Field(default_factory=list)
    dimensions: list[DimensionBinding] = Field(default_factory=list)
    local_filters: list[DashboardFilter] = Field(default_factory=list)
    position: GridPosition
    description: str | None = None

    @model_validator(mode="after")
    def validate_visual_contract(self):
        if self.component_type == ComponentType.TEXT:
            return self

        if not self.metrics:
            raise ValueError(f"{self.component_type.value} requires at least one metric")

        if self.component_type == ComponentType.KPI and self.dimensions:
            raise ValueError("KPI must not define chart dimensions")

        if self.component_type in {ComponentType.LINE, ComponentType.AREA}:
            temporal = any(
                d.role == FieldRole.TEMPORAL_DIMENSION for d in self.dimensions
            )
            if not temporal:
                raise ValueError(
                    f"{self.component_type.value} requires a temporal dimension"
                )

        if self.component_type in {
            ComponentType.BAR,
            ComponentType.DONUT,
            ComponentType.TREEMAP,
            ComponentType.RANKING,
        } and not self.dimensions:
            raise ValueError(f"{self.component_type.value} requires a dimension")

        return self


class DashboardPage(BaseModel):
    page_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str | None = None
    global_filters: list[DashboardFilter] = Field(default_factory=list)
    components: list[DashboardComponent] = Field(default_factory=list)


class DashboardProject(BaseModel):
    project_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str | None = None
    audience: DashboardAudience
    sources: list[AnalyticalSource]
    pages: list[DashboardPage]
    outputs: list[OutputType] = Field(default_factory=lambda: [OutputType.WEB])
    refresh_policy: str | None = None
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_references(self):
        source_ids = {source.source_id for source in self.sources}
        if len(source_ids) != len(self.sources):
            raise ValueError("source_id values must be unique")

        for page in self.pages:
            for component in page.components:
                if component.source_id not in source_ids:
                    raise ValueError(
                        f"component {component.title!r} references unknown "
                        f"source_id {component.source_id!r}"
                    )
        return self
