"""Read-only bridge for the first React BI Factory migration slice.

Run: python -u scripts/serve_bi_factory_api.py --port 8505
Does not mutate project data, publications or the Streamlit installation.
"""
from __future__ import annotations

import argparse
import csv
import json
from bi_factory_catalog import OPERATIONS, read as catalog_read, COMPONENTS as SHARED_COMPONENTS
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "storage/information_products/registry.json"
FOLDERS = ROOT / "storage/information_products/folders.json"
RREO = ROOT / "storage/official/siconfi/rreo"
PUBLISHED = ROOT / "storage/dashboard_projects/published.json"
PRODUCT_FILES = ROOT / "storage/dashboard_projects/products"
FISCAL_REPORT = ROOT / "storage/reports/official_fiscal/rreo-2025-dashboard.json"
FISCAL_STUDIO_CSV = ROOT / "storage/reports/official_fiscal/rreo-2025-dashboard.csv"


def load_list(path: Path) -> list:
    if not path.is_file():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"Esperada lista em {path.name}")
    return value


def all_products() -> list[dict]:
    products = load_list(REGISTRY)
    known = {str(item.get("id")) for item in products}
    if PUBLISHED.is_file():
        legacy = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        products.append({"id": "legacy-published", "name": legacy.get("name", "Painel legado publicado"),
                         "type": "Painel", "code": "LEGADO", "folder_id": None,
                         "status": "Publicado", "source": "published.json"})
    if PRODUCT_FILES.is_dir():
        for path in sorted(PRODUCT_FILES.glob("*.json")):
            if path.stem not in known:
                try:
                    doc = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                products.append({"id": path.stem, "name": doc.get("name", path.stem),
                                 "type": "Painel", "code": "SEM CADASTRO", "folder_id": None,
                                 "status": "Projeto recuperado", "source": "products/" + path.name})
    return products


def product_components() -> dict:
    result = {}
    paths = [(path.stem, path) for path in sorted(PRODUCT_FILES.glob("*.json"))] if PRODUCT_FILES.is_dir() else []
    if PUBLISHED.is_file():
        paths.append(("legacy-published", PUBLISHED))
    for identifier, path in paths:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            components = []
            for page_index, page in enumerate(doc.get("pages", [])):
                for index, item in enumerate(page.get("components", [])):
                    if not isinstance(item, dict):
                        continue
                    components.append({
                        "id": str(item.get("id") or f"{page_index}-{index}"),
                        "name": str(item.get("title") or item.get("name") or item.get("label") or f"Componente {index + 1}"),
                        "type": str(item.get("type") or item.get("kind") or "Objeto"),
                        "page": str(page.get("name") or page.get("title") or f"Página {page_index + 1}"),
                        "library_component_id": item.get("library_component_id"),
                        "library_version": item.get("library_version"),
                    })
            result[identifier] = components
        except (OSError, ValueError, TypeError):
            result[identifier] = []
    return result


def inventory() -> dict:
    registered = load_list(REGISTRY)
    published = json.loads(PUBLISHED.read_text(encoding="utf-8")) if PUBLISHED.is_file() else {}
    project_files = sorted(PRODUCT_FILES.glob("*.json")) if PRODUCT_FILES.is_dir() else []
    items = []
    for path in project_files:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            count = sum(len(page.get("components", [])) for page in doc.get("pages", []))
            items.append({"id": path.stem, "name": doc.get("name", path.stem), "components": count,
                          "registered": any(p.get("id") == path.stem for p in registered)})
        except (OSError, ValueError, TypeError):
            items.append({"id": path.stem, "error": "Arquivo inválido"})
    return {"registered_products": len(registered), "saved_dashboard_files": len(project_files),
            "saved_dashboards": items, "legacy_published": bool(published),
            "legacy_components": sum(len(page.get("components", [])) for page in published.get("pages", [])),
            "note": "Objetos cadastrados, componentes e painéis publicados são conjuntos distintos."}


def overview() -> dict:
    return {
        "project": {"id": "pmcg-financas-publicas", "name": "PMCG — Finanças Públicas", "years": [2022, 2023, 2024, 2025, 2026]},
        "products": all_products(),
        "inventory": inventory(),
        "components_by_product": product_components(),
        "shared_components": catalog_read(SHARED_COMPONENTS),
        "free_canvases": {path.stem: json.loads(path.read_text(encoding="utf-8")).get("free_canvas") for path in PRODUCT_FILES.glob("*.json") if path.is_file()} if PRODUCT_FILES.is_dir() else {},
        "product_canvases": {path.stem: json.loads(path.read_text(encoding="utf-8")).get("studio_items", []) for path in PRODUCT_FILES.glob("*.json")} if PRODUCT_FILES.is_dir() else {},
        "folders": load_list(FOLDERS),
        "fiscal": {"source": "STN/SICONFI", "years": [
            {"year": year, "files": len(list((RREO / str(year)).rglob("*.json")))}
            for year in range(2022, 2027)
        ]},
    }


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        route = self.path.split("?")[0]
        operation = route.removeprefix("/api/create/")
        if not route.startswith("/api/create/") or operation not in OPERATIONS:
            self.send_error(404, "Operação não encontrada")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 65536:
                raise ValueError("Tamanho de requisição inválido")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Corpo inválido")
            result = OPERATIONS[operation](data)
            payload = json.dumps({"ok": True, "item": result}, ensure_ascii=False).encode("utf-8")
            status = 201
        except (ValueError, TypeError, OSError, KeyError) as error:
            payload = json.dumps({"error": str(error)}, ensure_ascii=False).encode("utf-8")
            status = 400
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        route = self.path.split("?")[0]
        if route not in ("/api/overview", "/api/fiscal-preview", "/api/studio-fiscal"):
            self.send_error(404, "Rota não encontrada")
            return
        try:
            if route == "/api/studio-fiscal":
                if not FISCAL_STUDIO_CSV.is_file():
                    result = {"rows": [], "error": "Dataset fiscal CSV não encontrado"}
                else:
                    with FISCAL_STUDIO_CSV.open(encoding="utf-8-sig", newline="") as source:
                        result = {"rows": list(csv.DictReader(source))}
            elif route == "/api/fiscal-preview":
                rows = load_list(FISCAL_REPORT)
                result = {"source": "STN/SICONFI · RREO Anexo 01", "rows": rows, "available": FISCAL_REPORT.is_file()}
            else:
                result = overview()
            payload = json.dumps(result, ensure_ascii=False).encode("utf-8")
        except (OSError, ValueError, TypeError) as error:
            payload = json.dumps({"error": str(error)}, ensure_ascii=False).encode("utf-8")
            self.send_response(500)
        else:
            self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8505)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"BI Factory API em http://0.0.0.0:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
