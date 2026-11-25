#!/usr/bin/env python3
"""Instalador seguro da pesquisa multifontes (sem trocar branch local)."""
from datetime import datetime
from pathlib import Path
import json,os,signal,socket,subprocess,sys,tempfile,time,urllib.request
ROOT=Path("/workspaces/bi-factory-seppe")
BASE="origin/feat/conhecimento-download-automatico-capag-20261125"
TARGET="origin/feat/conhecimento-busca-multifontes-simples-20261125"
UPDATES=["scripts/bi_knowledge_official.py","web/bi_factory/src/OfficialKnowledgeSearch.jsx"]
ADDS=["scripts/bi_knowledge_federated.py","scripts/test_knowledge_federated.py",
      "scripts/instalar_pesquisa_multifontes.py"]
PARENT="web/bi_factory/src/KnowledgeStart.jsx"

def command(*args,cwd=ROOT):
    return subprocess.run(args,cwd=cwd,check=True)

def remote(ref,path):
    result=subprocess.run(["git","show",ref+":"+path],cwd=ROOT,capture_output=True)
    if result.returncode:raise RuntimeError("Referência ausente: "+ref+":"+path)
    return result.stdout

def combine(path,local,old,new):
    if local in (old,new):return new
    with tempfile.TemporaryDirectory() as directory:
        paths=[Path(directory)/x for x in ("local","base","alvo")]
        for p,data in zip(paths,(local,old,new)):p.write_bytes(data)
        result=subprocess.run(["git","merge-file","-p","--diff3",
          *(str(x) for x in paths)],capture_output=True)
    if result.returncode:raise RuntimeError("Conflito: "+path+". Nada foi instalado.")
    return result.stdout

def adapt_parent(raw):
    s=raw.decode("utf-8")
    old='  <div className="card catalogForm" style={{padding:20}}>\n   <h2>1. O que você deseja conhecer?</h2>'
    upload='  <div className="card catalogForm" style={{padding:20}}>\n   <h2>3. Incluir documentos próprios</h2>'
    history='  <div className="card" style={{padding:20}}>\n   <h2>4. Acervo de conhecimento do projeto</h2>'
    if "BI_KNOWLEDGE_OFFICIAL_SLOT" in s and "Pesquisa antiga (opcional)" in s:return raw
    if not all(x in s for x in (old,upload,history)):
        raise RuntimeError("Tela local personalizada desconhecida; preservada integralmente.")
    if "BI_KNOWLEDGE_OFFICIAL_SLOT" not in s:
        line='import React,{useEffect,useState} from "react";'
        if "import OfficialKnowledgeSearch" not in s:
            if line not in s:raise RuntimeError("Import JSX não reconhecido")
            s=s.replace(line,line+'\nimport OfficialKnowledgeSearch from "./OfficialKnowledgeSearch.jsx";',1)
        s=s.replace(old,'  {/* BI_KNOWLEDGE_OFFICIAL_SLOT */}\n'
            '  <OfficialKnowledgeSearch project={project}/>\n'+old,1)
    if "Pesquisa antiga (opcional)" not in s:
        s=s.replace(old,'  <details><summary>Pesquisa antiga (opcional)</summary>\n'+old,1)
        s=s.replace(upload,'  </details>\n  <details><summary>Enviar documento próprio (opcional)</summary>\n'+upload,1)
        s=s.replace(history,'  </details>\n  <details><summary>Histórico antigo do acervo (opcional)</summary>\n'+history,1)
        end='\n </div>;\n}'
        if end not in s:raise RuntimeError("Fim da tela JSX não reconhecido")
        s=s.replace(end,'\n  </details>'+end,1)
    return s.encode("utf-8")

def test(*args,cwd=ROOT):
    env=os.environ.copy()
    deps=str(ROOT/".git"/"knowledge-deps")
    env["PYTHONPATH"]=deps+(os.pathsep+env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    subprocess.run(args,cwd=cwd,check=True,env=env)

def is_open(port):
    try:
        with socket.create_connection(("127.0.0.1",port),timeout=.5):return True
    except OSError:return False

def main():
    if not (ROOT/".git").exists():raise RuntimeError("Codespaces BI Factory não encontrado")
    command("git","fetch","origin",BASE.removeprefix("origin/"))
    staged={}
    for name in UPDATES+ADDS+[PARENT]:
        path=ROOT/name
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise RuntimeError("Caminho inseguro: "+name)
        local=path.read_bytes() if path.exists() else None
        if name==PARENT:
            if local is None:raise RuntimeError("Tela de Conhecimento ausente")
            new=adapt_parent(local)
        elif name in ADDS:
            new=remote(TARGET,name)
            if local is not None and local!=new:
                raise RuntimeError("Arquivo novo já existe diferente: "+name)
        else:
            if local is None:raise RuntimeError("Arquivo-base ausente: "+name)
            new=combine(name,local,remote(BASE,name),remote(TARGET,name))
        if local!=new:staged[name]=(local,new)
        print(("PREPARADO: " if local!=new else "JÁ INSTALADO: ")+name,flush=True)
    backup=ROOT/".git"/"backups"/("multifontes-"+datetime.now().strftime("%Y%m%d-%H%M%S"))
    written=[]
    try:
        for name,(old,new) in staged.items():
            target=ROOT/name
            if old is not None:
                copy=backup/name;copy.parent.mkdir(parents=True,exist_ok=True)
                copy.write_bytes(old)
            target.parent.mkdir(parents=True,exist_ok=True)
            fd,tmp=tempfile.mkstemp(prefix=".multi-",dir=target.parent)
            with os.fdopen(fd,"wb") as f:f.write(new);f.flush();os.fsync(f.fileno())
            if target.exists():os.chmod(tmp,target.stat().st_mode&0o777)
            os.replace(tmp,target)
            written.append(name)
        test(sys.executable,"-m","py_compile",
             "scripts/bi_knowledge_official.py","scripts/bi_knowledge_federated.py",
             "scripts/serve_bi_factory_api.py")
        test(sys.executable,"scripts/test_knowledge_official.py")
        test(sys.executable,"scripts/test_knowledge_federated.py")
        web=ROOT/"web/bi_factory"
        if not (web/"node_modules/.bin/vite").exists():test("npm","ci",cwd=web)
        test("npm","run","build",cwd=web)
    except Exception:
        for name in reversed(written):
            old=staged[name][0];target=ROOT/name
            if old is None:target.unlink(missing_ok=True)
            else:target.write_bytes(old)
        raise
    if backup.exists():print("BACKUP:",backup,flush=True)
    if is_open(8505):
        pids=[]
        for d in Path("/proc").iterdir():
            if not d.name.isdecimal():continue
            try:
                args=(d/"cmdline").read_bytes().replace(b"\0",b" ").decode()
                if ("scripts/serve_bi_factory_api.py" in args and
                    (d/"cwd").resolve()==ROOT):pids.append(int(d.name))
            except (OSError,ValueError,PermissionError):pass
        if len(pids)!=1:
            print("API 8505 desconhecida: código instalado sem reiniciar processo alheio.")
            return
        os.kill(pids[0],signal.SIGTERM)
        for _ in range(40):
            if not is_open(8505):break
            time.sleep(.2)
        if is_open(8505):raise RuntimeError("Porta 8505 ocupada; reinicie API conhecida")
    test("bash","scripts/start_bi_factory_codespaces.sh")
    with urllib.request.urlopen("http://127.0.0.1:8505/api/projects",timeout=8) as result:
        if "projects" not in json.load(result):raise RuntimeError("API sem projetos")
    print("OK. Abra 8506 > Conhecimento; pesquise e marque os documentos. 8507 preservada.")

if __name__=="__main__":
    try:main()
    except Exception as ex:
        print("ERRO: "+str(ex),file=sys.stderr)
        sys.exit(1)
