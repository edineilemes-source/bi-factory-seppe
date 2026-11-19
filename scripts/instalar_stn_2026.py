#!/usr/bin/env python3
"""Instala suporte ao RREO 2026 no Codespaces, preservando os produtos e as fontes.
Compatível com instalação anterior 2022-25 ou arquivos base ainda não instalados.
"""
from pathlib import Path
import subprocess,os,sys,time,signal,urllib.request,datetime
ROOT=Path("/workspaces/bi-factory-seppe")
BASE="origin/feat/onboarding-projetos-conhecimento-20261117"
OLD="origin/feat/stn-produtos-periodos-2022-2025"
NEW="origin/feat/stn-produtos-2026"
FILES=[
 "scripts/serve_bi_factory_api.py",
 "prototypes/editor-visual/server.py",
 "prototypes/editor-visual/index.html",
 "web/bi_factory/src/main.jsx",
 "web/bi_factory/src/style.css",
 "web/bi_factory/src/FiscalSourcePicker.jsx",
 "scripts/importar_rreo_stn_2022_2025.py",
 "scripts/consolidar_rreo_2022_2025.py",
 "scripts/importar_rreo_2026.py",
 "scripts/consolidar_rreo_2022_2026.py",
]

def git(ref,path):
    p=subprocess.run(["git","show",f"{ref}:{path}"],cwd=ROOT,capture_output=True)
    return p.stdout if p.returncode==0 else None

def api_ok():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8505/api/fiscal-catalog",timeout=2) as r:
            return r.status==200
    except Exception:return False

def restart():
    found=[]
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():continue
        try:
            argv=(proc/"cmdline").read_bytes().split(bytes([0]))
            if not any(b"serve_bi_factory_api.py" in a for a in argv):continue
            if b"8505" not in argv:continue
            if (proc/"cwd").resolve()!=ROOT:continue
            found.append(int(proc.name))
        except (OSError,PermissionError):continue
    if len(found)>1:
        print("Reinício manual necessário: mais de uma API encontrada.")
        return
    if found:
        os.kill(found[0],signal.SIGTERM)
        for _ in range(40):
            try:
                os.kill(found[0],0)
                stat=(Path("/proc")/str(found[0])/"status").read_text(errors="replace")
                if "Z (zombie)" in stat:break
            except (ProcessLookupError,FileNotFoundError):break
            time.sleep(.2)
        else:
            print("API anterior não encerrou. Não iniciar processo concorrente.")
            return
    elif api_ok():
        print("API responde mas processo não identificado; preservada.")
        return
    log=Path("/tmp/bi-factory-seppe-logs");log.mkdir(exist_ok=True)
    with (log/"api-8505.log").open("ab") as out:
        subprocess.Popen([sys.executable,"-u",str(ROOT/"scripts/serve_bi_factory_api.py"),"--port","8505"],cwd=ROOT,
                         stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
    for _ in range(40):
        if api_ok():
            print("API 8505 validada em /api/fiscal-catalog.")
            return
        time.sleep(.5)
    print("API não validada; consulte /tmp/bi-factory-seppe-logs/api-8505.log")

def main():
    if not (ROOT/".git").is_dir():raise RuntimeError("Codespaces BI Factory não encontrado")
    changes={}
    for name in FILES:
        path=ROOT/name
        if path.is_symlink():raise RuntimeError("Link simbólico recusado: "+name)
        actual=path.read_bytes() if path.is_file() else None
        previous=git(OLD,name)
        baseline=git(BASE,name)
        target=git(NEW,name)
        if target is None:raise RuntimeError("Arquivo remoto inexistente: "+name)
        if actual==target:continue
        if actual not in (previous,baseline):
            raise RuntimeError("Alteração local não reconhecida em "+name+"; nenhum arquivo foi alterado")
        changes[name]=(actual,target)
    backup=ROOT/".git"/"backups"/("stn-2026-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    for name,(previous,_) in changes.items():
        if previous is not None:
            path=backup/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(previous)
    changed=[]
    try:
        for name,(_,new) in changes.items():
            path=ROOT/name;path.parent.mkdir(parents=True,exist_ok=True)
            temp=path.with_name(path.name+".stn-2026-pending")
            if temp.exists():raise RuntimeError("Arquivo temporário já existe: "+name)
            try:
                temp.write_bytes(new)
                if path.is_file():os.chmod(temp,path.stat().st_mode&0o777)
                os.replace(temp,path)
            finally:temp.unlink(missing_ok=True)
            changed.append(name)
        subprocess.run([sys.executable,"-m","py_compile",
            "scripts/serve_bi_factory_api.py","prototypes/editor-visual/server.py",
            "scripts/importar_rreo_stn_2022_2025.py","scripts/importar_rreo_2026.py",
            "scripts/consolidar_rreo_2022_2026.py"],cwd=ROOT,check=True)
        subprocess.run(["npm","run","build"],cwd=ROOT/"web/bi_factory",check=True)
    except Exception:
        for name in changed:
            previous=changes[name][0];path=ROOT/name
            if previous is None:path.unlink(missing_ok=True)
            else:path.write_bytes(previous)
        raise
    print("Interface e API 2026 instaladas; build aprovado.")
    if changes:print("Backup do código:",backup)
    print("Consultando STN para exercícios anteriores ainda não importados...")
    subprocess.run([sys.executable,"scripts/importar_rreo_stn_2022_2025.py"],cwd=ROOT,check=False)
    print("Consultando bimestres 1 a 5 de 2026...")
    subprocess.run([sys.executable,"scripts/importar_rreo_2026.py"],cwd=ROOT,check=False)
    print("Consolidando 2022–2026...")
    subprocess.run([sys.executable,"scripts/consolidar_rreo_2022_2026.py"],cwd=ROOT,check=False)
    restart()
    print("Verifique HTTP /api/fiscal-catalog e os períodos indicados como disponíveis.")
    print("2026: 6º bimestre ainda não encerrado; 5º pode estar pendente de declaração.")
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("INSTALAÇÃO BLOQUEADA OU REVERTIDA:",e,file=sys.stderr)
        sys.exit(1)
