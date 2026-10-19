"""Read-only web server for the SEPPE fiscal situation room.

Run: python scripts/serve_sala_situacao.py --port 8503
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "web" / "sala_situacao" / "index.html"
STUDIO = ROOT / "web" / "sala_situacao" / "studio.html"
DATA = ROOT / "storage" / "reports" / "official_fiscal" / "rreo-2025-dashboard.json"
PUBLISHED = ROOT / "storage" / "dashboard_projects" / "published.json"
PRODUCTS = ROOT / "storage" / "dashboard_projects" / "products"
REGISTRY = ROOT / "storage" / "information_products" / "registry.json"
FOLDERS = ROOT / "storage" / "information_products" / "folders.json"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlsplit(self.path)
        route = url.path
        if route in ("/", "/index.html"):
            path, mime = PAGE, "text/html; charset=utf-8"
        elif route in ("/studio", "/studio.html"):
            path, mime = STUDIO, "text/html; charset=utf-8"
        elif route == "/api/fiscal":
            path, mime = DATA, "application/json; charset=utf-8"
        elif route == "/api/dashboard-folders":
            try:
                if FOLDERS.is_file():
                    folders = json.loads(FOLDERS.read_text(encoding="utf-8"))
                else:
                    folders = [{"id": "default-" + str(i), "name": name, "parent_id": None, "order": i}
                               for i, name in enumerate(("Finanças Públicas", "Saúde", "Educação", "Planejamento"))]
                self._send(200, json.dumps(folders, ensure_ascii=False).encode("utf-8"), "application/json")
            except (OSError, ValueError) as exc:
                self._send(500, json.dumps({"error": str(exc)}).encode("utf-8"), "application/json")
            return
        elif route == "/api/dashboard-products":
            products = []
            if PUBLISHED.is_file():
                try:
                    legacy = json.loads(PUBLISHED.read_text(encoding="utf-8"))
                    products.append({"id": "legacy", "name": legacy.get("name", "Sala de Gestão"), "folder_id": None, "visibility": "Interno"})
                except (OSError, ValueError):
                    pass
            if REGISTRY.is_file():
                try:
                    for product in json.loads(REGISTRY.read_text(encoding="utf-8")):
                        if product.get("type") in ("Painel", "Portal") and (PRODUCTS / (product["id"] + ".json")).is_file():
                            products.append({"id": product["id"], "name": product["name"], "code": product.get("code"),
                                             "folder_id": product.get("folder_id"), "visibility": product.get("visibility", "Interno"),
                                             "type": product.get("type")})
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            self._send(200, json.dumps(products, ensure_ascii=False).encode("utf-8"), "application/json")
            return
        elif route == "/api/dashboard-project":
            identifier = parse_qs(url.query).get("product", ["legacy"])[0]
            if identifier == "legacy":
                path = PUBLISHED
            else:
                try:
                    identifier = str(UUID(identifier))
                except ValueError:
                    self._send(400, b'{"error":"invalid_product_id"}', "application/json")
                    return
                path = PRODUCTS / (identifier + ".json")
            mime = "application/json; charset=utf-8"
        elif route == "/health":
            self._send(200, b'{"status":"ok"}', "application/json")
            return
        else:
            self._send(404, b'{"error":"not_found"}', "application/json")
            return
        if not path.is_file():
            self._send(503, json.dumps({"error": "dataset_unavailable" if route == "/api/fiscal" else "project_not_published" if route == "/api/dashboard-project" else "page_unavailable"}).encode(), "application/json")
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
