#!/usr/bin/env python3
"""Ponte experimental GitHub Issues -> homologação Codespaces.

Apenas uma tarefa predefinida; NÃO executa shell fornecido por issues.
Requer GitHub CLI autenticado no Codespaces e Codespaces ligado.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(os.environ.get("BI_FACTORY_ROOT", pathlib.Path(__file__).resolve().parent.parent))
REPO = "edineilemes-source/bi-factory-seppe"
OWNER = "edineilemes-source"
TITLE = "[BI-AGENT] HOMOLOGAR"
REMOTE = "homolog/cadastro-filtros-echarts-20261113"
LOCAL = "teste/cadastro-filtros-20261113"
STATE = pathlib.Path("/tmp/bi-factory-agent-processed.json")
LOG = pathlib.Path("/tmp/bi-factory-seppe-logs")
LOG.mkdir(parents=True, exist_ok=True)


def run(args, cwd=ROOT, timeout=180, check=True):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f"{' '.join(args)}: {result.stderr[-900:] or result.stdout[-900:]}")
    return result.stdout.strip()


def gh(*args):
    return run(["gh", *args], timeout=40)


def report(number, message):
    gh("issue", "comment", str(number), "--repo", REPO, "--body", message[:4000])


def processed():
    try:
        return set(json.loads(STATE.read_text()))
    except (FileNotFoundError, ValueError):
        return set()


def mark(number):
    seen = processed()
    seen.add(number)
    STATE.write_text(json.dumps(sorted(seen)))


def homologate():
    # Nunca trocar branch com modificações rastreadas pendentes.
    status = run(["git", "status", "--porcelain", "--untracked-files=no"])
    if status:
        raise RuntimeError("Há alterações rastreadas locais; homologação bloqueada para preservar trabalho.")
    run(["git", "fetch", "origin", REMOTE], timeout=120)
    # show-ref não produz saída; verificar código de retorno diretamente.
    has_branch = subprocess.run(["git", "show-ref", "--verify", "--quiet", "refs/heads/" + LOCAL],
                                cwd=ROOT).returncode == 0
    if has_branch:
        run(["git", "switch", LOCAL])
    else:
        run(["git", "switch", "--track", "-c", LOCAL, "origin/" + REMOTE])
    run(["git", "merge", "--ff-only", "origin/" + REMOTE])
    web = ROOT / "web" / "bi_factory"
    if not (web / "node_modules" / ".bin" / "vite").exists():
        run(["npm", "ci"], cwd=web, timeout=300)
    build = run(["npm", "run", "build"], cwd=web, timeout=300)
    # Encerrar apenas listeners das portas do BI Factory.
    for port in (8505, 8506):
        ids = run(["lsof", "-tiTCP:" + str(port), "-sTCP:LISTEN"], check=False)
        for pid in ids.splitlines():
            if pid.isdecimal():
                run(["kill", pid], check=False)
    time.sleep(2)
    started = run(["bash", "scripts/start_bi_factory_codespaces.sh"], timeout=100)
    commit = run(["git", "rev-parse", "--short", "HEAD"])
    return f"Homologação iniciada. Commit: `{commit}`.\n\n```\n{started[-1500:]}\n```\nBuild: {build[-180:]}"


def cycle():
    issues = json.loads(gh("issue", "list", "--repo", REPO, "--state", "open",
                          "--limit", "100", "--json", "number,title,author"))
    seen = processed()
    for issue in issues:
        number = issue["number"]
        if number in seen or issue["title"] != TITLE:
            continue
        # Rejeitar solicitações de terceiros mesmo em repositório público.
        if issue.get("author", {}).get("login", "").lower() != OWNER:
            continue
        mark(number)  # evita repetição inclusive em caso de falha
        try:
            report(number, "Agente recebeu tarefa permitida: homologar branch fixa. Iniciando.")
            result = homologate()
            report(number, "✅ " + result)
            gh("issue", "close", str(number), "--repo", REPO,
               "--comment", "Concluído pelo agente Codespaces.")
        except Exception as error:
            report(number, "❌ Falha na homologação (sem limpar dados): " + str(error)[-2000:])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    # Verificar autenticação antes de iniciar o loop.
    gh("auth", "status")
    print("BI Factory Agent: aguardando issues autorizadas", flush=True)
    while True:
        try:
            cycle()
        except Exception as error:
            print("Erro de consulta:", error, flush=True)
        if args.once:
            break
        time.sleep(30)


if __name__ == "__main__":
    main()
