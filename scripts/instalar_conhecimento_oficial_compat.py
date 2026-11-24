#!/usr/bin/env python3
"""Integra pesquisa oficial de conhecimento na BI Factory sem alterar dados/branches.

Pré-condições: Codespaces existente com git fetch da branch do recurso.
Backup do código anterior em .git/backups; conserva KnowledgeStart local e injeta pesquisa oficial isolada.
Somente API 8505 conhecida é reiniciada; serviço da 8507 não é interrompido.
"""
from __future__ import annotations
from datetime import datetime
import os
import re
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import json

ROOT=Path("/workspaces/bi-factory-seppe")
BASE="origin/fix/editor8507-integrado-catalogo-8506-20261124"
TARGET="origin/fix/conhecimento-installer-autoteste-preservacao-20261124"
MODIFIED=("scripts/serve_bi_factory_api.py",)
EXTENDED="web/bi_factory/src/KnowledgeStart.jsx"
NEW=(
 "scripts/bi_knowledge_official.py",
 "scripts/test_knowledge_official.py",
 "web/bi_factory/src/OfficialKnowledgeSearch.jsx",
 "scripts/test_knowledge_compat_installer.py",
 "scripts/instalar_conhecimento_oficial_compat.py",
)
ALL=(*MODIFIED,EXTENDED,*NEW)
WEB=ROOT/"web/bi_factory"

def git_bytes(ref,path):
    result=subprocess.run(["git","show",ref+":"+path],cwd=ROOT,capture_output=True)
    if result.returncode:
        raise RuntimeError("Arquivo remoto não disponível: "+ref+":"+path)
    return result.stdout

def merge3(name,base,current,wanted):
    with tempfile.TemporaryDirectory(prefix="knowledge-merge-") as directory:
        paths=[Path(directory)/x for x in ("local","base","updated")]
        for path,content in zip(paths,(current,base,wanted)):
            path.write_bytes(content)
        result=subprocess.run(["git","merge-file","-p","--diff3",
                               *(str(x) for x in paths)],capture_output=True)
    if result.returncode:
        raise RuntimeError("Conflito de código no arquivo "+name+
          ": o arquivo local foi preservado. "+result.stderr.decode("utf-8","replace")[-300:])
    return result.stdout

def inject_knowledge_ui(original):
    """Preserva o componente KnowledgeStart local; insere apenas o módulo novo.

    Recusa layouts que não possa reconhecer com segurança. Idempotente:
    nunca duplica a integração nem troca os campos da ficha.
    """
    text=original.decode("utf-8")
    if ("BI_KNOWLEDGE_OFFICIAL_SLOT" in text or
        ('"/discover"' in text and '"/approve"' in text)):
        return original
    func=re.search(r'\bfunction\s+KnowledgeStart\s*\(',text)
    if not func:
        raise RuntimeError("KnowledgeStart local não apresenta a função conhecida: nada foi alterado")
    after=text[func.end():]
    found=re.search(r'\breturn\s*\(?\s*<(?:div|main|section)\b[^>]*>',after)
    if not found:
        found=re.search(r'\breturn\s*\(?\s*<>',after)
    if not found:
        raise RuntimeError("KnowledgeStart local: elemento principal JSX não localizado com segurança")
    at=func.end()+found.end()
    import_stmt='import OfficialKnowledgeSearch from "./OfficialKnowledgeSearch.jsx";\n'
    # Import estático no início do módulo; componente dentro do container original.
    if import_stmt not in text:
        # Colocar após imports já existentes mantém comentários e personalizações
        # no começo do arquivo, inclusive na simulação com cabeçalho local.
        imports=list(re.finditer(r'(?m)^[ \t]*import[^\n]*;[ \t]*\r?\n',text[:func.start()]))
        if imports:
            position=imports[-1].end()
        else:
            # Componentes sem import devem receber o import no topo.
            position=0
        text=text[:position]+import_stmt+text[position:]
        if position<=at:
            at+=len(import_stmt)
    slot='\n  {/* BI_KNOWLEDGE_OFFICIAL_SLOT: pesquisa oficial adicionada sem substituir o cadastro */}\n  <OfficialKnowledgeSearch project={project}/>\n'
    text=text[:at]+slot+text[at:]
    if text.count("BI_KNOWLEDGE_OFFICIAL_SLOT")!=1:
        raise RuntimeError("Falha no controle de integração única de Conhecimento")
    return text.encode("utf-8")

def test(name,cmd,cwd=ROOT):
    print("TESTANDO",name,flush=True)
    subprocess.run(cmd,cwd=cwd,check=True)

def alive(port):
    try:
        with socket.create_connection(("127.0.0.1",port),timeout=.6):return True
    except OSError:return False

def owned_api_pids():
    found=[]
    for p in Path("/proc").iterdir():
        if not p.name.isdecimal():continue
        try:
            args=(p/"cmdline").read_bytes().replace(b"\0",b" ").decode("utf-8","replace")
            cwd=(p/"cwd").resolve()
            if "scripts/serve_bi_factory_api.py" in args and cwd==ROOT:
                found.append(int(p.name))
        except (OSError,ValueError,PermissionError):
            continue
    return found

def http_json(url):
    with urllib.request.urlopen(url,timeout=5) as response:
        return json.loads(response.read(1_000_000))

def main():
    if not (ROOT/".git").is_dir():
        raise RuntimeError("Execute no Codespaces /workspaces/bi-factory-seppe")
    # Simulação de conflitos locais antes de qualquer escrita.
    base_view=git_bytes(BASE,EXTENDED)
    edited_view=b"// comentario local que deve permanecer intacto\n"+base_view
    merged_view=inject_knowledge_ui(edited_view)
    if not merged_view.startswith(b"// comentario local"):
        raise RuntimeError("Cabeçalho local não preservado durante a simulação")
    if b"// comentario local que deve permanecer intacto" not in merged_view:
        raise RuntimeError("Comentário local perdido durante a simulação")
    if inject_knowledge_ui(merged_view)!=merged_view:
        raise RuntimeError("Componente duplicado após segunda integração")
    print("OK: tela Conhecimento local preservada na simulação.",flush=True)
    pending={}
    for name in ALL:
        remote=None if name==EXTENDED else git_bytes(TARGET,name)
        dest=ROOT/name
        if dest.is_symlink() or (dest.exists() and not dest.is_file()):
            raise RuntimeError("Arquivo local não é seguro para mesclar: "+name)
        local=dest.read_bytes() if dest.exists() else None
        if name==EXTENDED:
            if local is None:
                raise RuntimeError("Arquivo KnowledgeStart.jsx local ausente")
            print("PRESERVANDO TELA EXISTENTE:",name,flush=True)
            final=inject_knowledge_ui(local)
            if final!=local:pending[name]=(local,final)
            else:print("JÁ INTEGRADO:",name)
            continue
        if local==remote:
            print("JÁ INSTALADO",name)
            continue
        if name in NEW:
            if local is not None:
                raise RuntimeError("Novo arquivo "+name+" já existe diferente; sem sobrescrever")
            pending[name]=(local,remote)
            continue
        if local is None:
            raise RuntimeError("Arquivo existente ausente: "+name)
        base=git_bytes(BASE,name)
        if local==base:
            final=remote
        else:
            print("PRESERVANDO ALTERAÇÕES LOCAIS",name,flush=True)
            final=merge3(name,base,local,remote)
        if final!=local:pending[name]=(local,final)
    if not pending:
        print("Código de pesquisa oficial já está presente.")
    backup=ROOT/".git"/"backups"/("conhecimento-oficial-"+datetime.now().strftime("%Y%m%d-%H%M%S"))
    written=[]
    try:
        for name,(old,new) in pending.items():
            dest=ROOT/name
            if old is not None:
                copy=backup/name
                copy.parent.mkdir(parents=True,exist_ok=True)
                copy.write_bytes(old)
            dest.parent.mkdir(parents=True,exist_ok=True)
            fd,tmp=tempfile.mkstemp(prefix=".knowledge-update-",dir=dest.parent)
            try:
                with os.fdopen(fd,"wb") as writer:
                    writer.write(new);writer.flush();os.fsync(writer.fileno())
                if dest.exists():os.chmod(tmp,dest.stat().st_mode&0o777)
                os.replace(tmp,dest)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
            written.append(name)
            print("INTEGRADO",name,flush=True)
        test("Sintaxe backend", [sys.executable,"-m","py_compile",
                                "scripts/bi_knowledge_official.py",
                                "scripts/serve_bi_factory_api.py"])
        test("Pesquisa e aprovação de PDFs sem rede", [sys.executable,
                 "scripts/test_knowledge_official.py"])
        test("Preservação da tela Conhecimento", [sys.executable,
                 "scripts/test_knowledge_compat_installer.py"])
        if not (WEB/"node_modules/.bin/vite").exists():
            test("Dependências do React",[ "npm","ci"],WEB)
        test("Compilação da interface Conhecimento",["npm","run","build"],WEB)
    except Exception:
        print("Teste falhou. Restaurando código anterior e mantendo dados originais.",flush=True)
        for name in reversed(written):
            old=pending[name][0]
            dest=ROOT/name
            if old is None:dest.unlink(missing_ok=True)
            else:dest.write_bytes(old)
        raise
    if backup.exists():print("BACKUP DE CÓDIGO:",backup,flush=True)
    print("Código validado. Verificando API 8505 para carregar a nova pesquisa.",flush=True)
    if alive(8505):
        pids=owned_api_pids()
        if len(pids)!=1:
            print("API 8505 não identificada univocamente. Nenhum processo foi interrompido.")
            print("Reinicie a API apenas após identificar o processo; arquivos e testes estão instalados.")
            return
        os.kill(pids[0],signal.SIGTERM)
        for _ in range(35):
            if not alive(8505):break
            time.sleep(.2)
        if alive(8505):
            raise RuntimeError("API 8505 não liberou a porta; serviços não foram alterados")
    test("Iniciar/verificar BI Factory",["bash","scripts/start_bi_factory_codespaces.sh"])
    projects=http_json("http://127.0.0.1:8505/api/projects")
    if not isinstance(projects,dict) or "projects" not in projects:
        raise RuntimeError("API /api/projects não está respondendo no contrato esperado")
    print("OK: Conhecimento com Pesquisa oficial e aprovação de PDFs integrado à aplicação.")
    print("Sem alterações em produtos, layouts, fontes fiscais ou no laboratório 8507.")
    print("Abra a aplicação BI Factory (porta do catálogo) e atualize Ctrl+Shift+R.",flush=True)

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("ERRO AO INSTALAR PESQUISA OFICIAL:",exc,file=sys.stderr,flush=True)
        sys.exit(1)
