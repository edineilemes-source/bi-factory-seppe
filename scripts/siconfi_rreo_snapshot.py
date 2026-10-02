from __future__ import annotations

from core.siconfi.client import SiconfiClient
from core.siconfi.snapshot import save_rreo_year_snapshot


CAMPO_GRANDE_IBGE = 5002704
RREO_ANEXO_01 = "RREO-Anexo 01"


if __name__ == "__main__":
    result = save_rreo_year_snapshot(
        SiconfiClient(),
        exercicio=2025,
        anexo=RREO_ANEXO_01,
        id_ente=CAMPO_GRANDE_IBGE,
        output_dir="storage/official/siconfi/rreo/2025/anexo01",
    )

    print("SICONFI RREO 2025 - Campo Grande/MS")
    for periodo in range(1, 7):
        print(f"P{periodo}: {result.period_counts.get(periodo, 0)} registros")
    print(f"TOTAL: {sum(result.period_counts.values())} registros")
    print(f"MANIFEST: {result.manifest_path}")
