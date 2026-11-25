#!/usr/bin/env python3
"""Instala busca e download automático de PDFs na BI Factory SEPPE.

Mantém a branch local, produtos, layouts, PDF e índices; compara apenas
quatro arquivos de código, preserva mudanças locais via merge de 3 vias,
faz backup/rollback e testa antes de reiniciar a API 8505 conhecida.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import json

ROOT=Path("/workspaces/bi-factory-seppe")
BASE="origin/fix/biblioteca-pypdf-isolado-codespaces-20261125"
TARGET="origin/feat/conhecimento-download-automatico-capag-20261125"
FILES=(
 "scripts/bi_knowledge_official.py",
 "scripts/serve_bi_factory_api.py",
 "web/bi_factory/src/OfficialKnowledgeSearch.jsx",
 "scripts/test_knowledge_official.py",
)
NEW_FILE="scripts/instalar_download_automatico_conhecimento.py"
WEB=ROOT/"web/bi_factory"

def git_content(ref,name):
    response=subprocess.run(["git","show",ref+":"+name],cwd=ROOT,capture_output=True)
    if response.returncode:
        raise RuntimeError("Arquivo de referência não encontrado: "+ref+":"+name)
    return response.stdout

def merge(name,old,base,target):
    if old==target:return old
    if old==base:return target
    with tempfile.TemporaryDirectory(prefix="bi-autodownload-") as temp:
        paths=[Path(temp)/part for part in ("local","base","new")]
        for p,blob in zip(paths,(old,base,target)):p.write_bytes(blob)
        result=subprocess.run(["git","merge-file","-p","--diff3",*(str(x) for x in paths)],
                              capture_output=True)
    if result.returncode:
        raise RuntimeError("Conflito em "+name+
           ". Preservado o arquivo local; nenhuma alteração foi aplicada.")
    return result.stdout

def run(cmd,cwd=ROOT):
    env=os.environ.copy()
    deps=str(ROOT/".git"/"knowledge-deps")
    env["PYTHONPATH"]=deps+(os.pathsep+env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    print("VALIDANDO:",' '.join(cmd),flush=True)
    subprocess.run(cmd,cwd=cwd,check=True,env=env)

def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1",port),timeout=.8):return True
    except OSError:return False

def api_processes():
    found=[]
    for p in Path("/proc").iterdir():
        if not p.name.isdecimal():continue
        try:
            argv=(p/"cmdline").read_bytes().replace(b"\0",b" ").decode("utf-8","replace")
            if ("scripts/serve_bi_factory_api.py" in argv
                and (p/"cwd").resolve()==ROOT):
                found.append(int(p.name))
        except (OSError,ValueError,PermissionError):
            continue
    return found

def main():
    if not (ROOT/".git").is_dir():
        raise RuntimeError("Execute no Codespaces /workspaces/bi-factory-seppe")
    pending={}
    for name in (*FILES,NEW_FILE):
        dest=ROOT/name
        if dest.is_symlink() or (dest.exists() and not dest.is_file()):
            raise RuntimeError("Arquivo inseguro para atualização: "+name)
        old=dest.read_bytes() if dest.exists() else None
        wanted=git_content(TARGET,name)
        if name==NEW_FILE:
            if old is not None and old!=wanted:
                raise RuntimeError("Instalador local diferente: não será sobrescrito")
            effective=wanted
        else:
            if old is None:raise RuntimeError("Código local ausente: "+name)
            effective=merge(name,old,git_content(BASE,name),wanted)
        if old!=effective:
            pending[name]=(old,effective)
            print("PREPARADO:",name,flush=True)
        else:print("JÁ ATUALIZADO:",name,flush=True)
    backup=ROOT/".git"/"backups"/("conhecimento-download-"+datetime.now().strftime("%Y%m%d-%H%M%S"))
    done=[]
    try:
        for name,(old,new) in pending.items():
            dest=ROOT/name
            if old is not None:
                copy=backup/name
                copy.parent.mkdir(parents=True,exist_ok=True)
                copy.write_bytes(old)
            dest.parent.mkdir(parents=True,exist_ok=True)
            fd,tmp=tempfile.mkstemp(prefix=".knowledge-auto-",dir=dest.parent)
            try:
                with os.fdopen(fd,"wb") as f:
                    f.write(new)
                    f.flush()
                    os.fsync(f.fileno())
                if dest.exists():os.chmod(tmp,dest.stat().st_mode&0o777)
                os.replace(tmp,dest)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
            done.append(name)
            print("ATUALIZADO:",name,flush=True)
        run([sys.executable,"-m","py_compile",
             "scripts/bi_knowledge_official.py","scripts/serve_bi_factory_api.py"])
        run([sys.executable,"scripts/test_knowledge_official.py"])
        run([sys.executable,"scripts/test_knowledge_library.py"])
        if not (WEB/"node_modules/.bin/vite").exists():run(["npm","ci"],WEB)
        run(["npm","run","build"],WEB)
    except Exception:
        print("Falha de teste; restaurando apenas o código desta instalação.",flush=True)
        for name in reversed(done):
            old=pending[name][0]
            dest=ROOT/name
            if old is None:dest.unlink(missing_ok=True)
            else:dest.write_bytes(old)
        raise
    if backup.exists():print("BACKUP:",backup)
    print("Código e testes concluídos. Ativando download automático na API.",flush=True)
    if port_open(8505):
        processes=api_processes()
        if len(processes)!=1:
            print("API 8505 é de processo desconhecido: não será interrompido.")
            print("Instalado, mas pendente reinício seguro da API 8505.")
            return
        os.kill(processes[0],signal.SIGTERM)
        for _ in range(40):
            if not port_open(8505):break
            time.sleep(.2)
        if port_open(8505):
            raise RuntimeError("API não liberou porta 8505")
    run(["bash","scripts/start_bi_factory_codespaces.sh"])
    with urllib.request.urlopen("http://127.0.0.1:8505/api/projects",timeout=6) as r:
        value=json.loads(r.read(1_000_000))
    if not isinstance(value,dict) or "projects" not in value:
        raise RuntimeError("API 8505 não respondeu corretamente")
    print("OK: pesquisar CAPAG e baixar PDFs oficiais automaticamente na Biblioteca.")
    print("Abra PORTAS > 8506, atualize Ctrl+Shift+R e pesquise CAPAG.")
    print("A 8507 experimental e o acervo de PDFs não foram alterados.")

if __name__=="__main__":
    try:main()
    except Exception as err:
        print("ERRO AO INSTALAR DOWNLOAD AUTOMÁTICO:",err,file=sys.stderr,flush=True)
        sys.exit(1)
