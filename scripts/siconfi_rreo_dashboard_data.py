from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.siconfi.rreo_anexo01 import load_rreo_year

SOURCE = PROJECT_ROOT / "storage/official/siconfi/rreo/2025/anexo01"
OUTPUT = PROJECT_ROOT / "storage/reports/official_fiscal"


def dashboard_row(item):
    analysis = item.analysis()
    return {
        "ano": item.year,
        "bimestre": item.period,
        "mes_fim": item.month_end,
        "receita_realizada_acumulada": item.revenue_ytd,
        "receita_no_bimestre": item.revenue_bimester,
        "despesa_empenhada_acumulada": item.committed_ytd,
        "despesa_liquidada_acumulada": item.liquidated_ytd,
        "despesa_liquidada_no_bimestre": item.liquidated_bimester,
        "despesa_paga_acumulada": item.paid_ytd,
        "resultado_orcamentario_formal": analysis.formal_budget_result,
        "margem_receita_menos_liquidada": analysis.revenue_liquidated_margin,
        "liquidada_sobre_receita_pct": analysis.liquidated_revenue_commitment_pct,
        "empenhada_nao_liquidada": analysis.committed_not_liquidated,
        "liquidada_nao_paga": analysis.liquidated_not_paid,
        "rpnp_inscritos": item.rpnp_registered,
        "receita_exceto_intra_acumulada": item.revenue_except_intra_ytd,
        "despesa_exceto_intra_liquidada_acumulada": item.expenditure_except_intra_liquidated_ytd,
    }


def main():
    series = load_rreo_year(SOURCE)
    rows = [dashboard_row(item) for item in series]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT / "rreo-2025-dashboard.json"
    csv_path = OUTPUT / "rreo-2025-dashboard.csv"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    final = series[-1]
    analysis = final.analysis()
    print("RREO 2025 normalizado para BI")
    print(f"Bimestres: {len(rows)}")
    print(f"Receita realizada: R$ {final.revenue_ytd:,.2f}")
    print(f"Despesa liquidada: R$ {final.liquidated_ytd:,.2f}")
    print(f"Receita - liquidada: R$ {analysis.revenue_liquidated_margin:,.2f}")
    print(f"Resultado formal (receita - empenhada): R$ {analysis.formal_budget_result:,.2f}")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
