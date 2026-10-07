from app.components.dashboard_project_designer_view import _build_project
from core.dashboard_project import AudienceType, ComponentType, OutputType

def test_builder_creates_executive_fiscal_project():
    project=_build_project(
        "Sala Executiva","Prefeita",AudienceType.EXECUTIVE,"Acompanhar execução",
        ["Exercício","Bimestre"],
        ["Receita realizada","Despesa paga"],
        ["Receita realizada","Despesa paga"],
        [OutputType.WEB,OutputType.PDF],
    )
    assert project.audience.name=="Prefeita"
    assert project.sources[0].fact_table=="bi_fiscal.vw_execucao_orcamentaria"
    assert len(project.pages[0].global_filters)==2
    assert [c.component_type for c in project.pages[0].components].count(ComponentType.KPI)==2
    assert project.pages[0].components[-1].component_type==ComponentType.LINE
    assert project.pages[0].components[-1].position.width==12

def test_builder_can_create_technical_excel_view():
    project=_build_project(
        "Contabilidade","Contadora",AudienceType.TECHNICAL,"Conferir execução",
        ["Exercício","Ente"],["Resultado orçamentário formal"],[],[OutputType.EXCEL],
    )
    assert project.audience.audience_type==AudienceType.TECHNICAL
    assert project.outputs==[OutputType.EXCEL]
    assert len(project.pages[0].components)==1
