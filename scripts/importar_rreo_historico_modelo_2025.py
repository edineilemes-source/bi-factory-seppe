#!/usr/bin/env python3
"""STN/SICONFI: importar RREO Anexo 01 de Campo Grande, 2022-2026.

Usa o MESMO normalizador (core.siconfi.rreo_anexo01) e a MESMA transformação
(scripts.siconfi_rreo_dashboard_data.dashboard_row) do dataset 2025 existente.
Somente declara disponíveis bimestres com dados oficiais validados.
2026: consulta 1º a 5º; 6º ainda não encerrado em 19/11/2026.
Não altera o arquivo 2025, produtos, registros nem layouts.
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.siconfi.client import SiconfiClient, SiconfiRreoQuery
from core.siconfi.rreo_anexo01 import normalize_rreo_anexo01
from scripts.siconfi_rreo_dashboard_data import dashboard_row

IBGE = 5002704
ANEXO = "RREO-Anexo 01"
FISCAL_DIR = ROOT / "storage/reports/official_fiscal"
RAW_ROOT = ROOT / "storage/official/siconfi/rreo"
MANIFEST_DIR = ROOT / "artifacts/stn_campo_grande_2022_2026"
BASE_2025 = FISCAL_DIR / "rreo-2025-dashboard.csv"
HISTORY = FISCAL_DIR / "rreo-2022-2026-dashboard.csv"
AUDIT_PATH = MANIFEST_DIR / "auditoria_importacao.json"
CLIENT = SiconfiClient(timeout=65)
REQUIRED = {
    "ano", "bimestre", "receita_realizada_acumulada",
    "despesa_empenhada_acumulada", "despesa_liquidada_acumulada",
    "despesa_paga_acumulada", "resultado_orcamentario_formal",
    "margem_receita_menos_liquidada", "liquidada_nao_paga",
}
_last_request = 0.0


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".siconfi-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def atomic_json(path: Path, payload: object) -> None:
    atomic_bytes(path, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode())


def snapshot_path(year: int, period: int) -> Path:
    return RAW_ROOT / str(year) / "anexo01" / f"rreo-{year}-p{period}-anexo01.json"


def fetch_official(year: int, period: int) -> list[dict]:
    global _last_request
    query = SiconfiRreoQuery(exercicio=year, periodo=period, anexo=ANEXO,
                             id_ente=IBGE, esfera="M")
    base_url = CLIENT.build_rreo_url(query)
    result = []
    offset = 0
    while True:
        url = base_url + "&" + urllib.parse.urlencode({"limit": 5000, "offset": offset})
        payload = None
        for attempt in range(4):
            wait = 1.1 - (time.monotonic() - _last_request)
            if wait > 0:
                time.sleep(wait)
            _last_request = time.monotonic()
            try:
                request = urllib.request.Request(
                    url, headers={"Accept": "application/json",
                                  "User-Agent": "bi-factory-seppe/1.0"})
                with urllib.request.urlopen(request, timeout=65) as response:
                    payload = json.load(response)
                break
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                if attempt == 3:
                    raise RuntimeError(f"Falha na API STN {year}/{period}: {exc}") from exc
                time.sleep(min(15, 2 ** attempt + 1))
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise ValueError(f"API STN sem lista 'items': {year}/{period}")
        page = payload["items"]
        result.extend(page)
        if not payload.get("hasMore"):
            break
        if not page:
            raise ValueError(f"Paginação STN vazia com hasMore: {year}/{period}")
        offset += len(page)
        if offset > 50000:
            raise ValueError(f"Limite de segurança da paginação excedido: {year}/{period}")
    return result


def normalize(items: list[dict], year: int, period: int) -> dict:
    if not items:
        raise ValueError("STN ainda não disponibilizou registros para este bimestre")
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Item STN não é objeto JSON")
        if item.get("id_ente") not in (None, "") and int(item["id_ente"]) != IBGE:
            raise ValueError("STN retornou registros de município diferente")
    normalized = normalize_rreo_anexo01(items)
    if normalized.year != year or normalized.period != period:
        raise ValueError("STN retornou exercício ou bimestre diferente do consultado")
    row = dashboard_row(normalized)
    if not REQUIRED.issubset(row):
        raise ValueError("Contrato de dados fiscais incompatível com o modelo de 2025")
    return row


def get_period(year: int, period: int) -> tuple[dict, int, str]:
    path = snapshot_path(year, period)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload.get("items") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise ValueError(f"Snapshot local inválido: {path}")
        return normalize(items, year, period), len(items), "snapshot_existente"

    items = fetch_official(year, period)
    row = normalize(items, year, period)  # Só armazena depois da validação.
    snapshot = {
        "source": "STN/Siconfi",
        "exercicio": year, "periodo": period, "periodicidade": "B",
        "anexo": ANEXO, "id_ente": IBGE, "esfera": "M", "items": items,
    }
    atomic_json(path, snapshot)
    return row, len(items), "stn_importado"


def csv_rows(path: Path) -> tuple[list[dict], list[str]]:
    if not path.is_file():
        return [], []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        cols = list(reader.fieldnames or [])
        if not REQUIRED.issubset(cols):
            raise ValueError(f"{path.name} não possui todas as medidas obrigatórias: "
                             + repr(sorted(REQUIRED.difference(cols))))
        rows = list(reader)
    seen = set()
    for row in rows:
        try:
            year = int(row["ano"])
            period = int(row["bimestre"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Ano/bimestre inválido em {path.name}") from exc
        if year not in range(2022, 2027) or period not in range(1, 7):
            raise ValueError(f"Período fora do domínio em {path.name}: {year}/{period}")
        if (year, period) in seen:
            raise ValueError(f"Período duplicado em {path.name}: {year}/{period}")
        seen.add((year, period))
        for metric in REQUIRED.difference({"ano", "bimestre"}):
            if row.get(metric) in (None, "", "None"):
                raise ValueError(f"Medida obrigatória vazia: {year}/{period}/{metric}")
            float(row[metric])
    return rows, cols


def write_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="",
                                     prefix=".rreo-history-", suffix=".csv",
                                     dir=path.parent, delete=False) as output:
        pending = Path(output.name)
        writer = csv.DictWriter(output, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in cols})
        output.flush()
        os.fsync(output.fileno())
    try:
        if path.exists():
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            backups = MANIFEST_DIR / "backups"
            backups.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backups / (path.name + "." + stamp + ".bak"))
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def main() -> int:
    if not BASE_2025.is_file():
        raise RuntimeError("O CSV original de 2025 não foi encontrado; nada será sobrescrito.")
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    base_rows, base_cols = csv_rows(BASE_2025)
    if {int(r["bimestre"]) for r in base_rows if int(r["ano"]) == 2025} != set(range(1, 7)):
        raise RuntimeError("O modelo original de 2025 não contém os seis bimestres; importação bloqueada.")
    history_rows, history_cols = csv_rows(HISTORY)
    data: dict[tuple[int, int], dict] = {}
    for row in history_rows:
        data[(int(row["ano"]), int(row["bimestre"]))] = row
    # Os seis bimestres homologados de 2025 prevalecem sobre uma base de história prévia.
    for row in base_rows:
        if int(row["ano"]) == 2025:
            data[(2025, int(row["bimestre"]))] = row

    audit = {
        "fonte": CLIENT.base_url + "/rreo",
        "ente": "Campo Grande-MS", "id_ente": IBGE,
        "anexo": ANEXO, "executado_utc": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        "periodos": [],
        "observacao": "RREO acumulado por bimestre. Não somar os bimestres.",
    }
    fetched = 0
    for year in (2022, 2023, 2024, 2026):
        last = 5 if year == 2026 else 6
        for period in range(1, last + 1):
            item = {"ano": year, "bimestre": period}
            if (year, period) in data:
                item["situacao"] = "validado_na_base_local"
            else:
                try:
                    row, total, origin = get_period(year, period)
                    data[(year, period)] = row
                    fetched += 1
                    item.update(situacao="validado", registros_brutos=total, origem=origin)
                    print(f"VALIDADO {year}/{period}: {total} registros oficiais", flush=True)
                except Exception as exc:
                    item.update(situacao="pendente_ou_falha", detalhe=str(exc))
                    print(f"NÃO CARREGADO {year}/{period}: {exc}", flush=True)
            audit["periodos"].append(item)
            atomic_json(AUDIT_PATH, audit)

    audit["periodos"].append(
        {"ano": 2026, "bimestre": 6, "situacao": "não_encerrado_em_2026_11_19"})
    for period in range(1, 7):
        audit["periodos"].append(
            {"ano": 2025, "bimestre": period, "situacao": "csv_2025_preservado"})

    cols = list(dict.fromkeys(base_cols + history_cols))
    for row in data.values():
        for col in row:
            if col not in cols:
                cols.append(col)
    ordered = [data[key] for key in sorted(data)]
    write_csv(HISTORY, ordered, cols)
    audit["total_bimestres_validos"] = len(data)
    audit["bimestres_novos"] = fetched
    audit["cobertura"] = {
        str(year): sorted(period for (y, period) in data if y == year)
        for year in range(2022, 2027)
    }
    audit["arquivo_consolidado"] = str(HISTORY)
    atomic_json(AUDIT_PATH, audit)
    print("\n=== COBERTURA FINAL DO RREO ===")
    for year, periods in audit["cobertura"].items():
        print(year + ":", periods)
    print("CSV consolidado:", HISTORY)
    print("Auditoria:", AUDIT_PATH)
    if not any(y != 2025 for y, _ in data):
        print("ATENÇÃO: nenhuma informação histórica adicional foi recuperada.")
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print("IMPORTAÇÃO INTERROMPIDA:", error, file=sys.stderr)
        sys.exit(1)
