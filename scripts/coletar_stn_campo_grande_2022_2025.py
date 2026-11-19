#!/usr/bin/env python3
"""Coleta oficial STN SICONFI: Campo Grande/MS, 2022-2025. Não altera storage operacional."""
import csv,json,time,sys,re,datetime,urllib.request,urllib.error,urllib.parse
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED

BASE="https://apidatalake.tesouro.gov.br/ords/siconfi/tt"
OUT=Path("/workspaces/bi-factory-seppe/artifacts/stn_campo_grande_2022_2025")
IBGE=5002704
OUT.mkdir(parents=True,exist_ok=True)
last=[0.0]
manifest={"fonte":BASE,"municipio":"Campo Grande/MS","id_ente":IBGE,"inicio_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"consultas":[],"falhas":[]}
records=[]

def fetch(endpoint,params):
    offset=0
    rows=[]
    while True:
        query=urllib.parse.urlencode({**params,"limit":5000,"offset":offset})
        url=f"{BASE}/{endpoint}?{query}"
        error=None
        for attempt in range(5):
            delay=1.1-(time.monotonic()-last[0])
            if delay>0:time.sleep(delay)
            last[0]=time.monotonic()
            try:
                req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"BI-Factory-SEPPE-STN/1.0"})
                with urllib.request.urlopen(req,timeout=60) as response:
                    data=json.load(response)
                break
            except (urllib.error.URLError,TimeoutError,ValueError) as exc:
                error=exc
                if attempt<4:time.sleep(min(20,2**attempt+1))
        else:raise RuntimeError(f"Falha na consulta {url}: {error}")
        if not isinstance(data.get("items"),list):raise ValueError(f"Resposta inválida: {url}")
        items=data["items"]
        rows.extend(items)
        if not data.get("hasMore"):return rows
        if not items:raise ValueError("Paginação vazia com hasMore=true")
        offset+=len(items)

def save_csv(file,rows):
    cols=list(dict.fromkeys(k for row in rows for k in row))
    with file.open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=cols or ["sem_registros"])
        writer.writeheader()
        if rows:writer.writerows(rows)

def collect(tipo,year,period,annex="",poder="",periodicidade=""):
    params={"an_exercicio":year,"id_ente":IBGE}
    if tipo!="DCA":
        params.update({"nr_periodo":period,"co_tipo_demonstrativo":tipo,"no_anexo":annex})
    if poder:params["co_poder"]=poder
    if periodicidade:params["in_periodicidade"]=periodicidade
    name=f"{tipo}_{year}_{period}_{annex}_{poder}_{periodicidade}"
    name=re.sub(r"[^a-zA-Z0-9_-]","_",name)+".json"
    path=OUT/name
    try:
        if path.exists():
            rows=json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(rows,list):raise ValueError("Arquivo de retomada inválido")
        else:
            rows=fetch(tipo.lower(),params)
            path.write_text(json.dumps(rows,ensure_ascii=False),encoding="utf-8")
        manifest["consultas"].append({"tipo":tipo,"ano":year,"periodo":period,"anexo":annex,"poder":poder,"periodicidade":periodicidade,"linhas":len(rows),"arquivo":name})
        records.extend({"_tipo_relatorio":tipo,"_ano_consulta":year,"_periodo_consulta":period,"_anexo_consulta":annex,"_poder_consulta":poder,**item} for item in rows)
        print(f"{tipo} {year} {period} {annex or 'todos'} {poder}: {len(rows)} registros",flush=True)
        return len(rows)
    except Exception as e:
        manifest["falhas"].append({"tipo":tipo,"ano":year,"periodo":period,"anexo":annex,"poder":poder,"erro":str(e)})
        print("FALHA:",tipo,year,period,annex,poder,str(e),file=sys.stderr,flush=True)
        return -1
    finally:
        (OUT/"manifesto.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")

def main():
    for year in range(2022,2026):
        for period in range(1,7):
            for anexo in range(1,15):
                collect("RREO",year,period,f"RREO-Anexo {anexo:02d}")
        for period in range(1,4):
            for poder in ("E","L"):
                count=collect("RGF",year,period,poder=poder,periodicidade="Q")
                if count<=0:
                    for anexo in range(1,7):
                        collect("RGF",year,period,f"RGF-Anexo {anexo:02d}",poder,"Q")
        collect("DCA",year,0)
    save_csv(OUT/"registros_detalhados.csv",records)
    summary=[]
    for tipo in ("RREO","RGF","DCA"):
        for year in range(2022,2026):
            subset=[r for r in records if r["_tipo_relatorio"]==tipo and r["_ano_consulta"]==year]
            summary.append({"tipo":tipo,"ano":year,"linhas":len(subset),"consultas_com_dados":sum(c["tipo"]==tipo and c["ano"]==year and c["linhas"]>0 for c in manifest["consultas"]),"falhas":sum(e["tipo"]==tipo and e["ano"]==year for e in manifest["falhas"])})
    save_csv(OUT/"resumo_cobertura.csv",summary)
    dest=OUT.parent/"stn_campo_grande_2022_2025.zip"
    with ZipFile(dest,"w",ZIP_DEFLATED) as z:
        for p in OUT.iterdir():
            if p.is_file():z.write(p,p.name)
    print("\nCOLETA FINALIZADA",json.dumps(summary,ensure_ascii=False,indent=2))
    print("Arquivo ZIP:",dest)
    print("Falhas:",len(manifest["falhas"]))
    return 2 if manifest["falhas"] else 0

if __name__=="__main__":
    sys.exit(main())
