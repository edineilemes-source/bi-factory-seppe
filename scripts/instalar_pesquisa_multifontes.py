#!/usr/bin/env python3
"""Instalador seguro da pesquisa multifontes (sem trocar branch local)."""
from datetime import datetime
from pathlib import Path
import json,os,signal,socket,subprocess,sys,tempfile,time,urllib.request
ROOT=Path("/workspaces/bi-factory-seppe")
BASE="origin/feat/conhecimento-download-automatico-capag-20261125"
TARGET="origin/feat/conhecimento-busca-multifontes-simples-20261125"
PREVIOUS="2546251b475e65d536534672452b0e35967fe453"
KNOWN_PREVIOUS_REFS=(
 "5fe6b1886f2e67a088d3ce57db4b580dd75db749",
 "10b8e1f7e56cde9f3709aedfa9797f521d448aa8",
 "0fb7e7a1aa9760f9e1524ee5f4d909a1116c34c7",
 "639023be0129d1920722b2160afb2ceba40f1b2c",
 "b6b062e9e441439e3f745620a2a6ff770e8299cf",
)
UPDATES=["scripts/bi_knowledge_official.py","web/bi_factory/src/OfficialKnowledgeSearch.jsx",
         "web/bi_factory/src/KnowledgeLibrary.jsx"]
ADDS=["scripts/bi_knowledge_federated.py","scripts/test_knowledge_federated.py",
      "scripts/test_instalar_pesquisa_multifontes.py",
      "scripts/test_knowledge_research_again.py",
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
    # Reconhece a versão multifontes instalada na rodada anterior, evitando
    # conflito de merge entre duas alterações legítimas do mesmo componente.
    previous=remote(PREVIOUS,path)
    if local==previous:return new
    for older_ref in KNOWN_PREVIOUS_REFS:
        try:
            if local==remote(older_ref,path):return new
        except RuntimeError:
            continue
    with tempfile.TemporaryDirectory() as directory:
        paths=[Path(directory)/x for x in ("local","base","alvo")]
        for p,data in zip(paths,(local,old,new)):p.write_bytes(data)
        result=subprocess.run(["git","merge-file","-p","--diff3",
          *(str(x) for x in paths)],capture_output=True)
    if result.returncode:raise RuntimeError("Conflito: "+path+". Nada foi instalado.")
    return result.stdout

def adapt_parent(raw):
    """Insere a pesquisa sem sobrescrever a tela KnowledgeStart personalizada.

    O layout conhecido pode ter a busca antiga recolhida. Para layouts locais
    diferentes, só injeta import e componente no início da raiz JSX.
    O restante do arquivo é preservado byte a byte (salvo pelas inserções).
    """
    import re
    s=raw.decode("utf-8")
    # A instalação anterior pode ter colocado a pesquisa na tela local.
    # Atualizar somente o módulo importado, jamais inseri-lo duas vezes.
    if ("BI_KNOWLEDGE_OFFICIAL_SLOT" in s or
        re.search(r"<OfficialKnowledgeSearch\b", s)):
        return raw
    func=re.search(r"\bfunction\s+KnowledgeStart\s*\(",s)
    if not func:
        raise RuntimeError("Função KnowledgeStart local não encontrada; arquivo preservado.")
    tail=s[func.end():]
    root=re.search(r"\breturn\s*\(?\s*<(?:div|main|section)\b[^>]*>",tail)
    if not root:
        root=re.search(r"\breturn\s*\(?\s*<>",tail)
    if not root:
        raise RuntimeError("Raiz JSX da tela Conhecimento não reconhecida; arquivo preservado.")
    at=func.end()+root.end()
    import_line='import OfficialKnowledgeSearch from "./OfficialKnowledgeSearch.jsx";\n'
    if 'import OfficialKnowledgeSearch from' not in s:
        imports=list(re.finditer(r'(?m)^[ \t]*import[^\n]*;[ \t]*\r?\n',s[:func.start()]))
        position=imports[-1].end() if imports else 0
        s=s[:position]+import_line+s[position:]
        if position<=at:at+=len(import_line)
    slot=('\n  {/* BI_KNOWLEDGE_OFFICIAL_SLOT: pesquisa por tema, preserva tela local */}\n'
          '  <OfficialKnowledgeSearch project={project}/>\n')
    s=s[:at]+slot+s[at:]
    if s.count("BI_KNOWLEDGE_OFFICIAL_SLOT")!=1:
        raise RuntimeError("Integração duplicada; tela original preservada")
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
            # O instalador é executado diretamente do GitHub. Se já há
            # uma cópia local antiga, preserva-a em vez de falhar ao atualizar.
            if name=="scripts/instalar_pesquisa_multifontes.py" and local is not None:
                new=local
            elif local is not None and local!=new:
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
        test(sys.executable,"scripts/test_knowledge_research_again.py")
        test(sys.executable,"scripts/test_instalar_pesquisa_multifontes.py")
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
