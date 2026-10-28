"""Local development-only product manager for the isolated visual editor.

Run: python3 prototypes/editor-visual/server.py --port 8510
Uses the existing information_product_registry, never exposes a public publishing API.
"""
from __future__ import annotations
import argparse
import csv
import json
import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, unquote
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.components import information_product_registry as registry

HERE = Path(__file__).resolve().parent
LAYOUTS = ROOT / "storage" / "information_products" / "layouts"
EXTRA = ROOT / "storage" / "information_products" / "metadata"
FIELDS = ("owner", "technical_owner", "audience", "project", "notes")
MAX_BODY = 2_000_000


def _id(value: str) -> str:
    return str(UUID(value))


def _read_json(path: Path, fallback):
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value):
    import os
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".tmp-", delete=False) as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        tmp = f.name
    os.replace(tmp, path)


def _enrich(product):
    return {**product, **_read_json(EXTRA / (product["id"] + ".json"), {})}


def _get_product(identifier):
    identifier = _id(identifier)
    return next((p for p in registry.load_registry() if p["id"] == identifier), None)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE), **kwargs)

    def _send(self, value, status=200):
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY:
            raise ValueError("Tamanho de requisição inválido")
        data = json.loads(self.rfile.read(length))
        if not isinstance(data, dict):
            raise ValueError("Objeto JSON esperado")
        return data

    def _route(self, method):
        path = unquote(urlsplit(self.path).path)
        if not path.startswith("/api/"):
            return False
        try:
            if path == "/api/fiscal" and method == "GET":
                source = ROOT / "storage/reports/official_fiscal/rreo-2025-dashboard.csv"
                if not source.exists():
                    self._send({"error": "Fonte fiscal oficial indisponível. Gere o relatório no BI Factory."}, 404)
                    return True
                with source.open(encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    rows = []
                    for row in reader:
                        converted = {}
                        for key, value in row.items():
                            if value is None or value == "":
                                converted[key] = None
                            elif key in ("ano", "exercicio", "bimestre"):
                                converted[key] = int(float(value))
                            else:
                                try:
                                    converted[key] = float(value)
                                except ValueError:
                                    converted[key] = value
                        rows.append(converted)
                        if len(rows) > 10000:
                            raise ValueError("Fonte fiscal excede o limite da prévia")
                self._send(rows)
                return True
            parts = path.strip("/").split("/")
            if parts == ["api", "products"]:
                if method == "GET":
                    self._send([_enrich(p) for p in registry.load_registry()])
                elif method == "POST":
                    data = self._body()
                    p = registry.create_product(
                        str(data.get("name", "")), str(data.get("type", "Painel")),
                        str(data.get("description", "")), str(data.get("refresh_policy", "Manual")),
                        str(data.get("destination", "")), None,
                        str(data.get("visibility", "Interno")),
                    )
                    self._save_extra(p["id"], data)
                    self._send(_enrich(p), 201)
                else:
                    self._send({"error": "Método inválido"}, 405)
                return True
            if len(parts) >= 3 and parts[:2] == ["api", "products"]:
                identifier = _id(parts[2])
                product = _get_product(identifier)
                if product is None:
                    self._send({"error": "Produto não encontrado"}, 404)
                    return True
                if len(parts) == 3:
                    if method == "GET":
                        self._send(_enrich(product))
                    elif method == "PATCH":
                        data = self._body()
                        permitted = {k: data[k] for k in ("name", "description", "refresh_policy",
                                     "destination", "visibility", "status") if k in data}
                        if permitted:
                            product = registry.update_product(identifier, **permitted)
                        self._save_extra(identifier, data)
                        self._send(_enrich(product))
                    else:
                        self._send({"error": "Método inválido"}, 405)
                    return True
                if len(parts) == 4 and parts[3] == "layout":
                    target = LAYOUTS / (identifier + ".json")
                    if method == "GET":
                        self._send(_read_json(target, None))
                    elif method == "PUT":
                        data = self._body()
                        if data.get("schema") != "bi-factory-editor-poc-v1" or not isinstance(data.get("layout"), list) or not isinstance(data.get("objects"), dict):
                            raise ValueError("Formato de layout inválido")
                        if len(data["layout"]) > 200 or len(data["objects"]) > 200:
                            raise ValueError("Máximo de 200 objetos")
                        _write_json(target, data)
                        registry.update_product(identifier)
                        self._send({"ok": True})
                    else:
                        self._send({"error": "Método inválido"}, 405)
                    return True
            self._send({"error": "Rota desconhecida"}, 404)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self._send({"error": str(exc)}, 400)
        except OSError:
            self._send({"error": "Erro de armazenamento"}, 500)
        return True

    def _save_extra(self, identifier, data):
        path = EXTRA / (identifier + ".json")
        current = _read_json(path, {})
        current.update({k: str(data[k])[:500] for k in FIELDS if k in data})
        _write_json(path, current)

    def do_GET(self):
        if self._route("GET"):
            return
        if urlsplit(self.path).path == "/":
            self.path = "/products.html"
        return super().do_GET()

    def do_POST(self):
        self._route("POST")

    def do_PATCH(self):
        self._route("PATCH")

    def do_PUT(self):
        self._route("PUT")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8510)
    args = parser.parse_args()
    print(f"Editor de produtos: http://localhost:{args.port}/")
    print("ATENÇÃO: servidor de desenvolvimento sem autenticação; mantenha a porta PRIVADA.")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
