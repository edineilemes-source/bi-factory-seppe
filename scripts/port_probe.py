#!/usr/bin/env python3
"""Diagnóstico isolado de requisições Codespaces -> navegador; somente biblioteca padrão."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone
import argparse
import json
import secrets

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path)
        query = parse_qs(path.query)
        marker = query.get("id", ["sem-id"])[0][:100]
        timestamp = datetime.now(timezone.utc).isoformat()
        print(json.dumps({"time":timestamp,"marker":marker,"method":"GET","path":path.path,"host":self.headers.get("Host"),"forwarded_host":self.headers.get("X-Forwarded-Host"),"forwarded_proto":self.headers.get("X-Forwarded-Proto"),"user_agent":self.headers.get("User-Agent","")[:160]},ensure_ascii=False),flush=True)
        if path.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if path.path not in ("/", "/probe", "/health"):
            self.send_error(404,"Rota inexistente no servidor de teste")
            return
        payload = {"ok":True,"id":marker,"time":timestamp,"path":path.path,"server":"seppe-port-probe"}
        if path.path == "/probe":
            body=json.dumps(payload,ensure_ascii=False,indent=2).encode()
            mime="application/json; charset=utf-8"
        else:
            body=("<!doctype html><html lang='pt-BR'><meta charset='utf-8'><title>SEPPE Port Probe</title>"
                  "<body><h2>SEPPE Port Probe: servidor alcançado</h2><pre id='result'></pre>"
                  "<script>document.getElementById('result').textContent="+json.dumps(json.dumps(payload,ensure_ascii=False))+ 
                  ";</script></body></html>").encode()
            mime="text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type",mime)
        self.send_header("Cache-Control","no-store, max-age=0")
        self.send_header("X-SEPPE-Probe-ID",marker)
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--port",type=int,default=8765)
    args=p.parse_args()
    print(f"SEPPE probe iniciado em 0.0.0.0:{args.port}",flush=True)
    ThreadingHTTPServer(("0.0.0.0",args.port),Handler).serve_forever()
