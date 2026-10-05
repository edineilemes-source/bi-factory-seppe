"""Dimensional warehouse schema for official municipal fiscal BI."""

from __future__ import annotations

FISCAL_DW_DDL = """
CREATE TABLE IF NOT EXISTS dim_ente (
    ente_id INTEGER PRIMARY KEY,
    cod_ibge INTEGER NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    uf TEXT NOT NULL,
    esfera TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_tempo_fiscal (
    tempo_id INTEGER PRIMARY KEY,
    exercicio INTEGER NOT NULL,
    bimestre INTEGER NOT NULL,
    mes_fim INTEGER NOT NULL,
    periodicidade TEXT NOT NULL DEFAULT 'B',
    UNIQUE (exercicio, bimestre)
);

CREATE TABLE IF NOT EXISTS dim_fonte_fiscal (
    fonte_id INTEGER PRIMARY KEY,
    sistema TEXT NOT NULL,
    demonstrativo TEXT NOT NULL,
    anexo TEXT NOT NULL,
    origem TEXT NOT NULL,
    UNIQUE (sistema, demonstrativo, anexo)
);

CREATE TABLE IF NOT EXISTS fato_execucao_orcamentaria (
    fato_id INTEGER PRIMARY KEY,
    ente_id INTEGER NOT NULL REFERENCES dim_ente(ente_id),
    tempo_id INTEGER NOT NULL REFERENCES dim_tempo_fiscal(tempo_id),
    fonte_id INTEGER NOT NULL REFERENCES dim_fonte_fiscal(fonte_id),
    receita_realizada_acumulada NUMERIC NOT NULL,
    receita_no_bimestre NUMERIC,
    despesa_empenhada_acumulada NUMERIC NOT NULL,
    despesa_liquidada_acumulada NUMERIC NOT NULL,
    despesa_liquidada_no_bimestre NUMERIC,
    despesa_paga_acumulada NUMERIC NOT NULL,
    resultado_orcamentario_formal NUMERIC NOT NULL,
    margem_receita_menos_liquidada NUMERIC NOT NULL,
    liquidada_sobre_receita_pct NUMERIC,
    empenhada_nao_liquidada NUMERIC NOT NULL,
    liquidada_nao_paga NUMERIC NOT NULL,
    rpnp_inscritos NUMERIC,
    UNIQUE (ente_id, tempo_id, fonte_id)
);
"""
