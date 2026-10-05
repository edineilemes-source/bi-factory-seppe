from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.fiscal_dw import FISCAL_DW_DDL

SOURCE = PROJECT_ROOT / "storage/reports/official_fiscal/rreo-2025-dashboard.csv"
TARGET = PROJECT_ROOT / "storage/reports/official_fiscal/fiscal_dw.sqlite"


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Dataset não encontrado: {SOURCE}")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(TARGET)
    connection.executescript(FISCAL_DW_DDL)
    connection.execute(
        "INSERT OR IGNORE INTO dim_ente(ente_id,cod_ibge,nome,uf,esfera) VALUES (1,5002704,?,?,?)",
        ("Prefeitura Municipal de Campo Grande", "MS", "M"),
    )
    connection.execute(
        "INSERT OR IGNORE INTO dim_fonte_fiscal(fonte_id,sistema,demonstrativo,anexo,origem) VALUES (1,?,?,?,?)",
        ("SICONFI", "RREO", "RREO-Anexo 01", "STN/SICONFI API"),
    )
    with SOURCE.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            year, period, month_end = int(row["ano"]), int(row["bimestre"]), int(row["mes_fim"])
            tempo_id = year * 10 + period
            connection.execute(
                "INSERT OR REPLACE INTO dim_tempo_fiscal(tempo_id,exercicio,bimestre,mes_fim,periodicidade) VALUES (?,?,?,?,?)",
                (tempo_id, year, period, month_end, "B"),
            )
            fields = [
                "receita_realizada_acumulada", "receita_no_bimestre", "despesa_empenhada_acumulada",
                "despesa_liquidada_acumulada", "despesa_liquidada_no_bimestre", "despesa_paga_acumulada",
                "resultado_orcamentario_formal", "margem_receita_menos_liquidada", "liquidada_sobre_receita_pct",
                "empenhada_nao_liquidada", "liquidada_nao_paga", "rpnp_inscritos",
            ]
            values = [float(row[name]) if row[name] not in ("", "None") else None for name in fields]
            connection.execute(
                """INSERT OR REPLACE INTO fato_execucao_orcamentaria(
                fato_id,ente_id,tempo_id,fonte_id,
                receita_realizada_acumulada,receita_no_bimestre,despesa_empenhada_acumulada,
                despesa_liquidada_acumulada,despesa_liquidada_no_bimestre,despesa_paga_acumulada,
                resultado_orcamentario_formal,margem_receita_menos_liquidada,liquidada_sobre_receita_pct,
                empenhada_nao_liquidada,liquidada_nao_paga,rpnp_inscritos) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [tempo_id, 1, tempo_id, 1, *values],
            )
    connection.commit()
    count = connection.execute("SELECT COUNT(*) FROM fato_execucao_orcamentaria").fetchone()[0]
    print(f"DW fiscal criado: {TARGET}")
    print(f"Fatos: {count}")
    print("Dimensões: dim_ente, dim_tempo_fiscal, dim_fonte_fiscal")
    connection.close()


if __name__ == "__main__":
    main()
