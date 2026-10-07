#!/usr/bin/env python3
"""Example: executive fiscal dashboard project."""
import json
import sys
from pathlib import Path

# Allow direct execution: python scripts/dashboard_project_example.py
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.dashboard_project import *

def kpi(title, field, x):
    return DashboardComponent(title=title,component_type=ComponentType.KPI,source_id="fiscal",metrics=[MetricBinding(field=field,label=title,aggregation="MAX",number_format="BRL_COMPACT")],position=GridPosition(x=x,y=0,width=3,height=2))

def build_project():
    return DashboardProject(
        name="Sala Executiva — Execução Orçamentária",
        description="Primeiro projeto de apresentação sobre o DW fiscal validado.",
        audience=DashboardAudience(name="Prefeita",audience_type=AudienceType.EXECUTIVE,objective="Acompanhar rapidamente a execução fiscal e sua tendência.",decision_horizon="Diário / semanal / fechamento do período"),
        sources=[AnalyticalSource(source_id="fiscal",name="Execução Orçamentária",fact_table="bi_fiscal.vw_execucao_orcamentaria")],
        pages=[DashboardPage(
            title="Visão Fiscal",
            global_filters=[
                DashboardFilter(field="exercicio",label="Exercício",selection="SINGLE",required=True,default=2025),
                DashboardFilter(field="bimestre",label="Bimestre",selection="SINGLE"),
            ],
            components=[
                kpi("Receita realizada","receita_realizada_acumulada",0),
                kpi("Despesa empenhada","despesa_empenhada_acumulada",3),
                kpi("Despesa liquidada","despesa_liquidada_acumulada",6),
                kpi("Despesa paga","despesa_paga_acumulada",9),
                DashboardComponent(
                    title="Evolução da execução orçamentária",component_type=ComponentType.LINE,source_id="fiscal",
                    metrics=[
                        MetricBinding(field="receita_realizada_acumulada",label="Receita",aggregation="MAX",number_format="BRL_COMPACT"),
                        MetricBinding(field="despesa_empenhada_acumulada",label="Empenhada",aggregation="MAX",number_format="BRL_COMPACT"),
                        MetricBinding(field="despesa_liquidada_acumulada",label="Liquidada",aggregation="MAX",number_format="BRL_COMPACT"),
                        MetricBinding(field="despesa_paga_acumulada",label="Paga",aggregation="MAX",number_format="BRL_COMPACT"),
                    ],
                    dimensions=[DimensionBinding(field="bimestre",label="Bimestre",role=FieldRole.TEMPORAL_DIMENSION,granularity="BIMESTRAL")],
                    position=GridPosition(x=0,y=2,width=8,height=5),
                ),
                DashboardComponent(title="Resultado orçamentário formal",component_type=ComponentType.KPI,source_id="fiscal",metrics=[MetricBinding(field="resultado_orcamentario_formal",label="Receita realizada − despesa empenhada",aggregation="MAX",number_format="BRL_COMPACT")],position=GridPosition(x=8,y=2,width=4,height=2)),
                DashboardComponent(title="Margem receita × liquidada",component_type=ComponentType.KPI,source_id="fiscal",metrics=[MetricBinding(field="margem_receita_menos_liquidada",label="Receita realizada − despesa liquidada",aggregation="MAX",number_format="BRL_COMPACT")],position=GridPosition(x=8,y=4,width=4,height=2)),
            ],
        )],
        outputs=[OutputType.WEB,OutputType.PDF],
        refresh_policy="Conforme atualização da fonte oficial",
    )

if __name__=="__main__":
    print(json.dumps(build_project().model_dump(mode="json"),ensure_ascii=False,indent=2))
