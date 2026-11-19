#!/usr/bin/env python3
"""Instala atualização seletiva de interface/API fiscal em Codespaces existente.
Não altera storage, branch ou arquivos fora da allowlist; recusa divergências locais.
"""
from pathlib import Path
import os,subprocess,datetime,sys
ROOT=Path("/workspaces/bi-factory-seppe")
BASE="origin/feat/onboarding-projetos-conhecimento-20261117"
HEAD="origin/feat/stn-produtos-periodos-2022-2025"
PATHS=[
 "scripts/serve_bi_factory_api.py",
 "prototypes/editor-visual/server.py",
 "prototypes/editor-visual/index.html",
 "web/bi_factory/src/main.jsx",
 "web/bi_factory/src/style.css",
 "web/bi_factory/src/FiscalSourcePicker.jsx",
]
def git(ref,path):
    p=subprocess.run(["git","show",f"{ref}:{path}"],cwd=ROOT,capture_output=True)
    return p.stdout if p.returncode==0 else None

def main():
    if not (ROOT/".git").is_dir():raise RuntimeError("Codespaces do BI Factory não encontrado")
    updates={}
    for path in PATHS:
        local=ROOT/path
        if local.is_symlink():raise RuntimeError("Link simbólico: "+path)
        existing=local.read_bytes() if local.exists() else None
        before,after=git(BASE,path),git(HEAD,path)
        if after is None:raise RuntimeError("Arquivo de atualização ausente: "+path)
        if existing==after:continue
        if existing!=before:
            raise RuntimeError("Alteração local não reconhecida; nenhum arquivo alterado: "+path)
        updates[path]=(existing,after)
    if not updates:
        print("Código fiscal já instalado. Confirme reinício da API 8505 e atualize a interface.")
        return
    stamp=datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup=ROOT/".git"/"backups"/("fiscal-produtos-"+stamp)
    for path,(before,_) in updates.items():
        if before is not None:
            dest=backup/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(before)
    changed=[]
    try:
        for path,(_,after) in updates.items():
            target=ROOT/path;target.parent.mkdir(parents=True,exist_ok=True)
            temp=target.with_name(target.name+".fiscal-new")
            temp.write_bytes(after)
            if target.exists():os.chmod(temp,target.stat().st_mode&0o777)
            os.replace(temp,target);changed.append(path)
        subprocess.run([sys.executable,"-m","py_compile","scripts/serve_bi_factory_api.py","prototypes/editor-visual/server.py"],cwd=ROOT,check=True)
        subprocess.run(["npm","run","build"],cwd=ROOT/"web/bi_factory",check=True)
    except Exception:
        for path in changed:
            before=updates[path][0];local=ROOT/path
            if before is None:local.unlink(missing_ok=True)
            else:local.write_bytes(before)
        raise
    print("CÓDIGO ATUALIZADO E BUILD APROVADO")
    print("Arquivos:",", ".join(changed))
    print("Backup:",backup)
    print("Reinicie somente a API Python 8505 para disponibilizar /api/fiscal-catalog.")
    print("Nenhum dado financeiro foi criado ou modificado.")
if __name__=="__main__":
    try:main()
    except Exception as exc:print("INSTALAÇÃO BLOQUEADA / REVERTIDA:",exc,file=sys.stderr);sys.exit(1)
