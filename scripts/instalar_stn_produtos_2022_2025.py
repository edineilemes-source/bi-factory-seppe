#!/usr/bin/env python3
"""Instala atualização seletiva de interface/API fiscal em Codespaces existente.
Não altera storage, branch ou arquivos fora da allowlist; recusa divergências locais.
"""
from pathlib import Path
import os,subprocess,datetime,sys,signal,time,urllib.request
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
 "scripts/importar_rreo_stn_2022_2025.py",
 "scripts/consolidar_rreo_2022_2025.py",
]
def git(ref,path):
    p=subprocess.run(["git","show",f"{ref}:{path}"],cwd=ROOT,capture_output=True)
    return p.stdout if p.returncode==0 else None

def api_ready():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8505/api/fiscal-catalog",timeout=3) as response:
            return response.status==200
    except Exception:
        return False

def restart_known_api():
    matching=[]
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():continue
        try:
            arguments=(proc/"cmdline").read_bytes().split(b"\\0")
            if not any(b"serve_bi_factory_api.py" in arg for arg in arguments):continue
            if b"8505" not in arguments:continue
            if (proc/"cwd").resolve()==ROOT:matching.append(int(proc.name))
        except (PermissionError,OSError):continue
    if len(matching)>1:
        print("Mais de uma API identificada; reinício manual necessário.")
        return
    if matching:
        os.kill(matching[0],signal.SIGTERM)
        for _ in range(50):
            try:os.kill(matching[0],0)
            except ProcessLookupError:break
            time.sleep(.2)
    elif api_ready():
        print("Porta 8505 responde mas o processo não foi identificado; preservada.")
        return
    logs=Path("/tmp/bi-factory-seppe-logs");logs.mkdir(exist_ok=True)
    with (logs/"api-8505.log").open("ab") as output:
        subprocess.Popen([sys.executable,"-u",str(ROOT/"scripts/serve_bi_factory_api.py"),"--port","8505"],
                         cwd=ROOT,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,
                         start_new_session=True)
    for _ in range(40):
        if api_ready():
            print("API fiscal 8505 reiniciada e /api/fiscal-catalog validada.")
            return
        time.sleep(.5)
    print("ATENÇÃO: API não respondeu ao novo endpoint. Verifique /tmp/bi-factory-seppe-logs/api-8505.log")

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
    print("Iniciando importação oficial STN para períodos ainda não presentes.")
    extraction=subprocess.run([sys.executable,"scripts/importar_rreo_stn_2022_2025.py"],cwd=ROOT)
    if extraction.returncode:
        print("ATENÇÃO: STN não forneceu todos os períodos. Veja artifacts/stn_rreo_raw_2022_2025/auditoria.json")
    consolidation=subprocess.run([sys.executable,"scripts/consolidar_rreo_2022_2025.py"],cwd=ROOT)
    if consolidation.returncode:
        print("ATENÇÃO: consolidação não concluída; CSVs originais preservados.")
    restart_known_api()
    print("Fontes originais anteriores e produtos preservados; apenas dados validados são apresentados.")
if __name__=="__main__":
    try:main()
    except Exception as exc:print("INSTALAÇÃO BLOQUEADA / REVERTIDA:",exc,file=sys.stderr);sys.exit(1)
