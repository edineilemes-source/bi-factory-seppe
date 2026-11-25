#!/usr/bin/env python3
"""Add a reviewable document library and project-scoped knowledge to BI Factory.

Only the user runs this script inside Codespaces. Never changes branches or
resets/deletes uncommitted work. Takes backups; executes tests/build before
restarting the known API on 8505. Leaves 8506 and 8507 frontend processes alone.
"""
from __future__ import annotations
from datetime import datetime
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
import json

ROOT=Path("/workspaces/bi-factory-seppe")
BASE="origin/fix/conhecimento-installer-autoteste-preservacao-20261124"
TARGET="origin/feat/conhecimento-biblioteca-leitura-modelagem-20261125"
UPDATED=(
 "scripts/bi_knowledge_official.py",
 "scripts/bi_factory_projects.py",
 "scripts/serve_bi_factory_api.py",
 "web/bi_factory/src/OfficialKnowledgeSearch.jsx",
)
DATAWORKSPACE="web/bi_factory/src/DataWorkspace.jsx"
NEW=(
 "scripts/bi_knowledge_library.py",
 "scripts/test_knowledge_library.py",
 "web/bi_factory/src/KnowledgeLibrary.jsx",
 "web/bi_factory/src/ModelKnowledgeContext.jsx",
 "requirements-knowledge.txt",
)
WEB=ROOT/"web/bi_factory"
MAX_NEW=700_000

def fetch_git(ref,name):
    p=subprocess.run(["git","show",ref+":"+name],cwd=ROOT,capture_output=True)
    if p.returncode!=0:
        raise RuntimeError("Referência indisponível no GitHub: "+ref+":"+name)
    if len(p.stdout)>MAX_NEW:
        raise RuntimeError("Arquivo remoto acima do limite: "+name)
    return p.stdout

def merge_three(name,base,local,new):
    if local==new:return local
    if local==base:return new
    with tempfile.TemporaryDirectory(prefix="bi-library-merge-") as temp:
        paths=[Path(temp)/item for item in ("local","base","update")]
        for dest,content in zip(paths,(local,base,new)):
            dest.write_bytes(content)
        p=subprocess.run(["git","merge-file","-p","--diff3",
            *(str(item) for item in paths)],capture_output=True)
    if p.returncode!=0:
        raise RuntimeError("Alterações locais incompatíveis em "+name+
            ". Nada foi modificado. Trecho necessário: "+p.stderr.decode("utf-8","replace")[-150:])
    return p.stdout

def insert_model_component(local):
    """Only add one import and one JSX slot to the user's DataWorkspace."""
    c=local.decode("utf-8")
    marker="BI_KNOWLEDGE_MODEL_CONTEXT"
    if marker in c:return local
    if "<ModelKnowledgeContext projectId={projectId} fields={fields}/>" in c:
        return local
    anchor='area==="Modelagem"&&<>'
    if c.count(anchor)!=1:
        raise RuntimeError("Não identifiquei com segurança a área Modelagem do DataWorkspace.jsx")
    if "const fields=" not in c or "projectId" not in c:
        raise RuntimeError("Campos de modelagem ou ID do projeto não identificados")
    insert='import ModelKnowledgeContext from "./ModelKnowledgeContext.jsx";\n'
    if insert not in c:
        imports=list(re.finditer(r'(?m)^[ \t]*import[^\n]*;[ \t]*\r?\n',c))
        where=imports[-1].end() if imports else 0
        c=c[:where]+insert+c[where:]
    add="\n        {/* BI_KNOWLEDGE_MODEL_CONTEXT */}\n        <ModelKnowledgeContext projectId={projectId} fields={fields}/>"
    c=c.replace(anchor,anchor+add,1)
    return c.encode("utf-8")

def validate_local_change(name,updated):
    c=updated.decode("utf-8")
    checks={
      "scripts/bi_knowledge_official.py":("capag","not a PDF","downloadable"),
      "scripts/bi_factory_projects.py":('not item.get("deleted_at")',),
      "scripts/serve_bi_factory_api.py":("bi_knowledge_library","read-documents",
                 "do_DELETE","concepts","/interpret"),
      "web/bi_factory/src/OfficialKnowledgeSearch.jsx":("KnowledgeLibrary","CAPAG"),
      DATAWORKSPACE:("ModelKnowledgeContext","projectId={projectId}"),
    }
    for term in checks.get(name,()):
        if term not in c:
            # In the case of wording changes, provide a specific location, no overwrite.
            raise RuntimeError("Integração incompleta em "+name+": "+term)

def run(cmd,cwd=ROOT):
    print("TESTANDO:",' '.join(cmd),flush=True)
    subprocess.run(cmd,cwd=cwd,check=True)

def listening(port):
    try:
        with socket.create_connection(("127.0.0.1",port),timeout=.6):return True
    except OSError:return False

def owned_api():
    matches=[]
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():continue
        try:
            command=(entry/"cmdline").read_bytes().replace(b"\x00",b" ").decode("utf-8","replace")
            if "scripts/serve_bi_factory_api.py" not in command:continue
            if (entry/"cwd").resolve()!=ROOT:continue
            matches.append(int(entry.name))
        except (ValueError,OSError,PermissionError):
            continue
    return matches

def check_json(url):
    with urlopen(url,timeout=6) as response:
        return json.loads(response.read(1_000_000))

def deploy():
    if not (ROOT/".git").is_dir():
        raise RuntimeError("Abra o Codespaces do bi-factory-seppe antes de executar")
    # Check a realistic local edit without touching a single actual file.
    old=fetch_git(BASE,DATAWORKSPACE)
    synthetic=b"// comentário local preservado\n"+old
    changed=insert_model_component(synthetic)
    if not changed.startswith(b"// comentário local preservado\n"):
        raise RuntimeError("Pré-teste: cabeçalho local não preservado")
    if insert_model_component(changed)!=changed:
        raise RuntimeError("Pré-teste: duplicação da integração da Modelagem")
    print("OK pré-teste: personalizações locais de Modelagem preservadas.",flush=True)
    pending={}
    for name in (*UPDATED,DATAWORKSPACE,*NEW):
        path=ROOT/name
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise RuntimeError("Arquivo local inseguro para atualizar: "+name)
        old=path.read_bytes() if path.exists() else None
        if name in NEW:
            new=fetch_git(TARGET,name)
            if old is not None and old!=new:
                raise RuntimeError("Arquivo novo já existe diferente e não será sobrescrito: "+name)
        elif name==DATAWORKSPACE:
            if old is None:raise RuntimeError("DataWorkspace existente não encontrado")
            new=insert_model_component(old)
        else:
            if old is None:raise RuntimeError("Arquivo local necessário não encontrado: "+name)
            new=merge_three(name,fetch_git(BASE,name),old,fetch_git(TARGET,name))
        if old==new:
            print("JÁ INSTALADO:",name)
            continue
        if name not in NEW:validate_local_change(name,new)
        pending[name]=(old,new)
        print("PREPARADO:",name,flush=True)
    stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
    backup=ROOT/".git"/"backups"/("biblioteca-conhecimento-"+stamp)
    modified=[]
    try:
        for name,(old,new) in pending.items():
            path=ROOT/name
            if old is not None:
                copy=backup/name
                copy.parent.mkdir(parents=True,exist_ok=True)
                copy.write_bytes(old)
            path.parent.mkdir(parents=True,exist_ok=True)
            fd,temp=tempfile.mkstemp(prefix=".bi-knowledge-",dir=path.parent)
            try:
                with os.fdopen(fd,"wb") as stream:
                    stream.write(new)
                    stream.flush()
                    os.fsync(stream.fileno())
                if path.exists():os.chmod(temp,path.stat().st_mode&0o777)
                os.replace(temp,path)
            finally:
                if os.path.exists(temp):os.unlink(temp)
            modified.append(name)
            print("ATUALIZADO:",name,flush=True)
        # Only local OSS dependency; no global Python changes or model downloads.
        import importlib.util
        if importlib.util.find_spec("pypdf") is None:
            deps=ROOT/".git"/"knowledge-deps"
            deps.mkdir(parents=True,exist_ok=True)
            run([sys.executable,"-m","pip","install","--no-deps",
                 "--target",str(deps),"-r","requirements-knowledge.txt"])
        run([sys.executable,"-m","py_compile",
             "scripts/bi_knowledge_official.py","scripts/bi_knowledge_library.py",
             "scripts/bi_factory_projects.py","scripts/serve_bi_factory_api.py"])
        run([sys.executable,"scripts/test_knowledge_official.py"])
        run([sys.executable,"scripts/test_knowledge_library.py"])
        run([sys.executable,"scripts/test_knowledge_compat_installer.py"])
        if not (WEB/"node_modules/.bin/vite").exists():
            run(["npm","ci"],WEB)
        run(["npm","run","build"],WEB)
    except Exception:
        print("Falha de testes/compilação. Restaurando código original.",flush=True)
        for name in reversed(modified):
            old=pending[name][0]
            path=ROOT/name
            if old is None:path.unlink(missing_ok=True)
            else:path.write_bytes(old)
        raise
    if backup.exists():print("BACKUP DO CÓDIGO:",backup,flush=True)
    print("Código validado; carregando biblioteca na API 8505.",flush=True)
    if listening(8505):
        owners=owned_api()
        if len(owners)!=1:
            print("API 8505 ativa, mas processo não identificável; não será interrompido.")
            print("Código instalado; reinicialização manual da API ainda necessária.")
            return
        os.kill(owners[0],signal.SIGTERM)
        for _ in range(40):
            if not listening(8505):break
            time.sleep(.2)
        if listening(8505):
            raise RuntimeError("8505 não liberou porta; nenhum processo externo foi encerrado")
    run(["bash","scripts/start_bi_factory_codespaces.sh"])
    # Use the existing PMCG project; read-only API requests.
    catalog=check_json("http://127.0.0.1:8505/api/projects")
    if not isinstance(catalog.get("projects"),list):
        raise RuntimeError("API /api/projects não respondeu no contrato esperado")
    index=check_json("http://127.0.0.1:8505/api/projects/pmcg-financas-publicas/library")
    if not isinstance(index.get("documents"),list):
        raise RuntimeError("Rota /library não foi ativada na API 8505")
    print("OK Biblioteca e Modelagem de conceitos integradas. PDFs antigos preservados.",flush=True)
    print("Abra a aplicação na 8506; atualize com Ctrl+Shift+R.",flush=True)
    print("8507 experimental, catálogo de produtos e bases fiscais não foram modificados.")

if __name__=="__main__":
    try:deploy()
    except Exception as error:
        print("ERRO AO ATIVAR BIBLIOTECA E IA:",error,file=sys.stderr,flush=True)
        sys.exit(1)
