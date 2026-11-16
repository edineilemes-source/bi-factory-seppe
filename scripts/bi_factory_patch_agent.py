#!/usr/bin/env python3
"""Conservative Codespaces bridge: apply reviewed GitHub commit patches without switching branches."""
import json, os, pathlib, re, subprocess, time
ROOT=pathlib.Path("/workspaces/bi-factory-seppe")
REPO="edineilemes-source/bi-factory-seppe"
OWNER="edineilemes-source"
TITLE="[BI-AGENT] APLICAR"
STATE=pathlib.Path("/tmp/bi-factory-agent-apply-processed.json")
LOG=pathlib.Path("/tmp/bi-factory-seppe-logs")
LOG.mkdir(parents=True,exist_ok=True)
ALLOWED={"web/bi_factory/src/main.jsx"}
def run(*args, input=None, timeout=90, check=True):
    p=subprocess.run(args,cwd=ROOT,input=input,text=True,capture_output=True,timeout=timeout)
    if check and p.returncode: raise RuntimeError((p.stderr or p.stdout)[-1300:])
    return p
def gh(*args): return run("gh",*args,timeout=45).stdout.strip()
def report(n,message): gh("issue","comment",str(n),"--repo",REPO,"--body",message[:3500])
def apply(body):
    m=re.fullmatch(r"commit=([a-f0-9]{40})\s*\nbranch=(fix/novo-produto-ficha-isolada-20261116)\s*",body.strip())
    if not m: raise RuntimeError("Formato não autorizado: requer commit SHA completo e branch permitida")
    sha,branch=m.groups()
    current=run("git","branch","--show-current").stdout.strip()
    if current!="teste/cadastro-filtros-20261113": raise RuntimeError("Branch local inesperada: "+current)
    run("git","fetch","--no-tags","origin",branch,timeout=120)
    remote=run("git","rev-parse","FETCH_HEAD").stdout.strip()
    run("git","merge-base","--is-ancestor",sha,remote)
    parent=run("git","rev-parse",sha+"^").stdout.strip()
    paths=run("git","diff","--name-only",parent,sha).stdout.splitlines()
    if not paths or not set(paths).issubset(ALLOWED): raise RuntimeError("Commit altera caminhos fora da lista permitida: "+str(paths))
    if run("git","status","--porcelain","--",*paths).stdout.strip(): raise RuntimeError("Arquivo local alterado; aplicação bloqueada para preservar trabalho")
    patch=run("git","diff","--binary",parent,sha,"--",*paths).stdout
    if not patch.strip(): raise RuntimeError("Patch vazio")
    check=run("git","apply","--check","-",input=patch,check=False)
    if check.returncode: raise RuntimeError("Patch não aplicável sem conflitos: "+check.stderr[-900:])
    run("git","apply","-",input=patch)
    return "Patch aplicado sem trocar branch ou sobrescrever alterações locais. Arquivos: "+", ".join(paths)+"; commit fonte: "+sha+". Alterações ficam no working tree para homologação, sem commit/push automático."
def cycle():
    try: seen=set(json.loads(STATE.read_text()))
    except (FileNotFoundError,ValueError): seen=set()
    issues=json.loads(gh("issue","list","--repo",REPO,"--state","open","--limit","100","--json","number,title,author,body"))
    for item in issues:
        n=item["number"]
        if n in seen or item["title"]!=TITLE or item.get("author",{}).get("login","").lower()!=OWNER: continue
        seen.add(n);STATE.write_text(json.dumps(sorted(seen)))
        try:
            report(n,"Agente recebeu solicitação de aplicação; verificando branch, commit, arquivos e conflitos.")
            result=apply(item.get("body") or "")
            report(n,"✅ "+result)
            gh("issue","close",str(n),"--repo",REPO,"--comment","Aplicação concluída; aguardando homologação visual.")
        except Exception as exc:
            report(n,"❌ Aplicação bloqueada: "+str(exc)[-1500:])
if __name__=="__main__":
    gh("auth","status")
    print("BI Factory patch agent ready",flush=True)
    while True:
        try: cycle()
        except Exception as exc: print("Agent error:",exc,flush=True)
        time.sleep(20)
