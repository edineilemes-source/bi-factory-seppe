#!/usr/bin/env python3
"""Freeze the *running Codespaces working tree* into an immutable GitHub milestone branch.

Does not switch branches, merge, reset, restore, delete, or modify operational storage.
Requires explicit execution by Codespaces operator. GitHub code alone is not the live state.
"""
import datetime
import pathlib
import subprocess
import sys
import urllib.request

ROOT=pathlib.Path("/workspaces/bi-factory-seppe")
EXPECTED="teste/cadastro-filtros-20261113"
MARK="marco/editor-visual-homologado-20261116"
TRACKED=[
    ".devcontainer/devcontainer.json",
    "docs/DIARIO_TECNICO.md",
    "docs/ESTADO_ATUAL.md",
    "scripts/autostart_bi_factory_codespaces.sh",
    "scripts/start_bi_factory_codespaces.sh",
    "web/bi_factory/src/main.jsx",
    "prototypes/editor-visual/index.html",
]
NEW=[
    "docs/missoes/AGENTE_PERMANENTE_20261116.md",
    "docs/missoes/RECUPERACAO_OPERACIONAL_20261116.md",
    "scripts/bi_factory_patch_agent.py",
    "tests/test_patch_agent_guards.py",
]
BLOCKED_PARTS={".env",".vite","node_modules","dist","storage",".git"}
def run(*args, check=True):
    p=subprocess.run(args,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if check and p.returncode:
        raise RuntimeError(("%s: "%' '.join(args))+(p.stderr or p.stdout)[-1800:])
    return p
def safe_path(path):
    pp=pathlib.PurePosixPath(path)
    if pp.is_absolute() or ".." in pp.parts or BLOCKED_PARTS.intersection(pp.parts) or pp.name.endswith((".bak",".key",".seppekey")):
        raise RuntimeError("Caminho não permitido no marco: "+path)
    candidate=ROOT/path
    if candidate.is_symlink(): raise RuntimeError("Link simbólico não autorizado: "+path)
def main():
    if not (ROOT/".git").exists():raise RuntimeError("Não está dentro do repositório correto")
    branch=run("git","branch","--show-current").stdout.strip()
    if branch!=EXPECTED:raise RuntimeError("Branch local inesperada: "+branch)
    # The new milestone must not replace an existing remote branch.
    remote=run("git","ls-remote","--heads","origin",MARK).stdout.strip()
    if remote:raise RuntimeError("Marco já existe no GitHub; proibido sobrescrever")
    staged=run("git","diff","--cached","--name-only").stdout.strip()
    if staged:raise RuntimeError("Existem alterações já em stage; preservadas. Marco bloqueado para não misturar commits")
    for p in TRACKED+NEW:safe_path(p)
    tracked_changes=set(run("git","diff","--name-only").stdout.splitlines())
    unexpected=tracked_changes-set(TRACKED)
    if unexpected:
        raise RuntimeError("Arquivos rastreados modificados fora da lista validada: "+", ".join(sorted(unexpected)))
    for p in TRACKED:
        if not (ROOT/p).is_file():raise RuntimeError("Arquivo esperado ausente: "+p)
    print("BRANCH LOCAL:",branch,flush=True)
    print("CONFIRMAÇÃO: código do Codespaces será a referência do marco.",flush=True)
    print("Verificando build React...",flush=True)
    build=run("npm","run","build","--prefix","web/bi_factory",check=False)
    if build.returncode:raise RuntimeError("Build falhou, nada foi commitado: "+(build.stdout+build.stderr)[-2500:])
    print("BUILD APROVADO.",flush=True)
    for endpoint in ("http://127.0.0.1:8506/","http://127.0.0.1:8506/api/overview","http://127.0.0.1:8506/visual-editor/index.html"):
        try:
            with urllib.request.urlopen(endpoint,timeout=5) as res:
                if res.status!=200:raise ValueError(f"HTTP {res.status}")
            print("SERVIÇO OK:",endpoint,flush=True)
        except Exception as e:raise RuntimeError("Verificação de serviço falhou, nada commitado: "+endpoint+": "+str(e))
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    summary=(
        "\n\n## MARCO CONGELADO — Editor Visual e ficha de produtos — 2026-11-16\n"
        "- Por decisão de homologação do usuário, a versão de referência é o código efetivamente em execução no Codespaces, branch local teste/cadastro-filtros-20261113.\n"
        "- O módulo Editor Visual/ficha de produtos está suficientemente maduro para avançar aos módulos de dados; congelado funcionalmente salvo correções de defeitos.\n"
        "- Próxima etapa: entrada, modelagem, transformação e conexão de dados aos gráficos e produtos.\n"
        "- A branch remota marco/editor-visual-homologado-20261116 reproduz o commit do Codespaces; branches experimentais anteriores não são consideradas homologadas automaticamente.\n"
        "- Dados operacionais, layouts persistidos, bancos, builds e node_modules ficam fora do Git. Nenhum merge/reset/rebase ou limpeza de dados.\n"
        "- Validação do marco: build React e verificações HTTP 8506, /api/overview, /visual-editor; testes funcionais adicionais podem ser necessários.\n"
    )
    # No edit of application code. Only docs within authorized tracked paths.
    for p in ("docs/ESTADO_ATUAL.md","docs/DIARIO_TECNICO.md"):
        with (ROOT/p).open("a",encoding="utf-8") as f:f.write(summary+f"- Registro gerado em UTC: {now}.\n")
    add=[p for p in TRACKED+NEW if (ROOT/p).is_file()]
    run("git","add","--",*add)
    staged_files=run("git","diff","--cached","--name-only").stdout.splitlines()
    if not staged_files:raise RuntimeError("Nenhuma alteração para registrar; commit de marco não criado")
    unexpected_stage=set(staged_files)-set(add)
    if unexpected_stage:raise RuntimeError("Stage contém arquivo fora da lista: "+str(unexpected_stage))
    print("ARQUIVOS NO COMMIT:",", ".join(staged_files),flush=True)
    run("git","commit","-m","Marco homologado: congelar editor visual e iniciar etapa de dados")
    sha=run("git","rev-parse","HEAD").stdout.strip()
    try:
        run("git","push","origin",f"HEAD:refs/heads/{MARK}")
    except Exception:
        print("COMMIT LOCAL CONCLUÍDO, mas push não confirmado; commit SHA:",sha,flush=True)
        raise
    check=run("git","ls-remote","--heads","origin",MARK).stdout.strip().split()[0]
    if check!=sha:raise RuntimeError("Hash remoto não coincide com commit local!")
    print("MARCO SINCRONIZADO COM SUCESSO",flush=True)
    print("CODESPACES HEAD:",sha,flush=True)
    print("GITHUB BRANCH:",MARK,flush=True)
    print("GITHUB SHA:",check,flush=True)
    print("DADOS OPERACIONAIS: NÃO ALTERADOS",flush=True)
    print("PRÓXIMA ETAPA: MÓDULOS DE DADOS",flush=True)
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("MARCO NÃO CONCLUÍDO:",e,file=sys.stderr,flush=True)
        sys.exit(1)
