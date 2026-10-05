from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "storage/reports/official_fiscal/rreo-2025-dashboard.csv"
TARGET = ROOT / "storage/reports/official_fiscal/fiscal_dw_postgres.sql"

FIELDS = [
    "receita_realizada_acumulada", "receita_no_bimestre", "despesa_empenhada_acumulada",
    "despesa_liquidada_acumulada", "despesa_liquidada_no_bimestre", "despesa_paga_acumulada",
    "resultado_orcamentario_formal", "margem_receita_menos_liquidada", "liquidada_sobre_receita_pct",
    "empenhada_nao_liquidada", "liquidada_nao_paga", "rpnp_inscritos",
]


def sql_num(value: str) -> str:
    return "NULL" if value in ("", "None") else str(float(value))


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Dataset não encontrado: {SOURCE}")
    rows = list(csv.DictReader(SOURCE.open(encoding="utf-8")))
    statements = [
        "BEGIN;",
        "CREATE SCHEMA IF NOT EXISTS bi_fiscal;",
        "DROP VIEW IF EXISTS bi_fiscal.vw_execucao_orcamentaria;",
        "DROP TABLE IF EXISTS bi_fiscal.fato_execucao_orcamentaria CASCADE;",
        "DROP TABLE IF EXISTS bi_fiscal.dim_fonte_fiscal CASCADE;",
        "DROP TABLE IF EXISTS bi_fiscal.dim_tempo_fiscal CASCADE;",
        "DROP TABLE IF EXISTS bi_fiscal.dim_ente CASCADE;",
        "CREATE TABLE bi_fiscal.dim_ente (ente_id integer PRIMARY KEY, cod_ibge integer NOT NULL UNIQUE, nome text NOT NULL, uf text NOT NULL, esfera text NOT NULL);",
        "CREATE TABLE bi_fiscal.dim_tempo_fiscal (tempo_id integer PRIMARY KEY, exercicio integer NOT NULL, bimestre integer NOT NULL, mes_fim integer NOT NULL, periodicidade text NOT NULL, UNIQUE(exercicio,bimestre));",
        "CREATE TABLE bi_fiscal.dim_fonte_fiscal (fonte_id integer PRIMARY KEY, sistema text NOT NULL, demonstrativo text NOT NULL, anexo text NOT NULL, origem text NOT NULL, UNIQUE(sistema,demonstrativo,anexo));",
        "CREATE TABLE bi_fiscal.fato_execucao_orcamentaria (fato_id integer PRIMARY KEY, ente_id integer NOT NULL REFERENCES bi_fiscal.dim_ente, tempo_id integer NOT NULL REFERENCES bi_fiscal.dim_tempo_fiscal, fonte_id integer NOT NULL REFERENCES bi_fiscal.dim_fonte_fiscal, receita_realizada_acumulada numeric(20,2) NOT NULL, receita_no_bimestre numeric(20,2), despesa_empenhada_acumulada numeric(20,2) NOT NULL, despesa_liquidada_acumulada numeric(20,2) NOT NULL, despesa_liquidada_no_bimestre numeric(20,2), despesa_paga_acumulada numeric(20,2) NOT NULL, resultado_orcamentario_formal numeric(20,2) NOT NULL, margem_receita_menos_liquidada numeric(20,2) NOT NULL, liquidada_sobre_receita_pct numeric(10,4), empenhada_nao_liquidada numeric(20,2) NOT NULL, liquidada_nao_paga numeric(20,2) NOT NULL, rpnp_inscritos numeric(20,2), UNIQUE(ente_id,tempo_id,fonte_id));",
        "INSERT INTO bi_fiscal.dim_ente VALUES (1,5002704,'Prefeitura Municipal de Campo Grande','MS','M');",
        "INSERT INTO bi_fiscal.dim_fonte_fiscal VALUES (1,'SICONFI','RREO','RREO-Anexo 01','STN/SICONFI API');",
    ]
    for row in rows:
        year, period, month_end = int(row["ano"]), int(row["bimestre"]), int(row["mes_fim"])
        tempo_id = year * 10 + period
        statements.append(f"INSERT INTO bi_fiscal.dim_tempo_fiscal VALUES ({tempo_id},{year},{period},{month_end},'B');")
        values = ",".join(sql_num(row[name]) for name in FIELDS)
        statements.append(f"INSERT INTO bi_fiscal.fato_execucao_orcamentaria VALUES ({tempo_id},1,{tempo_id},1,{values});")
    statements += [
        "CREATE VIEW bi_fiscal.vw_execucao_orcamentaria AS SELECT e.cod_ibge,e.nome AS ente,e.uf,t.exercicio,t.bimestre,t.mes_fim,t.periodicidade,fo.sistema,fo.demonstrativo,fo.anexo,f.receita_realizada_acumulada,f.receita_no_bimestre,f.despesa_empenhada_acumulada,f.despesa_liquidada_acumulada,f.despesa_liquidada_no_bimestre,f.despesa_paga_acumulada,f.resultado_orcamentario_formal,f.margem_receita_menos_liquidada,f.liquidada_sobre_receita_pct,f.empenhada_nao_liquidada,f.liquidada_nao_paga,f.rpnp_inscritos FROM bi_fiscal.fato_execucao_orcamentaria f JOIN bi_fiscal.dim_ente e USING(ente_id) JOIN bi_fiscal.dim_tempo_fiscal t USING(tempo_id) JOIN bi_fiscal.dim_fonte_fiscal fo USING(fonte_id);",
        "COMMIT;",
    ]
    TARGET.write_text("\n".join(statements) + "\n", encoding="utf-8")
    print(f"PostgreSQL bootstrap: {TARGET}")
    print(f"Fatos exportados: {len(rows)}")
    print("Dataset Superset: bi_fiscal.vw_execucao_orcamentaria")


if __name__ == "__main__":
    main()
