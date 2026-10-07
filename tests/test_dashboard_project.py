import pytest
from pydantic import ValidationError
from core.dashboard_project import *

def component(kind,metrics=None,dimensions=None,source_id="fact"):
    return DashboardComponent(title="Teste",component_type=kind,source_id=source_id,metrics=metrics or [],dimensions=dimensions or [],position=GridPosition(x=0,y=0,width=6,height=3))

def test_line_requires_temporal_dimension():
    with pytest.raises(ValidationError):
        component(ComponentType.LINE,[MetricBinding(field="valor",label="Valor")],[DimensionBinding(field="orgao",label="Órgão")])

def test_line_accepts_temporal_dimension():
    item=component(ComponentType.LINE,[MetricBinding(field="valor",label="Valor")],[DimensionBinding(field="data",label="Data",role=FieldRole.TEMPORAL_DIMENSION)])
    assert item.component_type==ComponentType.LINE

def test_kpi_rejects_dimension():
    with pytest.raises(ValidationError):
        component(ComponentType.KPI,[MetricBinding(field="valor",label="Valor")],[DimensionBinding(field="orgao",label="Órgão")])

def test_grid_cannot_overflow():
    with pytest.raises(ValidationError):
        GridPosition(x=10,y=0,width=3,height=2)

def test_project_rejects_unknown_source():
    with pytest.raises(ValidationError):
        DashboardProject(name="Projeto",audience=DashboardAudience(name="Gestor",audience_type=AudienceType.MANAGERIAL,objective="Acompanhar"),sources=[AnalyticalSource(source_id="fact",name="Fato",fact_table="bi.fato")],pages=[DashboardPage(title="Página",components=[component(ComponentType.KPI,[MetricBinding(field="valor",label="Valor")],source_id="missing")])])
