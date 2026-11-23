#!/usr/bin/env python3
"""Patch 502 lab 8507, preserving the stable 8506 and all data/products.

- Install only 8507 server, 8507 frontend and dedicated regression test.
- Accept only exact original lab files or already-installed fix.
- Restart only a uniquely identified lab 8507 process (never 8506/8505).
- Verify state and fiscal endpoints separately; fall back to read-only CSV.
"""
from __future__ import annotations
import datetime
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT=Path("/workspaces/bi-factory-seppe")
BASE="origin/feat/lab-echarts-eixos-8507-20261119"
FIX="origin/fix/lab8507-fonte-historica-e-reinicio-20261123"
SERVER=ROOT/"scripts/serve_echarts_axes_8507.py"
FILES=(
 "scripts/serve_echarts_axes_8507.py",
 "experiments/echarts-axes-8507/app.js",
 "scripts/test_lab_8507_fiscal_fallback.py",
)
URL="http://127.0.0.1:8507"
LOG=Path("/tmp/bi-factory-seppe-logs/lab-echarts-8507.log")

def git_file(ref,name):
    p=subprocess.run(["git","show",ref+":"+name],cwd=ROOT,capture_output=True)
    return p.stdout if p.returncode==0 else None

def fingerprint(blob):
    return hashlib.sha256(blob).hexdigest()[:16]

def validate_code(files):
    with tempfile.TemporaryDirectory(prefix="lab8507-fix-") as tmp:
        for name,data in files.items():
            dest=Path(tmp)/Path(name).name
            dest.write_bytes(data)
            if name.endswith(".js"):
                cmd=["node","--check",str(dest)]
            elif name.endswith(".py"):
                cmd=[sys.executable,"-m","py_compile",str(dest)]
            else:
                continue
            result=subprocess.run(cmd,capture_output=True,text=True)
            if result.returncode:raise RuntimeError("Sintaxe inválida em "+name+": "+result.stderr[-800:])

def read_api(endpoint,timeout=4):
    with urllib.request.urlopen(URL+endpoint,timeout=timeout) as response:
        result=json.load(response)
    return result

def is_listening(port):
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1",port))==0

def known_server_pids():
    result=[]
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            parts=(entry/"cmdline").read_bytes().split(b"\x00")
            argv=[p.decode(errors="replace") for p in parts if p]
            if str(SERVER) not in argv:
                continue
            if "--port" not in argv or argv[argv.index("--port")+1]!="8507":
                continue
            if (entry/"cwd").resolve()!=ROOT:
                continue
            result.append(int(entry.name))
        except (OSError,IndexError,PermissionError,ValueError):
            continue
    return result

def restart_experimental_server():
    current=known_server_pids()
    if len(current)>1:
        raise RuntimeError("Mais de um processo experimental 8507 encontrado; encerramento automático recusado.")
    if current:
        pid=current[0]
        print("Reiniciando SOMENTE o laboratório 8507, PID",pid)
        os.kill(pid,signal.SIGTERM)
        for _ in range(60):
            if not is_listening(8507):
                break
            time.sleep(.2)
        else:
            raise RuntimeError("Servidor antigo 8507 não liberou a porta; não forçar encerramento.")
    elif is_listening(8507):
        raise RuntimeError("Porta 8507 ocupada por servidor não identificado; mantido sem encerramento.")
    LOG.parent.mkdir(parents=True,exist_ok=True)
    with LOG.open("ab") as stream:
        subprocess.Popen(
            [sys.executable,"-u",str(SERVER),"--host","127.0.0.1","--port","8507"],
            cwd=ROOT,stdin=subprocess.DEVNULL,
            stdout=stream,stderr=subprocess.STDOUT,start_new_session=True,
        )
    for _ in range(70):
        try:
            health=read_api("/api/health",timeout=2)
            if health.get("lab")=="echarts-axes" and health.get("port")==8507 and health.get("fallback_csv"):
                print("SERVIDOR EXPERIMENTAL 8507 ATUALIZADO")
                return
        except (OSError,ValueError,KeyError):
            pass
        time.sleep(.2)
    raise RuntimeError("Não foi possível confirmar reinício da 8507. Log: "+str(LOG))

def main():
    if not (ROOT/".git").is_dir():
        raise RuntimeError("Repositório BI Factory SEPPE não encontrado neste Codespaces.")
    updates={}
    expected={}
    for name in FILES:
        path=ROOT/name
        if path.is_symlink():raise RuntimeError("Arquivo é link simbólico, atualização cancelada: "+name)
        before=path.read_bytes() if path.is_file() else None
        old=git_file(BASE,name)
        new=git_file(FIX,name)
        if new is None:raise RuntimeError("Arquivo da correção não encontrado: "+name)
        expected[name]=new
        if before==new:
            print("JÁ ATUALIZADO:",name)
            continue
        if before!=old:
            print("Arquivo local:",fingerprint(before or b""),
                  "Base:",fingerprint(old or b""),"Destino:",fingerprint(new))
            raise RuntimeError("Arquivo local divergente; nenhuma substituição: "+name)
        if before is None and old is not None:
            raise RuntimeError("Arquivo da 8507 ausente: "+name)
        updates[name]=(before,new)
        print("CORREÇÃO PREPARADA:",name)
    validate_code(expected)
    backup=ROOT/".git"/"backups"/("lab8507-fix502-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    for name,(old,_) in updates.items():
        if old is None:continue
        archive=backup/name
        archive.parent.mkdir(parents=True,exist_ok=True)
        archive.write_bytes(old)
    installed=[]
    try:
        for name,(old,new) in updates.items():
            dest=ROOT/name;dest.parent.mkdir(parents=True,exist_ok=True)
            pending=dest.with_name(dest.name+".8507-fix-pending")
            if pending.exists():raise RuntimeError("Arquivo temporário já existe: "+str(pending))
            try:
                pending.write_bytes(new)
                if dest.exists():os.chmod(pending,dest.stat().st_mode&0o777)
                os.replace(pending,dest);installed.append(name)
            finally:
                pending.unlink(missing_ok=True)
        subprocess.run([sys.executable,"scripts/test_lab_8507_fiscal_fallback.py"],
                       cwd=ROOT,check=True)
        subprocess.run(["node","scripts/test_echarts_axes_8507.js"],
                       cwd=ROOT,check=True)
        subprocess.run(["node","scripts/test_lab_ui_contract_8507.js"],
                       cwd=ROOT,check=True)
    except Exception:
        for name in installed:
            old=updates[name][0]
            dest=ROOT/name
            if old is None:dest.unlink(missing_ok=True)
            else:dest.write_bytes(old)
        raise
    if installed:print("Arquivos corrigidos:",", ".join(installed))
    if backup.exists():print("Backup dos arquivos 8507:",backup)
    restart_experimental_server()
    for route in ("/api/state","/api/fiscal","/api/source"):
        try:
            data=read_api(route,timeout=10)
            if route=="/api/state":
                print("OK /api/state —",len(data.get("objects",[])),"objetos do rascunho preservados")
            elif route=="/api/fiscal":
                if not isinstance(data,list):raise ValueError("API não entregou lista fiscal")
                coverage={}
                for row in data:
                    year=int(row.get("ano",row.get("exercicio")))
                    bim=int(row["bimestre"])
                    coverage.setdefault(str(year),set()).add(bim)
                print("OK /api/fiscal —",len(data),"períodos",
                      {year:sorted(periods) for year,periods in sorted(coverage.items())})
            else:print("OK /api/source —",data)
        except Exception as exc:
            raise RuntimeError("Falha após reinício na rota "+route+": "+str(exc)) from exc
    print("CORREÇÃO 8507 CONCLUÍDA: reabra a porta 8507 no Codespaces e pressione Ctrl+Shift+R.")
    print("Portas 8506/8505, branch, produtos, layouts e CSV histórico não foram modificados.")
    print("Se o navegador continuar mostrando 502 mas os testes acima passarem, reabra a porta no painel PORTAS.")

if __name__=="__main__":
    try:main()
    except Exception as error:
        print("ERRO DE ATIVAÇÃO DA 8507:",error,file=sys.stderr)
        sys.exit(1)
