#!/usr/bin/env python3
"""ETL oficial RREO Anexo 01, Campo Grande/MS, 2022-2025.
Baixa JSON com proveniência, seleciona contas totais e colunas acumuladas,
rejeita ambiguidade e não fabrica zero. Não sobrescreve arquivos.
"""
from pathlib import Path
from decimal import Decimal,InvalidOperation
import urllib.request,urllib.parse,urllib.error,json,csv,time,datetime,os,tempfile,sys

ROOT=Path("/workspaces/bi-factory-seppe")
BASE="https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo"
DEST=ROOT/"storage/reports/official_fiscal"
RAW=ROOT/"artifacts/stn_rreo_raw_2022_2025"
IBGE=5002704
COLS={
 "receita_realizada_acumulada":("TotalReceitas","Até o Bimestre (c)"),
 "despesa_empenhada_acumulada":("TotalDespesas","DESPESAS EMPENHADAS ATÉ O BIMESTRE (f)"),
 "despesa_liquidada_acumulada":("TotalDespesas","DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)"),
 "despesa_paga_acumulada":("TotalDespesas","DESPESAS PAGAS ATÉ O BIMESTRE (j)"),
}
HEAD=["ano","bimestre",*COLS,"resultado_orcamentario_formal","margem_receita_menos_liquidada","liquidada_nao_paga"]
last=0
def fetch(year,bim):
    global last
    query={"an_exercicio":year,"nr_periodo":bim,"co_tipo_demonstrativo":"RREO","no_anexo":"RREO-Anexo 01","id_ente":IBGE,"limit":5000}
    rows=[];offset=0
    while True:
        query["offset"]=offset
        wait=1.1-(time.monotonic()-last)
        if wait>0:time.sleep(wait)
        last=time.monotonic()
        url=BASE+"?"+urllib.parse.urlencode(query)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"BI-Factory-SEPPE/1.0"}),timeout=50) as response:
                    data=json.load(response)
                break
            except (TimeoutError,urllib.error.URLError,ValueError) as e:
                if attempt==3:raise RuntimeError(f"Falha API {year}/{bim}: {e}")
                time.sleep(2**attempt)
        items=data.get("items")
        if not isinstance(items,list):raise ValueError(f"Resposta sem items: {year}/{bim}")
        rows.extend(items)
        if not data.get("hasMore"):return rows
        if not items:raise ValueError("Paginação vazia")
        offset+=len(items)

def to_decimal(value):
    if isinstance(value,(int,float)):return Decimal(str(value))
    value=str(value).strip()
    if "," in value:
        value=value.replace(".","").replace(",",".")
    return Decimal(value)

def extract(rows,year,bim):
    values={}
    for field,(account,column) in COLS.items():
        candidates=[]
        for row in rows:
            if str(row.get("cod_conta","")).strip()!=account:continue
            if str(row.get("coluna","")).strip().casefold()!=column.casefold():continue
            try:candidates.append(to_decimal(row["valor"]))
            except (KeyError,InvalidOperation):pass
        unique=set(candidates)
        if len(unique)!=1:
            raise ValueError(f"{year}/{bim}: {field} deve ter um valor inequívoco; encontrados {len(candidates)} registros e {len(unique)} valores distintos")
        values[field]=next(iter(unique))
    receipt=values["receita_realizada_acumulada"]
    empenhada=values["despesa_empenhada_acumulada"]
    liquidada=values["despesa_liquidada_acumulada"]
    paga=values["despesa_paga_acumulada"]
    return {"ano":year,"bimestre":bim,**{k:str(v) for k,v in values.items()},
            "resultado_orcamentario_formal":str(receipt-empenhada),
            "margem_receita_menos_liquidada":str(receipt-liquidada),
            "liquidada_nao_paga":str(liquidada-paga)}

def write_once(path,rows,header=None):
    if path.exists():return
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".stn-",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8-sig",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=header or list(rows[0]))
            writer.writeheader();writer.writerows(rows)
            stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def main():
    RAW.mkdir(parents=True,exist_ok=True)
    outcome={"município":"Campo Grande-MS","ibge":IBGE,"origem":BASE,"data_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"resultados":[]}
    failures=0
    for year in range(2022,2026):
        source=DEST/f"rreo-{year}-dashboard.csv"
        if source.exists():
            print(f"{year}: fonte anual já existente; não sobrescrita",flush=True)
            continue
        yearrows=[]
        for bim in range(1,7):
            path=RAW/f"rreo_anexo01_{year}_{bim}.json"
            try:
                if path.exists():rows=json.loads(path.read_text(encoding="utf-8"))
                else:
                    rows=fetch(year,bim)
                    if rows:path.write_text(json.dumps(rows,ensure_ascii=False),encoding="utf-8")
                if not rows:raise ValueError("STN retornou zero registros")
                item=extract(rows,year,bim)
                yearrows.append(item);outcome["resultados"].append({"ano":year,"bimestre":bim,"estado":"validado","registros_brutos":len(rows)})
                print(f"{year} {bim}º: OK ({len(rows)} registros brutos)",flush=True)
            except Exception as e:
                failures+=1
                outcome["resultados"].append({"ano":year,"bimestre":bim,"estado":"falha","motivo":str(e)})
                print(f"{year} {bim}º: FALHA {e}",file=sys.stderr,flush=True)
            (RAW/"auditoria.json").write_text(json.dumps(outcome,ensure_ascii=False,indent=2),encoding="utf-8")
        if yearrows:
            write_once(source,yearrows,HEAD)
            print(f"{year}: {len(yearrows)} bimestres salvos (ausentes permanecem ausentes)",flush=True)
    print("Dados brutos e auditoria:",RAW)
    return 2 if failures else 0
if __name__=="__main__":
    sys.exit(main())
