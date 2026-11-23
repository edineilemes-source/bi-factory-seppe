"""Read-only bridge for the first React BI Factory migration slice.

Run: python -u scripts/serve_bi_factory_api.py --port 8505
Does not mutate project data, publications or the Streamlit installation.
"""
from __future__ import annotations

import argparse
import csv
import json
import bi_factory_analytics_adapter as analytics
import bi_factory_projects as projects
from bi_factory_catalog import OPERATIONS, read as catalog_read, COMPONENTS as SHARED_COMPONENTS
from http.server import ThreadingHTTPServer
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "prototypes" / "editor-visual"))
import server as visual_editor_server

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "storage/information_products/registry.json"
FOLDERS = ROOT / "storage/information_products/folders.json"
RREO = ROOT / "storage/official/siconfi/rreo"
PUBLISHED = ROOT / "storage/dashboard_projects/published.json"
PRODUCT_FILES = ROOT / "storage/dashboard_projects/products"
FISCAL_REPORT = ROOT / "storage/reports/official_fiscal/rreo-2025-dashboard.json"
FISCAL_STUDIO_CSV = ROOT / "storage/reports/official_fiscal/rreo-2025-dashboard.csv"


def fiscal_catalog() -> dict:
    """Metadados de seleção sem declarar períodos não importados como disponíveis."""
    historic = ROOT / "storage/reports/official_fiscal/rreo-2022-2026-dashboard.csv"
    previous = ROOT / "storage/reports/official_fiscal/rreo-2022-2025-dashboard.csv"
    if not historic.is_file() and previous.is_file():
        historic = previous
    legacy = FISCAL_STUDIO_CSV
    file = historic if historic.is_file() else legacy
    periods = set()
    if file.is_file():
        with file.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                try:
                    year = int(float(row.get("ano") or row.get("exercicio") or 0))
                    period = int(float(row.get("bimestre") or 0))
                except (ValueError, TypeError):
                    continue
                if year in range(2022, 2027) and period in range(1, 7):
                    periods.add((year, period))
    measures = [
        {"label": title, "field": field} for title, field in [
            ("Receita realizada", "receita_realizada_acumulada"),
            ("Despesa empenhada", "despesa_empenhada_acumulada"),
            ("Despesa liquidada", "despesa_liquidada_acumulada"),
            ("Despesa paga", "despesa_paga_acumulada"),
            ("Resultado orçamentário formal", "resultado_orcamentario_formal"),
            ("Margem receita × liquidada", "margem_receita_menos_liquidada"),
            ("Liquidada não paga", "liquidada_nao_paga"),
        ]
    ]
    return {
        "name": "RREO — Execução Orçamentária (STN/SICONFI)",
        "years": [2022, 2023, 2024, 2025, 2026], "bimesters": [1,2,3,4,5,6],
        "dimensions": ["ano", "bimestre"], "measures": measures,
        "available": [{"ano": y, "bimestre": b} for y,b in sorted(periods)],
        "source": historic.name if historic.is_file() else (
            "rreo-2025-dashboard.csv" if legacy.is_file() else None),
        "status": "parcial" if len(periods)<30 else "completo",
        "note": "RREO: bimestres acumulados. RGF: quadrimestres em base separada. Períodos não importados não possuem valores."
    }


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


class Handler(visual_editor_server.Handler):
    def _projects_dispatch(self, method):
        path = self.path.split("?")[0]
        if path != "/api/projects" and not path.startswith("/api/projects/"):
            return False
        try:
            parts = path.strip("/").split("/")
            if method == "GET":
                if len(parts) == 2:
                    result = {"projects": projects.projects()}
                elif len(parts) == 3:
                    result = projects.get(parts[2])
                elif len(parts) == 4 and parts[3] == "knowledge":
                    result = projects.summary(parts[2])
                else:
                    self._analytics_send({"error": "Rota não encontrada"}, 404)
                    return True
            elif method in ("POST", "PATCH"):
                size = int(self.headers.get("Content-Length") or 0)
                if size < 1 or size > 17 * 1024 * 1024:
                    raise ValueError("Tamanho de requisição inválido")
                data = json.loads(self.rfile.read(size))
                if method == "POST" and len(parts) == 2:
                    result = projects.create(data)
                elif method == "PATCH" and len(parts) == 3:
                    result = projects.update(parts[2], data)
                elif method == "POST" and len(parts) == 4 and parts[3] == "research":
                    if data.get("project_id") != parts[2]:
                        raise ValueError("Projeto inconsistente")
                    result = projects.research(data)
                elif method == "POST" and len(parts) == 4 and parts[3] == "documents":
                    if data.get("project_id") != parts[2]:
                        raise ValueError("Projeto inconsistente")
                    result = projects.upload(data)
                else:
                    self._analytics_send({"error": "Operação não encontrada"}, 404)
                    return True
            else:
                self._analytics_send({"error": "Método não permitido"}, 405)
                return True
            self._analytics_send(result, 201 if method == "POST" else 200)
        except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as error:
            self._analytics_send({"error": str(error)}, 400)
        except Exception:
            import logging
            logging.exception("Falha no módulo de projetos")
            self._analytics_send({"error": "Erro interno no módulo de projetos"}, 500)
        return True

    def _analytics_send(self, result, status=200):
        payload = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _analytics_dispatch(self, method):
        route = self.path.split("?")[0]
        if not route.startswith("/api/analytics/"):
            return False
        try:
            if method == "GET":
                if route == "/api/analytics/capabilities":
                    result = analytics.capabilities()
                elif route.startswith("/api/analytics/analysis/"):
                    result = analytics.get(route.removeprefix("/api/analytics/analysis/"))
                else:
                    self._analytics_send({"error":"Rota analítica inexistente"},404)
                    return True
            elif method == "POST":
                length = int(self.headers.get("Content-Length", "0"))
                # Encoded 8 MB payload + JSON overhead.
                if length <= 0 or length > 12 * 1024 * 1024:
                    raise ValueError("Requisição maior que o limite permitido")
                body = json.loads(self.rfile.read(length))
                if route == "/api/analytics/upload":
                    result = analytics.upload(body)
                elif route == "/api/analytics/answer":
                    result = analytics.answer(body)
                else:
                    self._analytics_send({"error":"Rota analítica inexistente"},404)
                    return True
            else:
                self._analytics_send({"error":"Método inválido"},405)
                return True
            self._analytics_send(result,201 if route == "/api/analytics/upload" else 200)
        except (ValueError, TypeError, KeyError, OSError, json.JSONDecodeError) as error:
            self._analytics_send({"error":str(error)},400)
        except Exception:
            import logging
            logging.exception("Falha inesperada na API analítica")
            self._analytics_send({"error":"Falha interna na análise. Consulte os logs do servidor."},500)
        return True
    def do_POST(self) -> None:
        if self._projects_dispatch("POST"):
            return
        if self._analytics_dispatch("POST"):
            return
        route = self.path.split("?")[0]
        if route == "/api/products":
            self._route("POST")
            return
        operation = route.removeprefix("/api/create/")
        if not route.startswith("/api/create/") or operation not in OPERATIONS:
            self.send_error(404, "Operação não encontrada")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 20 * 1024 * 1024:
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
        if self._projects_dispatch("GET"):
            return
        if self._analytics_dispatch("GET"):
            return
        route = self.path.split("?")[0]
        if route == "/echarts-studio.html":
            return super().do_GET()
        if route.startswith("/visual-editor/"):
            self.path = "/" + route.removeprefix("/visual-editor/")
            return super().do_GET()
        if route in ("/api/fiscal","/api/products","/api/visual-8507/lab-draft") or route.startswith("/api/products/"):
            self._route("GET")
            return
        if route not in ("/api/overview", "/api/fiscal-preview", "/api/studio-fiscal", "/api/fiscal-catalog"):
            self.send_error(404, "Rota não encontrada")
            return
        try:
            if route == "/api/fiscal-catalog":
                result = fiscal_catalog()
            elif route == "/api/studio-fiscal":
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

    def do_PATCH(self) -> None:
        if self._projects_dispatch("PATCH"):
            return
        if self.path.startswith("/api/products/"):
            self._route("PATCH")
        else:
            self.send_error(404, "Rota não encontrada")

    def do_PUT(self) -> None:
        if self.path.startswith("/api/products/"):
            self._route("PUT")
        else:
            self.send_error(404, "Rota não encontrada")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8505)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"BI Factory API em http://0.0.0.0:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
