#!/usr/bin/env python3
"""BI Factory — laboratório experimental 8507, totalmente isolado da 8506.

Usa SOMENTE a API fiscal já existente 8505 como fonte, sem alterar seus dados.
Salva o rascunho do laboratório em storage/labs/echarts-axes-8507/.
Por segurança, usa 127.0.0.1 e deve ser encaminhado como porta PRIVATE.
"""
from __future__ import annotations
import argparse
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
MAX_BYTES=1_500_000

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(HERE),**kwargs)

    def json(self,data,status=200):
        payload=json.dumps(data,ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Content-Length",str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        route=urlsplit(self.path).path
        if route=="/api/fiscal":
            try:
                with urllib.request.urlopen(UPSTREAM,timeout=15) as response:
                    rows=json.load(response)
                if not isinstance(rows,list):
                    raise ValueError("API fiscal não retornou uma lista")
                if len(rows)>10000:
                    raise ValueError("Quantidade inesperada de linhas")
                return self.json(rows)
            except (ValueError,urllib.error.URLError,TimeoutError) as exc:
                return self.json({"error":"Fonte fiscal 8505 indisponível: "+str(exc)},503)
        if route=="/api/state":
            if STATE.exists():
                try:return self.json(json.loads(STATE.read_text(encoding="utf-8")))
                except (json.JSONDecodeError,OSError) as exc:
                    return self.json({"error":"Rascunho inválido: "+str(exc)},500)
            return self.json({"version":1,"objects":[],"filters":{},"selected":null})
        if route=="/api/health":
            return self.json({"status":"ok","lab":"echarts-axes","port":8507,
              "upstream":8505,"storage_isolated":True})
        if route=="/":
            self.path="/index.html"
        elif route.startswith("/api/"):
            return self.json({"error":"Rota inexistente"},404)
        return super().do_GET()

    def do_POST(self):
        if urlsplit(self.path).path!="/api/state":
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
                    "chart","text","image","filter","measure_filter"):
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
