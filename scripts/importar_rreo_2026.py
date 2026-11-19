#!/usr/bin/env python3
"""Atualiza somente RREO Anexo 01 de 2026 até o 5º bimestre, se a STN publicar.
Usa o mesmo contrato semântico e verificações de 2022-2025. Sem dados sintéticos.
"""
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec
import csv,json,os,sys,tempfile,datetime,shutil

ROOT=Path("/workspaces/bi-factory-seppe")
SOURCE=ROOT/"storage/reports/official_fiscal/rreo-2026-dashboard.csv"
AUDIT=ROOT/"artifacts/stn_rreo_raw_2022_2025"
PREVIOUS=ROOT/"scripts/importar_rreo_stn_2022_2025.py"
def write_csv(path,rows,fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=".stn-2026-",suffix=".csv",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8-sig",newline="") as f:
            w=csv.DictWriter(f,fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
            f.flush();os.fsync(f.fileno())
        if path.exists():
            backup=AUDIT/"backups"/("rreo-2026-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S")+".csv")
            backup.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,backup)
            print("Backup do arquivo anual:",backup)
        os.replace(name,path)
    finally:
        Path(name).unlink(missing_ok=True)
def main():
    if not PREVIOUS.is_file():raise RuntimeError("Importador RREO anterior não foi instalado")
    spec=spec_from_file_location("rreo_existing",PREVIOUS)
    engine=module_from_spec(spec);spec.loader.exec_module(engine)
    AUDIT.mkdir(parents=True,exist_ok=True)
    existing={}
    if SOURCE.is_file():
        with SOURCE.open(encoding="utf-8-sig",newline="") as f:
            reader=csv.DictReader(f)
            if not set(engine.HEAD).issubset(reader.fieldnames or []):
                raise RuntimeError("CSV 2026 existente apresenta contrato diferente; preservado")
            for row in reader:
                period=int(row["bimestre"])
                if int(row["ano"])!=2026 or period not in range(1,7) or period in existing:
                    raise RuntimeError("CSV 2026 existente contém período inesperado ou duplicado")
                existing[period]=row
    attempts=[]
    updated=False
    for bim in range(1,6):
        if bim in existing:
            print(f"2026 {bim}º: já importado; preservado")
            attempts.append({"bimestre":bim,"situacao":"preservado"})
            continue
        raw=AUDIT/f"rreo_anexo01_2026_{bim}.json"
        try:
            if raw.is_file():
                rows=json.loads(raw.read_text(encoding="utf-8"))
            else:
                rows=engine.fetch(2026,bim)
                if rows:raw.write_text(json.dumps(rows,ensure_ascii=False),encoding="utf-8")
            if not rows:
                attempts.append({"bimestre":bim,"situacao":"sem_registros_na_consulta"})
                print(f"2026 {bim}º: não disponibilizado pela consulta da STN")
                continue
            normalized=engine.extract(rows,2026,bim)
            existing[bim]=normalized
            updated=True
            attempts.append({"bimestre":bim,"situacao":"validado","registros_brutos":len(rows)})
            print(f"2026 {bim}º: validado ({len(rows)} linhas brutas)")
        except Exception as exc:
            attempts.append({"bimestre":bim,"situacao":"falha","motivo":str(exc)})
            print(f"2026 {bim}º: falha: {exc}",file=sys.stderr)
        finally:
            (AUDIT/"auditoria_2026.json").write_text(json.dumps({
                "municipio":"Campo Grande-MS","ibge":5002704,"ano":2026,
                "consultado_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "bimestres_consultados":attempts,
                "sexto_bimestre":"não encerrado em 19/11/2026"
            },ensure_ascii=False,indent=2),encoding="utf-8")
    if updated:
        write_csv(SOURCE,[existing[k] for k in sorted(existing)],engine.HEAD)
    elif not existing:
        print("STN não disponibilizou registros suficientes para gerar CSV 2026.")
    print("Bimestres de 2026 importados:",sorted(existing))
    return 2 if any(a["situacao"]=="falha" for a in attempts) else 0
if __name__=="__main__":
    try:sys.exit(main())
    except Exception as error:
        print("IMPORTAÇÃO 2026 BLOQUEADA:",error,file=sys.stderr);sys.exit(1)
