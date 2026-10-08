"""Read-only web server for the SEPPE fiscal situation room.

Run: python scripts/serve_sala_situacao.py --port 8503
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "web" / "sala_situacao" / "index.html"
DATA = ROOT / "storage" / "reports" / "official_fiscal" / "rreo-2025-dashboard.json"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = self.path.split("?", 1)[0]
        if route in ("/", "/index.html"):
            path, mime = PAGE, "text/html; charset=utf-8"
        elif route == "/api/fiscal":
            path, mime = DATA, "application/json; charset=utf-8"
        elif route == "/health":
            self._send(200, b'{"status":"ok"}', "application/json")
            return
        else:
            self._send(404, b'{"error":"not_found"}', "application/json")
            return
        if not path.is_file():
            self._send(503, json.dumps({"error": "dataset_unavailable" if route == "/api/fiscal" else "page_unavailable"}).encode(), "application/json")
            return
        self._send(200, path.read_bytes(), mime)

    def _send(self, code, data, mime):
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; font-src 'self'")
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8503)
    args = parser.parse_args()
    print(f"Sala de Situação SEPPE em http://0.0.0.0:{args.port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()
