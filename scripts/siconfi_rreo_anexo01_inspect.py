from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BASE = PROJECT_ROOT / "storage/official/siconfi/rreo/2025/anexo01"

KEYWORDS = (
    "RECEITA",
    "DESPESA",
    "EMPENH",
    "LIQUID",
    "PAG",
    "INTRA-ORÇAMENT",
    "INTRAORÇAMENT",
)


def load_items(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload.get("items", [])
    if isinstance(payload, list):
        return payload
    raise ValueError(f"Formato inesperado: {path}")


def main() -> None:
    files = sorted(p for p in BASE.glob("*.json") if "manifest" not in p.name)
    if not files:
        raise SystemExit(f"Nenhum snapshot encontrado em {BASE}")

    print("=== RREO ANEXO 01 / CAMPO GRANDE 2025 ===")
    print("Arquivos:", len(files))

    for path in files:
        items = load_items(path)
        periodo = items[0].get("periodo") if items else "?"
        print(f"\n=== P{periodo} | {path.name} | {len(items)} registros ===")

        columns = sorted({str(i.get("coluna")) for i in items})
        print("COLUNAS:")
        for col in columns:
            print(" -", col)

        by_account: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for item in items:
            account = str(item.get("conta") or "")
            code = str(item.get("cod_conta") or "")
            if any(k in account.upper() or k in code.upper() for k in KEYWORDS):
                by_account[(code, account)].append(item)

        print("\nCONTAS CANDIDATAS / VALORES:")
        for (code, account), rows in sorted(by_account.items()):
            # Prioritize totals and high-level STN accounts; keep output manageable.
            upper = account.upper()
            if not (
                code.lower().startswith(("receita", "despesa"))
                or "TOTAL" in upper
                or "RECEITAS (" in upper
                or "DESPESAS (" in upper
            ):
                continue
            print(f"\n[{code}] {account}")
            for row in rows:
                print(f"  {row.get('coluna')}: {row.get('valor')}")


if __name__ == "__main__":
    main()
