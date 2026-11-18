#!/usr/bin/env python3
"""One-shot guarded project onboarding update for the EXISTING Codespaces.

Only update allowlisted files after verifying local versions match the last
successful React/Python deployment. Never reset, checkout, merge, stage,
commit, push or touch operational storage. Back up and roll back on failures.
"""
from pathlib import Path
import datetime
import os
import signal
import subprocess
import sys
import time
import urllib.request

ROOT=Path("/workspaces/bi-factory-seppe")
BRANCH="teste/cadastro-filtros-20261113"
BASELINE="10c68b71cfdbc880d33a776f7477bf933800872c"
TARGET="7c8596b97236c317afaaea924c1ef13c5e69c174"
REMOTE="feat/onboarding-projetos-conhecimento-20261117"
FILES=[
    "scripts/serve_bi_factory_api.py",
    "scripts/bi_factory_projects.py",
    "web/bi_factory/src/main.jsx",
    "web/bi_factory/src/ProjectHome.jsx",
    "web/bi_factory/src/KnowledgeStart.jsx",
    "web/bi_factory/src/DataWorkspace.jsx",
    "tests/test_projects_knowledge_http.py",
    "tests/e2e/test_project_knowledge_onboarding.py",
    "tests/e2e/test_unified_react_workspace.py",
]

def cmd(*argv,check=True):
    p=subprocess.run(argv,cwd=ROOT,capture_output=True)
    if check and p.returncode:
        raise RuntimeError(" ".join(argv)+": "+(p.stderr or p.stdout).decode(errors="replace")[-1800:])
    return p

def show(sha,name):
    p=cmd("git","show",f"{sha}:{name}",check=False)
    return p.stdout if p.returncode==0 else None

def http(url):
    try:
        with urllib.request.urlopen(url,timeout=3) as response:
            return response.status==200
    except Exception:
        return False

def pids():
    results=[]
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():continue
        try:
            args=(p/"cmdline").read_bytes().split(b"\0")
            if not any(b"serve_bi_factory_api.py" in x for x in args):continue
            if not any(x==b"8505" for x in args):continue
            if (p/"cwd").resolve()==ROOT:results.append(int(p.name))
        except (OSError,PermissionError):pass
    return results

def stop():
    found=pids()
    if len(found)>1:raise RuntimeError("Múltiplos processos da API identificados")
    if not found:
        if http("http://127.0.0.1:8505/api/overview"):
            raise RuntimeError("Porta 8505 ocupada por API desconhecida")
        return
    pid=found[0]
    os.kill(pid,signal.SIGTERM)
    for _ in range(60):
        try:
            os.kill(pid,0)
            status=(Path("/proc")/str(pid)/"status").read_text(errors="replace")
            if "Z (zombie)" in status:break
        except (ProcessLookupError,FileNotFoundError):break
        time.sleep(0.1)
    else:raise RuntimeError("API anterior não encerrou; parada sem forçar encerramento")

def start():
    logs=Path("/tmp/bi-factory-seppe-logs");logs.mkdir(exist_ok=True)
    with (logs/"api-8505.log").open("ab") as stream:
        subprocess.Popen([sys.executable,"-u",str(ROOT/"scripts/serve_bi_factory_api.py"),"--port","8505"],
                         cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,
                         start_new_session=True)
    for _ in range(60):
        if http("http://127.0.0.1:8505/api/projects"):return
        time.sleep(0.5)
    raise RuntimeError("API 8505 não respondeu ao catálogo de projetos")

def main():
    if not (ROOT/".git").is_dir():raise RuntimeError("Codespaces esperado não encontrado")
    if cmd("git","branch","--show-current").stdout.decode().strip()!=BRANCH:
        raise RuntimeError("Branch local inesperada; nenhum arquivo alterado")
    # Ensure this same branch contains the frozen release, not another checkout.
    cmd("git","merge-base","--is-ancestor","751e292d4b06f41d79a3e7a1fc18b82e34c0ebcc","HEAD")
    cmd("git","fetch","--no-tags","origin",REMOTE)
    remote_sha=cmd("git","rev-parse","FETCH_HEAD").stdout.decode().strip()
    for name in FILES:
        if show(TARGET,name)!=show(remote_sha,name):
            raise RuntimeError("Arquivo diverge da versão testada: "+name)
    originals={};changes={}
    for name in FILES:
        path=ROOT/name
        if path.is_symlink():raise RuntimeError("Link simbólico recusado: "+name)
        old=path.read_bytes() if path.is_file() else None
        new=show(TARGET,name)
        if new is None:raise RuntimeError("Arquivo não encontrado no commit testado: "+name)
        if old==new:continue
        previous=show(BASELINE,name)
        if old!=previous:
            raise RuntimeError("Alterações locais não reconhecidas em "+name+"; nada foi alterado")
        originals[name]=old;changes[name]=new
    if not changes:
        print("Projeto e Conhecimento já correspondem à versão testada")
        return
    stamp=datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup=ROOT/".git"/"backups"/("projetos-conhecimento-"+stamp)
    for name,content in originals.items():
        if content is not None:
            out=backup/name
            out.parent.mkdir(parents=True,exist_ok=True)
            out.write_bytes(content)
    print("Backup:",backup,flush=True)
    updated=[];stopped=False
    def rollback():
        for name in updated:
            old=originals[name];path=ROOT/name
            if old is None:path.unlink(missing_ok=True)
            else:path.write_bytes(old)
    try:
        for name,data in changes.items():
            path=ROOT/name;path.parent.mkdir(parents=True,exist_ok=True)
            tmp=path.with_name(path.name+".onboarding-new")
            if tmp.exists():raise RuntimeError("Arquivo temporário preexistente: "+name)
            try:
                tmp.write_bytes(data)
                if path.exists():os.chmod(tmp,path.stat().st_mode&0o777)
                os.replace(tmp,path)
            finally:
                tmp.unlink(missing_ok=True)
            updated.append(name)
        cmd(sys.executable,"-m","py_compile","scripts/serve_bi_factory_api.py","scripts/bi_factory_projects.py")
        cmd(sys.executable,"-m","unittest","tests.test_projects_knowledge_http","-q")
        cmd("npm","run","build","--prefix","web/bi_factory")
        print("Testes de projetos, conhecimento e build aprovados localmente",flush=True)
        stopped=True
        stop();start()
        for url in ("http://127.0.0.1:8506/","http://127.0.0.1:8506/api/projects",
                    "http://127.0.0.1:8506/api/overview"):
            if not http(url):raise RuntimeError("Rota inacessível: "+url)
    except Exception:
        rollback()
        if stopped:
            try:stop();start()
            except Exception as error:print("ATENÇÃO: restaurado o código, API pode exigir reinício:",error,flush=True)
        raise
    print("ONBOARDING DE PROJETOS E CONHECIMENTO INSTALADO E VERIFICADO",flush=True)
    print("Mesmo Codespaces, porta 8506, sem alterações de dados/produtos antigos",flush=True)
    print("Commit do código validado:",TARGET,flush=True)

if __name__=="__main__":
    try:main()
    except Exception as e:
        print("IMPLANTAÇÃO BLOQUEADA:",e,file=sys.stderr,flush=True)
        sys.exit(1)
