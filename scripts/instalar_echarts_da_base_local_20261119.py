#!/usr/bin/env python3
"""Instala seletores no Codespaces a partir dos HTMLs efetivamente identificados.

Diagnóstico 2026-11-19: os dois HTMLs locais estão na versão anterior
à implantação histórica STN. Não presume que feat/stn-produtos-2026 esteja
instalada. Só grava arquivos que correspondam à base confirmada ou ao destino.
"""
from pathlib import Path
import datetime, hashlib, os, re, subprocess, sys, tempfile

ROOT=Path("/workspaces/bi-factory-seppe")
BASE="origin/feat/onboarding-projetos-conhecimento-20261117"
TARGET="origin/fix/echarts-dimensoes-medidas-20261119"
PATHS=("prototypes/editor-visual/index.html",
       "prototypes/editor-visual/echarts-studio.html")

def show(ref,path):
    p=subprocess.run(["git","show",f"{ref}:{path}"],cwd=ROOT,capture_output=True)
    if p.returncode:raise RuntimeError("Referência indisponível "+ref+":"+path+
                                      " "+p.stderr.decode(errors="replace")[-300:])
    return p.stdout

def jscheck(path,contents):
    html=contents.decode("utf-8")
    scripts=[m.group(1) for m in re.finditer(r"<script[^>]*>(.*?)</script>",html,re.I|re.S)
             if m.group(1).strip()]
    if not scripts:raise RuntimeError("Nenhum JS encontrado: "+path)
    for code in scripts:
        with tempfile.NamedTemporaryFile(mode="w",suffix=".js",encoding="utf-8",delete=False) as f:
            f.write(code);name=f.name
        try:
            result=subprocess.run(["node","--check",name],capture_output=True,text=True)
            if result.returncode:raise RuntimeError("JS inválido em "+path+" "+result.stderr[-1200:])
        finally:Path(name).unlink(missing_ok=True)

def fingerprint(contents):
    return hashlib.sha256(contents).hexdigest()

def main():
    if not (ROOT/".git").is_dir():raise RuntimeError("Repositório Codespaces não localizado")
    updates={}
    for path in PATHS:
        local=ROOT/path
        if not local.is_file() or local.is_symlink():raise RuntimeError("HTML não localizado ou link: "+path)
        current=local.read_bytes()
        baseline=show(BASE,path)
        desired=show(TARGET,path)
        jscheck(path,desired)
        if current==desired:
            print("JÁ ATUALIZADO:",path)
            continue
        if current!=baseline:
            print("HASH LOCAL:",fingerprint(current))
            print("HASH BASE:",fingerprint(baseline))
            print("HASH NOVO:",fingerprint(desired))
            raise RuntimeError("A versão local de "+path+" ainda difere da base original; "+
                               "nenhum arquivo será substituído. Informe os hashes acima.")
        updates[path]=(current,desired)
        print("BASE ORIGINAL CONFIRMADA:",path,fingerprint(current)[:16])
    if not updates:
        print("Ambos os editores já estão atualizados.")
        return
    stamp=datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup=ROOT/".git"/"backups"/("echarts-base-real-"+stamp)
    for path,(old,_) in updates.items():
        dest=backup/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(old)
    applied=[]
    try:
        for path,(_,new) in updates.items():
            dest=ROOT/path
            pending=dest.with_name(dest.name+".echarts-ready")
            if pending.exists():raise RuntimeError("Arquivo temporário preexistente: "+str(pending))
            try:
                pending.write_bytes(new)
                os.chmod(pending,dest.stat().st_mode&0o777)
                os.replace(pending,dest)
                applied.append(path)
            finally:pending.unlink(missing_ok=True)
        for path in PATHS:jscheck(path,(ROOT/path).read_bytes())
    except Exception:
        for path in applied:(ROOT/path).write_bytes(updates[path][0])
        raise
    print("SUCESSO: ECharts e Editor Visual atualizados. Backup:",backup)
    print("Dados, layouts salvos e branch atual não alterados.")
    print("Feche os dois editores e reabra com Ctrl+Shift+R.")
    print("ATENÇÃO: os períodos exibidos com dados dependem da fonte /api/fiscal "+
          "e do carregamento STN no Codespaces; esta atualização altera os seletores, não importa valores.")

if __name__=="__main__":
    try:main()
    except Exception as e:print("INSTALAÇÃO NÃO APLICADA:",e,file=sys.stderr);sys.exit(1)
