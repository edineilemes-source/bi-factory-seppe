#!/usr/bin/env python3
"""BI Factory — laboratório experimental 8507, totalmente isolado da 8506.

Usa SOMENTE a API fiscal já existente 8505 como fonte, sem alterar seus dados.
Salva o rascunho do laboratório em storage/labs/echarts-axes-8507/.
Por segurança, usa 127.0.0.1 e deve ser encaminhado como porta PRIVATE.
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/"experiments/echarts-axes-8507"
WORKSPACE=ROOT/"storage/labs/echarts-axes-8507"
STATE=WORKSPACE/"state.json"
UPSTREAM="http://127.0.0.1:8505/api/fiscal"
HISTORICAL=ROOT/"storage/reports/official_fiscal/rreo-2022-2026-dashboard.csv"
LEGACY=ROOT/"storage/reports/official_fiscal/rreo-2025-dashboard.csv"
REQUIRED={
 "ano","bimestre","receita_realizada_acumulada",
 "despesa_empenhada_acumulada","despesa_liquidada_acumulada",
 "despesa_paga_acumulada","resultado_orcamentario_formal",
 "margem_receita_menos_liquidada","liquidada_nao_paga",
}
MAX_BYTES=8_000_000

def load_local_fiscal():
    """Read-only fallback; never generates numbers and never modifies the source."""
    source=HISTORICAL if HISTORICAL.is_file() else LEGACY
    if not source.is_file():
        raise FileNotFoundError("CSV histórico e CSV original 2025 não encontrados")
    with source.open(encoding="utf-8-sig",newline="") as handle:
        reader=csv.DictReader(handle)
        columns=set(reader.fieldnames or [])
        if not REQUIRED.issubset(columns):
            raise ValueError("CSV fiscal sem colunas obrigatórias: "+
                             ", ".join(sorted(REQUIRED-columns)))
        rows=list(reader)
    if not rows:
        raise ValueError("CSV fiscal vazio")
    unique=set()
    for row in rows:
        try:
            year=int(row["ano"]);period=int(row["bimestre"])
            if year<2022 or year>2026 or period<1 or period>6:
                raise ValueError("Período fora do intervalo 2022–2026")
            for key in REQUIRED-{"ano","bimestre"}:
                if row[key] in ("",None,"None"):
                    raise ValueError("Medida obrigatória ausente: "+key)
                float(row[key])
        except (ValueError,TypeError,KeyError) as exc:
            raise ValueError("CSV fiscal contém registro inválido") from exc
        if (year,period) in unique:
            raise ValueError("Ano/bimestre duplicado no CSV fiscal")
        unique.add((year,period))
        row["ano"]=year;row["bimestre"]=period
    rows.sort(key=lambda r:(r["ano"],r["bimestre"]))
    return rows,source

def load_fiscal():
    """Prefer API 8505; fallback to the already homologated local CSV."""
    upstream_error=None
    try:
        with urllib.request.urlopen(UPSTREAM,timeout=3) as response:
            rows=json.load(response)
        if not isinstance(rows,list) or not 0<len(rows)<=10000:
            raise ValueError("API fiscal 8505 retornou formato inválido")
        return rows,"api-8505"
    except (ValueError,urllib.error.URLError,TimeoutError,OSError) as exc:
        upstream_error=str(exc)
    rows,source=load_local_fiscal()
    return rows,"csv-local:"+source.name

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(HERE),**kwargs)

    def end_headers(self):
        # Arquivos de desenvolvimento da 8507 devem ser sempre revalidados.
        # Evita que o navegador mantenha um app.js antigo usando /api/state.
        self.send_header("Cache-Control","no-store, max-age=0")
        self.send_header("Pragma","no-cache")
        self.send_header("Expires","0")
        return super().end_headers()

    def json(self,data,status=200):
        payload=json.dumps(data,ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Content-Length",str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        route=urlsplit(self.path).path
        if route=="/api/fiscal":
            try:
                rows,source=load_fiscal()
                self._fiscal_source=source
                return self.json(rows)
            except (ValueError,OSError,urllib.error.URLError,TimeoutError) as exc:
                return self.json({"error":"Fontes fiscais indisponíveis: "+str(exc)},503)
        if route=="/api/source":
            try:
                rows,source=load_fiscal()
                return self.json({"source":source,"periodos":len(rows),
                                  "exercicios":sorted({int(r["ano"]) for r in rows})})
            except (ValueError,OSError,urllib.error.URLError,TimeoutError) as exc:
                return self.json({"error":str(exc)},503)
        if route in ("/api/state","/lab/draft"):
            if STATE.exists():
                try:return self.json(json.loads(STATE.read_text(encoding="utf-8")))
                except (json.JSONDecodeError,OSError) as exc:
                    return self.json({"error":"Rascunho inválido: "+str(exc)},500)
            return self.json({"version":1,"objects":[],"filters":{},"selected":None})
        if route=="/api/health":
            return self.json({"status":"ok","lab":"echarts-axes","port":8507,
              "upstream":8505,"fallback_csv":True,"storage_isolated":True,
              "build":"lab8507-click-editar-echarts-20261123-r9"})
        if route=="/":
            self.path="/index.html"
        elif route.startswith("/api/"):
            return self.json({"error":"Rota inexistente"},404)
        return super().do_GET()

    def do_POST(self):
        if urlsplit(self.path).path not in ("/api/state","/lab/draft"):
            return self.json({"error":"Rota inexistente"},404)
        try:
            size=int(self.headers.get("Content-Length","0"))
            if size<=0 or size>MAX_BYTES:
                return self.json({"error":"Rascunho grande ou vazio"},413)
            payload=json.loads(self.rfile.read(size))
            if not isinstance(payload,dict) or payload.get("version")!=1:
                return self.json({"error":"Versão de rascunho incompatível"},400)
            objects=payload.get("objects")
            if not isinstance(objects,list) or len(objects)>100:
                return self.json({"error":"Lista de objetos inválida"},400)
            for obj in objects:
                if not isinstance(obj,dict) or obj.get("type") not in (
                    "chart","text","title","image","filter","filter_panel","measure_filter",
                    "rectangle","square","diamond","ellipse","arrow","line"):
                    return self.json({"error":"Tipo de objeto não permitido"},400)
                if not isinstance(obj.get("id"),str) or len(obj["id"])>100:
                    return self.json({"error":"ID inválido"},400)
            if not isinstance(payload.get("filters",{}),dict):
                return self.json({"error":"Filtros inválidos"},400)
            WORKSPACE.mkdir(parents=True,exist_ok=True)
            if STATE.exists():
                backup=WORKSPACE/"state.previous.json"
                backup.write_bytes(STATE.read_bytes())
            fd,pending=tempfile.mkstemp(prefix=".axes-",dir=WORKSPACE)
            try:
                with os.fdopen(fd,"wb") as dest:
                    dest.write(json.dumps(payload,ensure_ascii=False,indent=2).encode("utf-8"))
                    dest.flush();os.fsync(dest.fileno())
                os.replace(pending,STATE)
            finally:
                if os.path.exists(pending):os.unlink(pending)
            return self.json({"ok":True,"objects":len(objects)})
        except (ValueError,TypeError,json.JSONDecodeError) as exc:
            return self.json({"error":"Requisição inválida: "+str(exc)},400)
        except OSError as exc:
            return self.json({"error":"Falha de armazenamento: "+str(exc)},500)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8507)
    parser.add_argument("--host",default="127.0.0.1")
    args=parser.parse_args()
    if not HERE.is_dir():
        raise SystemExit("Laboratório ainda não instalado: "+str(HERE))
    print(f"BI Factory Laboratório ECharts: http://{args.host}:{args.port}/",flush=True)
    print("8506 permanece separado. Mantenha a porta 8507 PRIVATE.",flush=True)
    ThreadingHTTPServer((args.host,args.port),Handler).serve_forever()
