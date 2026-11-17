#!/usr/bin/env python3
"""Install tested React + recovered Python modules in the CURRENT Codespaces.

- No checkout/reset/merge/rebase/push or storage/ modification.
- Strict target allowlist and clean-file checks against local HEAD.
- Backup and rollback on static/test/build or HTTP verification failure.
- API restart only for the uniquely identified BI Factory 8505 process.
- React keeps the same Codespaces 8506 URL.
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

ROOT = Path("/workspaces/bi-factory-seppe")
EXPECTED_LOCAL = "teste/cadastro-filtros-20261113"
MARKER = "751e292d4b06f41d79a3e7a1fc18b82e34c0ebcc"
REMOTE = "feat/integracao-react-pipeline-legado-20261117"
TESTED = "10c68b71cfdbc880d33a776f7477bf933800872c"
PATHS = [
    "scripts/serve_bi_factory_api.py",
    "scripts/bi_factory_analytics_adapter.py",
    "web/bi_factory/src/main.jsx",
    "web/bi_factory/src/DataWorkspace.jsx",
    "tests/test_react_analytics_bridge.py",
    "tests/test_react_analytics_http.py",
    "tests/e2e/test_unified_react_workspace.py",
    "tests/regression/test_prepared_grain_navigation.py",
]
APPS = [
    "scripts/serve_bi_factory_api.py",
    "scripts/bi_factory_analytics_adapter.py",
    "web/bi_factory/src/main.jsx",
    "web/bi_factory/src/DataWorkspace.jsx",
]

def run(*command, check=True):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError(f"{' '.join(command)}: {(result.stderr or result.stdout)[-2000:]}")
    return result

def git(*args):
    return run("git", *args).stdout

def request(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False

def wait_http(url, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if request(url): return True
        time.sleep(0.5)
    return False

def api_pids():
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit(): continue
        try:
            args = (entry / "cmdline").read_bytes().split(b"\0")
            if not any(b"serve_bi_factory_api.py" in arg for arg in args): continue
            if not any(arg == b"8505" for arg in args): continue
            cwd = (entry / "cwd").resolve()
            if cwd != ROOT: continue
            found.append(int(entry.name))
        except (OSError, PermissionError):
            continue
    return found

def stop_api():
    pids = api_pids()
    if len(pids) > 1:
        raise RuntimeError("Mais de um processo 8505 identificado; implantação recusada")
    if not pids:
        if request("http://127.0.0.1:8505/api/overview"):
            raise RuntimeError("8505 ocupada por processo desconhecido; não interrompido")
        return
    pid = pids[0]
    os.kill(pid, signal.SIGTERM)
    for _ in range(50):
        try:
            os.kill(pid, 0)
            state = (Path("/proc") / str(pid) / "status").read_text(errors="replace")
            if "State:" in state and "Z (zombie)" in state: break
        except (ProcessLookupError, FileNotFoundError): break
        time.sleep(0.1)
    else:
        raise RuntimeError("Serviço API não encerrou após SIGTERM; nenhuma ação destrutiva")

def start_api():
    logdir = Path("/tmp/bi-factory-seppe-logs")
    logdir.mkdir(exist_ok=True)
    logfile = (logdir / "api-8505.log").open("ab")
    try:
        subprocess.Popen(
            [sys.executable, "-u", str(ROOT / "scripts/serve_bi_factory_api.py"), "--port", "8505"],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=logfile,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
    finally:
        logfile.close()
    if not wait_http("http://127.0.0.1:8505/api/overview", seconds=30):
        raise RuntimeError("API 8505 não respondeu; consulte /tmp/bi-factory-seppe-logs/api-8505.log")

def main():
    if not (ROOT/".git").is_dir():
        raise RuntimeError("Repositório Codespaces não localizado")
    local = git("branch", "--show-current").strip()
    if local != EXPECTED_LOCAL:
        raise RuntimeError("Branch local inesperada: "+local)
    run("git","merge-base","--is-ancestor",MARKER,"HEAD")
    git("fetch","--no-tags","origin",REMOTE)
    remote_sha=git("rev-parse","FETCH_HEAD").strip()
    # All deployable files must be byte-identical to an already completely tested revision.
    for rel in PATHS:
        delta=run("git","diff","--quiet",TESTED,remote_sha,"--",rel,check=False)
        if delta.returncode:
            raise RuntimeError("Código remoto mudou após os quatro testes verdes: "+rel)
    originals={}
    incoming={}
    for rel in PATHS:
        target=ROOT/rel
        if target.is_symlink(): raise RuntimeError("Caminho simbólico recusado: "+rel)
        exists=target.exists()
        if exists and not target.is_file(): raise RuntimeError("Caminho não regular: "+rel)
        old=target.read_bytes() if exists else None
        command=run("git","show",f"{TESTED}:{rel}",check=False)
        if command.returncode: raise RuntimeError("Arquivo faltando no commit validado: "+rel)
        # git show decoded as text: target files in this allowlist must all be UTF-8.
        new=command.stdout.encode("utf-8")
        if old != new:
            if exists:
                tracked=run("git","ls-files","--error-unmatch","--",rel,check=False)
                if tracked.returncode:
                    raise RuntimeError("Arquivo não rastreado já existe; não sobrescrever: "+rel)
                clean=run("git","diff","--quiet","HEAD","--",rel,check=False)
                staged=run("git","diff","--cached","--quiet","--",rel,check=False)
                if clean.returncode or staged.returncode:
                    raise RuntimeError("Alteração local precisa ser preservada: "+rel)
            originals[rel]=old
            incoming[rel]=new
    if not incoming:
        print("ARQUIVOS JÁ IGUAIS À VERSÃO TESTADA",flush=True)
        return
    stamp=datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup=ROOT/".git"/"backups"/f"reativacao-motores-{stamp}"
    for rel, original in originals.items():
        if original is not None:
            saved=backup/rel
            saved.parent.mkdir(parents=True,exist_ok=True)
            saved.write_bytes(original)
    print("BACKUP:",backup,flush=True)
    print("Arquivos autorizados:",", ".join(incoming),flush=True)
    changed = []
    stopped=False
    def rollback_files():
        for rel in changed:
            file=ROOT/rel
            original=originals[rel]
            if original is None: file.unlink(missing_ok=True)
            else: file.write_bytes(original)
    try:
        for rel,data in incoming.items():
            target=ROOT/rel
            target.parent.mkdir(parents=True,exist_ok=True)
            temp=target.with_name(target.name+".bi-new")
            if temp.exists(): raise RuntimeError("Arquivo temporário pré-existente: "+str(temp))
            try:
                temp.write_bytes(data)
                if target.exists(): os.chmod(temp,target.stat().st_mode & 0o777)
                os.replace(temp,target)
            finally:
                temp.unlink(missing_ok=True)
            changed.append(rel)
        run(sys.executable,"-m","py_compile",*["scripts/serve_bi_factory_api.py","scripts/bi_factory_analytics_adapter.py"])
        run(sys.executable,"-m","unittest","tests.test_react_analytics_bridge","tests.test_react_analytics_http","-q")
        run("npm","run","build","--prefix","web/bi_factory")
        print("TESTES SINTÉTICOS E BUILD APROVADOS NO CODESPACES",flush=True)
        stopped=True
        stop_api()
        start_api()
        for url in [
            "http://127.0.0.1:8506/",
            "http://127.0.0.1:8506/api/analytics/capabilities",
            "http://127.0.0.1:8506/api/overview",
        ]:
            if not wait_http(url,seconds=15):
                raise RuntimeError("Rota unificada não respondeu: "+url)
    except Exception:
        rollback_files()
        if stopped:
            try:
                stop_api()
                start_api()
                print("API anterior restaurada",flush=True)
            except Exception as err:
                print("ALERTA: arquivos revertidos, mas reinicialização da API antiga falhou:",err,flush=True)
        raise
    print("INTEGRAÇÃO REACT + MOTORES PYTHON IMPLANTADA E VERIFICADA",flush=True)
    print("GitHub código testado:",TESTED,flush=True)
    print("Mesmo Codespaces e porta 8506. Use F5 para verificar.",flush=True)
    print("Sem troca de branch, commit, push, reset, limpeza ou alteração de storage operacional.",flush=True)

if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print("IMPLANTAÇÃO BLOQUEADA:",exc,file=sys.stderr,flush=True)
        sys.exit(1)
