#!/usr/bin/env python3
"""Instala e inicia laboratório X/Y/Z/Cabeçalho na porta isolada 8507.

Não modifica nenhum arquivo de 8506/8505, devcontainer, produtos ou layouts.
Só grava nova árvore experiments/echarts-axes-8507 e servidor/testes 8507.
Recusa sobrescrever qualquer arquivo desconhecido. Faz backup e rollback.
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
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT=Path("/workspaces/bi-factory-seppe")
REV="origin/feat/lab-echarts-eixos-8507-20261119"
FILES=(
 "experiments/echarts-axes-8507/index.html",
 "experiments/echarts-axes-8507/style.css",
 "experiments/echarts-axes-8507/engine.js",
 "experiments/echarts-axes-8507/app.js",
 "scripts/serve_echarts_axes_8507.py",
 "scripts/test_echarts_axes_8507.js",
 "scripts/test_lab_ui_contract_8507.js",
)
PORT=8507
BASE="http://127.0.0.1:8507"

def remote(path):
    p=subprocess.run(["git","show",REV+":"+path],cwd=ROOT,capture_output=True)
    if p.returncode:
        raise RuntimeError("Arquivo não encontrado no GitHub: "+path+" "+p.stderr.decode(errors="replace")[-400:])
    return p.stdout

def check_syntax(files):
    with tempfile.TemporaryDirectory(prefix="bi-lab-check-") as tmp:
        tempdir=Path(tmp)
        for name,bytes_ in files.items():
            if name.endswith(".js"):
                temp=tempdir/Path(name).name
                temp.write_bytes(bytes_)
                result=subprocess.run(["node","--check",str(temp)],capture_output=True,text=True)
                if result.returncode:
                    raise RuntimeError("JavaScript inválido "+name+" "+result.stderr[-900:])
            elif name.endswith(".py"):
                temp=tempdir/Path(name).name
                temp.write_bytes(bytes_)
                result=subprocess.run([sys.executable,"-m","py_compile",str(temp)],capture_output=True,text=True)
                if result.returncode:
                    raise RuntimeError("Python inválido "+name+" "+result.stderr[-900:])

def health():
    try:
        with urllib.request.urlopen(BASE+"/api/health",timeout=2) as response:
            result=json.load(response)
        return result if isinstance(result,dict) else None
    except (OSError,ValueError):
        return None

def port_free():
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1",PORT))!=0

def start():
    already=health()
    if already:
        if already.get("lab")=="echarts-axes" and already.get("port")==PORT:
            print("Servidor experimental 8507 já está no ar; reutilizando.")
            return
        raise RuntimeError("Porta 8507 já ocupada por outra aplicação; não interferir.")
    if not port_free():
        raise RuntimeError("Porta 8507 ocupada, serviço não identificado; nenhuma tentativa de encerrá-lo.")
    logs=Path("/tmp/bi-factory-seppe-logs")
    logs.mkdir(parents=True,exist_ok=True)
    logfile=logs/"lab-echarts-8507.log"
    with logfile.open("ab") as output:
        subprocess.Popen([
            sys.executable,"-u",str(ROOT/"scripts/serve_echarts_axes_8507.py"),
            "--host","127.0.0.1","--port",str(PORT)
        ],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=output,
           stderr=subprocess.STDOUT,start_new_session=True)
    for _ in range(50):
        outcome=health()
        if outcome and outcome.get("lab")=="echarts-axes":
            print("SERVIDOR 8507 INICIADO E VALIDADO.")
            return
        time.sleep(.2)
    raise RuntimeError("Servidor 8507 não respondeu; veja "+str(logfile))

def endpoint(url,timeout=8):
    with urllib.request.urlopen(url,timeout=timeout) as resp:
        return json.load(resp)

def preserve_8506():
    """Arquivo versionado do estado local atual, inclusive mudanças não commitadas."""
    stamp=datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    folder=ROOT/".git"/"backups"/("apresentacao-estavel-8506-"+stamp)
    folder.mkdir(parents=True,exist_ok=True)
    entries=[
      "web/bi_factory/src",
      "web/bi_factory/vite.config.js",
      "web/bi_factory/package.json",
      "web/bi_factory/package-lock.json",
      "prototypes/editor-visual",
      "scripts/serve_bi_factory_api.py",
      "storage/information_products/registry.json",
      "storage/information_products/folders.json",
      "storage/information_products/layouts",
      "storage/dashboard_projects/products",
      "storage/reports/official_fiscal/rreo-2022-2026-dashboard.csv",
    ]
    present=[];missing=[]
    archive=folder/"codigo-e-produtos-8506.tar.gz"
    with tarfile.open(archive,mode="w:gz",dereference=False) as out:
      for name in entries:
        item=ROOT/name
        if not item.exists() or item.is_symlink():
          missing.append(name);continue
        # Ignorar links simbólicos contidos na árvore, sem seguir caminhos externos.
        def safe(member):
          return None if member.issym() or member.islnk() else member
        out.add(item,arcname=name,recursive=True,filter=safe)
        present.append(name)
    branch=subprocess.run(["git","branch","--show-current"],cwd=ROOT,
                          capture_output=True,text=True).stdout.strip()
    sha=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,
                       capture_output=True,text=True).stdout.strip()
    digest=hashlib.sha256()
    with archive.open("rb") as reader:
        while True:
            chunk=reader.read(1024*1024)
            if not chunk:break
            digest.update(chunk)
    manifest={
      "created_local":datetime.datetime.now().isoformat(timespec="seconds"),
      "snapshot":"8506 antes de instalar laboratório 8507",
      "branch":branch,"head":sha,
      "included":present,"not_found":missing,
      "archive":str(archive),
      "bytes":archive.stat().st_size,
      "sha256":digest.hexdigest(),
    }
    (folder/"manifest.json").write_text(
        json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print("SNAPSHOT DA 8506 (não altera a aplicação):",archive)
    return folder

def main():
    if not (ROOT/".git").is_dir():raise RuntimeError("Repositório Codespaces BI Factory não encontrado")
    updates={}
    known={}
    for name in FILES:
        dest=ROOT/name
        if dest.is_symlink():raise RuntimeError("Link simbólico não permitido: "+name)
        if dest.exists() and not dest.is_file():
            raise RuntimeError("Caminho não é arquivo: "+name)
        desired=remote(name)
        existing=dest.read_bytes() if dest.exists() else None
        known[name]=desired
        if existing==desired:
            print("JÁ INSTALADO:",name)
            continue
        if existing is not None:
            sha=hashlib.sha256(existing).hexdigest()[:16]
            raise RuntimeError("Arquivo experimental alterado localmente: "+name+
                               " SHA="+sha+"; preservado sem sobrescrita")
        updates[name]=(existing,desired)
        print("NOVO ARQUIVO 8507:",name)
    check_syntax(known)
    preserve_8506()
    stamp=datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup=ROOT/".git"/"backups"/("lab-8507-"+stamp)
    saved=[]
    try:
        for name,(before,desired) in updates.items():
            target=ROOT/name
            target.parent.mkdir(parents=True,exist_ok=True)
            if before is not None:
                old=backup/name
                old.parent.mkdir(parents=True,exist_ok=True)
                old.write_bytes(before)
            pending=target.with_name(target.name+".8507-pending")
            if pending.exists():raise RuntimeError("Arquivo temporário preexistente: "+str(pending))
            try:
                pending.write_bytes(desired)
                os.replace(pending,target)
                saved.append(name)
            finally:
                pending.unlink(missing_ok=True)
        subprocess.run(["node","scripts/test_echarts_axes_8507.js"],
                       cwd=ROOT,check=True)
        subprocess.run(["node","scripts/test_lab_ui_contract_8507.js"],
                       cwd=ROOT,check=True)
    except Exception:
        for name in saved:
            old=updates[name][0]
            if old is None:(ROOT/name).unlink(missing_ok=True)
            else:(ROOT/name).write_bytes(old)
        raise
    start()
    try:
        data=endpoint(BASE+"/api/fiscal",timeout=20)
        valid={(str(r.get("ano",r.get("exercicio"))),str(r["bimestre"]))
               for r in data if isinstance(r,dict) and r.get("bimestre") is not None}
        print("Dados oficiais consultáveis via 8507:",len(valid),"bimestres")
        available={str(y):sorted(int(b) for year,b in valid if year==str(y))
                   for y in range(2022,2027)}
        print("Cobertura:",json.dumps(available,ensure_ascii=False))
    except Exception as exc:
        print("ATENÇÃO: a 8507 iniciou, mas a fonte fiscal 8505 está indisponível:",exc)
    try:
        state=endpoint(BASE+"/api/state")
        print("Rascunho isolado na 8507:",len(state.get("objects",[])),"objetos")
    except Exception as exc:
        print("ATENÇÃO: não foi possível testar persistência do laboratório:",exc)
    print()
    print("PORTA DE TESTE: 8507 — processo iniciado em 127.0.0.1:8507")
    print("No painel PORTAS do Codespaces, encaminhe 8507 com visibilidade PRIVATE.")
    print("A 8506 continua intacta: não houve checkout, merge, alteração de UI ou banco da versão estável.")
    print("Laboratório: Editor Visual (sem combos de ano/bimestre na esquerda) + ECharts X/Y/Z/Cabeçalho.")
    print("Rascunhos exclusivos: storage/labs/echarts-axes-8507/state.json")
    name=os.environ.get("CODESPACE_NAME")
    domain=os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN")
    if name and domain:
        print("URL estimada a partir do Codespaces:",f"https://{name}-8507.{domain}",
              "(requer porta encaminhada e autenticação)")
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except Exception as exc:
        print("LABORATÓRIO 8507 NÃO INSTALADO:",exc,file=sys.stderr)
        sys.exit(1)
