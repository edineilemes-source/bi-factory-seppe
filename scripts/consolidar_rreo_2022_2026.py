#!/usr/bin/env python3
"""Consolida séries RREO anuais já normalizadas no padrão do dashboard de 2025.
Não transforma JSON bruto SICONFI sem contrato semântico validado.
Não sobrescreve fontes. Não insere zeros em períodos sem dados.
"""
import csv,sys,os,tempfile,shutil,datetime
from pathlib import Path
ROOT=Path("/workspaces/bi-factory-seppe")
DIR=ROOT/"storage/reports/official_fiscal"
REQUIRED={"ano","bimestre","receita_realizada_acumulada","despesa_empenhada_acumulada","despesa_liquidada_acumulada","despesa_paga_acumulada"}
TARGET=DIR/"rreo-2022-2026-dashboard.csv"

def main():
    rows=[];cols=[];periods=set()
    for year in range(2022,2027):
        source=DIR/f"rreo-{year}-dashboard.csv"
        if not source.is_file():
            print(f"{year}: fonte normalizada ausente, nenhum valor presumido")
            continue
        with source.open(encoding="utf-8-sig",newline="") as stream:
            reader=csv.DictReader(stream)
            fields=set(reader.fieldnames or [])
            if not REQUIRED.issubset(fields):
                raise ValueError(f"{source.name}: colunas obrigatórias ausentes: {sorted(REQUIRED-fields)}")
            for key in reader.fieldnames or []:
                if key not in cols:cols.append(key)
            for row in reader:
                y,b=int(float(row["ano"])),int(float(row["bimestre"]))
                if y!=year or not 1<=b<=6:raise ValueError(f"{source.name}: ano/bimestre fora do domínio: {y}/{b}")
                if (y,b) in periods:raise ValueError(f"{source.name}: bimestre duplicado {y}/{b}")
                for metric in REQUIRED-{"ano","bimestre"}:
                    if row[metric] in ("",None):raise ValueError(f"{source.name}: medida obrigatória vazia: {metric} no {b}º")
                    float(row[metric])
                periods.add((y,b));rows.append(row)
        print(f"{year}: {sum(y==year for y,_ in periods)} bimestres validados")
    if not rows:
        print("Nenhuma fonte anual normalizada encontrada; base histórica não foi gerada.")
        return 2
    rows.sort(key=lambda r:(int(float(r["ano"])),int(float(r["bimestre"]))))
    DIR.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".rreo-2022-2025-",suffix=".csv",dir=DIR)
    try:
        with os.fdopen(fd,"w",encoding="utf-8-sig",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=cols)
            writer.writeheader()
            writer.writerows(rows)
            stream.flush();os.fsync(stream.fileno())
        if TARGET.exists():
            backup=ROOT/'artifacts'/'stn_rreo_raw_2022_2025'/'backups'/('rreo-consolidado-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.csv')
            backup.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(TARGET,backup)
            print('Backup da base consolidada:',backup)
        os.replace(tmp,TARGET)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    print(f"Base consolidada: {TARGET}; {len(periods)} de 30 períodos previstos")
    print("OBS: RREO é acumulado. Não somar bimestres. RGF exige modelo quadrimestral próprio.")
    return 0
if __name__=="__main__":
    try:sys.exit(main())
    except Exception as e:
        print("CONSOLIDAÇÃO BLOQUEADA:",e,file=sys.stderr);sys.exit(1)
