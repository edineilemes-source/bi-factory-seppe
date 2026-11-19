#!/usr/bin/env python3
"""Carga histórica RREO para Codespaces com ativação segura na API 8505.

Obtém script versionado do GitHub já buscado por git fetch, não altera a branch
atual, reaproveita os seis bimestres originais de 2025, preserva produtos/dados.
"""
from pathlib import Path
import csv
import datetime
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path("/workspaces/bi-factory-seppe")
REMOTE = "origin/fix/carga-rreo-historica-real-20261119"
IMPORT = "scripts/importar_rreo_historico_modelo_2025.py"
HANDLER = "prototypes/editor-visual/server.py"
HISTORICAL = ROOT / "storage/reports/official_fiscal/rreo-2022-2026-dashboard.csv"

OLD_LINE = '                source = ROOT / "storage/reports/official_fiscal/rreo-2025-dashboard.csv"'
NEW_LINE = '''                historical = ROOT / "storage/reports/official_fiscal/rreo-2022-2026-dashboard.csv"
                legacy = ROOT / "storage/reports/official_fiscal/rreo-2025-dashboard.csv"
                source = historical if historical.is_file() else legacy'''


def git_show(path):
    result = subprocess.run(["git", "show", REMOTE + ":" + path],
                            cwd=ROOT, capture_output=True)
    if result.returncode:
        raise RuntimeError("Não foi possível recuperar script oficial do GitHub: " +
                           result.stderr.decode(errors="replace")[-500:])
    return result.stdout


def periods_from_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        data = list(csv.DictReader(f))
    result = {}
    for row in data:
        y, p = int(row["ano"]), int(row["bimestre"])
        result.setdefault(y, set()).add(p)
    return {year: sorted(periods) for year, periods in sorted(result.items())}


def port_open():
    try:
        with socket.create_connection(("127.0.0.1", 8505), timeout=1):
            return True
    except OSError:
        return False


def api_periods():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8505/api/fiscal", timeout=10) as response:
            payload = json.load(response)
        if not isinstance(payload, list):
            return None
        result = {}
        for row in payload:
            y = int(row.get("ano") or row.get("exercicio"))
            p = int(row["bimestre"])
            result.setdefault(y, set()).add(p)
        return {year: sorted(periods) for year, periods in sorted(result.items())}
    except Exception:
        return None


def restart_api():
    matching = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            args = (proc / "cmdline").read_bytes().split(bytes([0]))
            if not any(b"serve_bi_factory_api.py" in arg for arg in args):
                continue
            if not any(arg == b"8505" for arg in args):
                continue
            if (proc / "cwd").resolve() != ROOT:
                continue
            matching.append(int(proc.name))
        except (PermissionError, OSError):
            continue

    if len(matching) > 1:
        print("ATENÇÃO: vários processos 8505 encontrados; não foi realizado reinício arriscado.")
        return False

    if matching:
        print("Reiniciando somente a API conhecida 8505 (PID", matching[0], ")")
        os.kill(matching[0], signal.SIGTERM)
        for _ in range(50):
            if not port_open():
                break
            time.sleep(0.2)
        else:
            print("ATENÇÃO: processo antigo não liberou a porta 8505.")
            return False
    elif port_open():
        print("ATENÇÃO: porta 8505 ocupada por processo não identificado; preservada.")
        return False

    logs = Path("/tmp/bi-factory-seppe-logs")
    logs.mkdir(parents=True, exist_ok=True)
    with (logs / "api-8505.log").open("ab") as output:
        subprocess.Popen(
            [sys.executable, "-u", str(ROOT / "scripts/serve_bi_factory_api.py"), "--port", "8505"],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    for _ in range(50):
        if api_periods() is not None:
            return True
        time.sleep(0.4)
    print("ATENÇÃO: API não iniciou. Consulte " + str(logs / "api-8505.log"))
    return False


def main():
    if not (ROOT / ".git").is_dir():
        raise RuntimeError("Não encontrei /workspaces/bi-factory-seppe.")
    original = ROOT / IMPORT
    candidate = git_show(IMPORT)
    if original.exists():
        if original.is_symlink() or original.read_bytes() != candidate:
            raise RuntimeError("Arquivo de importação local divergente; não sobrescrever: " + IMPORT)
    else:
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_bytes(candidate)

    subprocess.run([sys.executable, "-m", "py_compile", str(original)],
                   cwd=ROOT, check=True)
    print("Executando coleta oficial STN/SICONFI e normalização do modelo 2025...", flush=True)
    outcome = subprocess.run([sys.executable, str(original)], cwd=ROOT, check=False)
    if outcome.returncode:
        print("Coleta parcial ou não concluída. Consultar o manifesto de auditoria.")
    if not HISTORICAL.is_file():
        print("Sem CSV histórico validado. API preservada, somente 2025 continua disponível.")
        return 2

    periods = periods_from_csv(HISTORICAL)
    print("Bimestres presentes no CSV consolidado:")
    for year in range(2022, 2027):
        print(" ", year, periods.get(year, []))
    if not any(periods.get(year) for year in (2022, 2023, 2024, 2026)):
        print("NENHUM BIMESTRE ADICIONAL validado; API preservada sem modificação.")
        return 2

    handler = ROOT / HANDLER
    if not handler.is_file() or handler.is_symlink():
        raise RuntimeError("Handler da API inexistente ou link simbólico.")
    code = handler.read_text(encoding="utf-8")
    if NEW_LINE in code:
        print("Handler fiscal já aponta para o CSV consolidado.")
    else:
        if code.count(OLD_LINE) != 1:
            raise RuntimeError("Handler fiscal diferente da versão conhecida; dados mantidos, API não alterada.")
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = ROOT / ".git/backups" / ("rreo-historico-api-" + stamp) / HANDLER
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(handler, backup)
        updated = code.replace(OLD_LINE, NEW_LINE, 1)
        with open(handler, "w", encoding="utf-8") as f:
            f.write(updated)
        try:
            subprocess.run([sys.executable, "-m", "py_compile", str(handler)], check=True)
        except Exception:
            shutil.copy2(backup, handler)
            raise
        print("Handler atualizado, backup:", backup)

    if not restart_api():
        print("Dados consolidados salvos, mas API 8505 ainda precisa de reinício controlado.")
        return 2
    delivered = api_periods()
    print("\n=== API /api/fiscal APÓS ATUALIZAÇÃO ===")
    print(json.dumps(delivered, ensure_ascii=False, indent=2))
    if delivered is None or not any(delivered.get(y) for y in (2022, 2023, 2024, 2026)):
        print("ATENÇÃO: API não retornou o histórico adicional. Conferir logs e handler.")
        return 2
    print("CARGA HISTÓRICA ATIVA: ECharts e Editor Visual podem consultar os anos importados.")
    print("Produtos, layouts e seis bimestres originais de 2025 preservados.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("INTEGRAÇÃO BLOQUEADA:", exc, file=sys.stderr)
        sys.exit(1)
