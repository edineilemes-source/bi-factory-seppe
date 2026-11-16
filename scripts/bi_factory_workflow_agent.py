#!/usr/bin/env python3
"""Conservative Codespaces bridge: apply reviewed GitHub commit patches without switching branches."""
import fcntl, json, os, pathlib, re, subprocess, time
ROOT=pathlib.Path("/workspaces/bi-factory-seppe")
REPO="edineilemes-source/bi-factory-seppe"
OWNER="edineilemes-source"
TITLE="[BI-AGENT] IMPLANTAR-FLUXO"
STATE=ROOT/".git/bi-factory-agent-apply-processed.json"
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
    """Apply a reviewed multi-file PR diff, never switch branches or overwrite dirty files."""
    m=re.fullmatch(r"base=([a-f0-9]{40})\\s*\\ncommit=([a-f0-9]{40})\\s*\\nbranch=(feat/fluxo-salvamento-unico-produto-20261116)\\s*",body.strip())
    if not m: raise RuntimeError("Formato não autorizado: base, commit e branch aprovada obrigatórios")
    base,sha,branch=m.groups()
    current=run("git","branch","--show-current").stdout.strip()
    if current!="teste/cadastro-filtros-20261113": raise RuntimeError("Branch local inesperada: "+current)
    run("git","fetch","--no-tags","origin",branch,timeout=120)
    remote=run("git","rev-parse","FETCH_HEAD").stdout.strip()
    if sha!=remote: raise RuntimeError("Commit não é a ponta aprovada da branch")
    run("git","merge-base","--is-ancestor",base,sha)
    paths=run("git","diff","--name-only",base,sha).stdout.splitlines()
    allowed={"web/bi_factory/src/main.jsx","prototypes/editor-visual/index.html"}
    if not paths or not set(paths).issubset(allowed):
        raise RuntimeError("Arquivos não permitidos no diff: "+str(paths))
    for path in paths:
        if run("git","status","--porcelain","--",path).stdout.strip():
            raise RuntimeError("Arquivo local modificado, implantação bloqueada: "+path)
    patch=run("git","diff","--binary",base,sha,"--",*paths).stdout
    check=run("git","apply","--check","-",input=patch,check=False)
    if check.returncode: raise RuntimeError("Patch incompatível com código local: "+check.stderr[-900:])
    run("git","apply","-",input=patch)
    return "Arquivos atualizados sem trocar branch ou tocar dados: "+", ".join(paths)+". SHA: "+sha+". Validar no navegador; alterações não commitadas."
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
def main():
    # Persistent singleton; subprocess.run closes inherited descriptors by default.
    with (ROOT/".git/bi-factory-patch-agent.lock").open("w") as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: return
        serve()

def serve():
    gh("auth","status")
    print("BI Factory patch agent ready",flush=True)
    while True:
        try: cycle()
        except Exception as exc: print("Agent error:",exc,flush=True)
        time.sleep(20)

if __name__=="__main__":
    main()
