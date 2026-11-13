#!/usr/bin/env python3
"""Allowlisted GitHub Issues bridge: start/check BI Factory only, never switch branches."""
import json, os, pathlib, subprocess, time
ROOT=pathlib.Path(__file__).resolve().parent.parent
REPO="edineilemes-source/bi-factory-seppe"
OWNER="edineilemes-source"
TITLE="[BI-AGENT] ABRIR"
STATE=pathlib.Path("/tmp/bi-factory-agent-open-processed.json")
LOG=pathlib.Path("/tmp/bi-factory-seppe-logs")
LOG.mkdir(parents=True,exist_ok=True)
def gh(*args):
    r=subprocess.run(["gh",*args],cwd=ROOT,capture_output=True,text=True,timeout=45)
    if r.returncode: raise RuntimeError(r.stderr[-900:] or r.stdout[-900:])
    return r.stdout.strip()
def report(n,msg): gh("issue","comment",str(n),"--repo",REPO,"--body",msg[:3500])
def cycle():
    try: seen=set(json.loads(STATE.read_text()))
    except (FileNotFoundError,ValueError): seen=set()
    issues=json.loads(gh("issue","list","--repo",REPO,"--state","open","--limit","100","--json","number,title,author"))
    for issue in issues:
        n=issue["number"]
        if n in seen or issue["title"]!=TITLE or issue.get("author",{}).get("login","").lower()!=OWNER: continue
        seen.add(n);STATE.write_text(json.dumps(sorted(seen)))
        try:
            report(n,"Agente recebeu solicitação de abertura do BI Factory.")
            with (LOG/"agent-open-startup.log").open("w") as out:
                r=subprocess.run(["bash","scripts/start_bi_factory_codespaces.sh"],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,timeout=180)
            detail=(LOG/"agent-open-startup.log").read_text(errors="replace")[-2000:]
            if r.returncode: raise RuntimeError(detail)
            report(n,"✅ BI Factory iniciado/verificado (8505 API, 8506 frontend).\n\n```\n"+detail+"\n```")
            gh("issue","close",str(n),"--repo",REPO,"--comment","Concluído pelo agente.")
        except Exception as exc:
            report(n,"❌ Falha ao iniciar: "+str(exc)[-1800:])
if __name__=="__main__":
    gh("auth","status")
    print("BI Factory Agent: aguardando solicitações ABRIR",flush=True)
    while True:
        try: cycle()
        except Exception as exc: print("Agent error:",exc,flush=True)
        time.sleep(30)
