#!/usr/bin/env python3
"""Instala seletores de dimensões/medidas no ECharts e Editor Visual existente.
Apenas dois HTMLs versionados. Recusa arquivos locais desconhecidos. Não altera storage.
"""
from pathlib import Path
import subprocess,sys,re,tempfile,os,datetime,urllib.request
ROOT=Path("/workspaces/bi-factory-seppe")
BASE="origin/feat/stn-produtos-2026"
TARGET="origin/fix/echarts-dimensoes-medidas-20261119"
FILES=["prototypes/editor-visual/echarts-studio.html","prototypes/editor-visual/index.html"]

def git(ref,path):
    p=subprocess.run(["git","show",f"{ref}:{path}"],cwd=ROOT,capture_output=True)
    return p.stdout if p.returncode==0 else None

def check_scripts(path):
    text=path.read_text(encoding="utf-8")
    chunks=re.findall(r"<script(?:\\s[^>]*)?>(.*?)</script>",text,flags=re.DOTALL|re.IGNORECASE)
    checked=0
    for chunk in chunks:
        if not chunk.strip():continue
        fd,tmp=tempfile.mkstemp(prefix="bi-verify-",suffix=".js")
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as dest:dest.write(chunk)
            subprocess.run(["node","--check",tmp],check=True)
            checked+=1
        finally:Path(tmp).unlink(missing_ok=True)
    if not checked:raise RuntimeError("Nenhum script interno encontrado em "+str(path))
    return checked

def main():
    if not (ROOT/".git").is_dir():raise RuntimeError("Projeto Codespaces não encontrado")
    changes={}
    for name in FILES:
        path=ROOT/name
        if not path.is_file() or path.is_symlink():raise RuntimeError("Arquivo inexistente ou link: "+name)
        before,after=git(BASE,name),git(TARGET,name)
        current=path.read_bytes()
        if before is None or after is None:raise RuntimeError("Referência Git não encontrada: "+name)
        if current==after:continue
        if current!=before:raise RuntimeError("Arquivo com alterações locais não reconhecidas; preservado: "+name)
        changes[name]=(current,after)
    if not changes:
        print("Dois editores já correspondem à versão nova.")
    else:
        backup=ROOT/".git"/"backups"/("echarts-dimensoes-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        for name,(previous,_) in changes.items():
            dest=backup/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(previous)
        changed=[]
        try:
            for name,(_,updated) in changes.items():
                path=ROOT/name;temp=path.with_name(path.name+".echarts-pending")
                if temp.exists():raise RuntimeError("Arquivo temporário preexistente: "+name)
                try:
                    temp.write_bytes(updated)
                    os.chmod(temp,path.stat().st_mode & 0o777)
                    os.replace(temp,path)
                finally:temp.unlink(missing_ok=True)
                changed.append(name)
            for name in FILES:print("JavaScript validado:",name,"blocos:",check_scripts(ROOT/name))
        except Exception:
            for name in changed:(ROOT/name).write_bytes(changes[name][0])
            raise
        print("Backup:",backup)
    for name in FILES:check_scripts(ROOT/name)
    print("ARQUIVOS ATUALIZADOS. Sem mudança em produtos, layouts ou dados.")
    print("Abra novamente a aba Produtos / Editor Visual e clique em Editar no Charts.")
    print("Atualize o navegador com Ctrl+Shift+R para evitar cache antigo.")
if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("INSTALAÇÃO BLOQUEADA OU REVERTIDA:",exc,file=sys.stderr)
        sys.exit(1)
