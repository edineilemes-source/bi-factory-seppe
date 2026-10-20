"""Read-only bridge for the first React BI Factory migration slice.

Run: python -u scripts/serve_bi_factory_api.py --port 8505
Does not mutate project data, publications or the Streamlit installation.
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "storage/information_products/registry.json"
FOLDERS = ROOT / "storage/information_products/folders.json"
RREO = ROOT / "storage/official/siconfi/rreo"


def load_list(path: Path) -> list:
    if not path.is_file():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"Esperada lista em {path.name}")
    return value


def overview() -> dict:
    return {
        "project": {"id": "pmcg-financas-publicas", "name": "PMCG — Finanças Públicas", "years": [2022, 2023, 2024, 2025, 2026]},
        "products": load_list(REGISTRY),
        "folders": load_list(FOLDERS),
        "fiscal": {"source": "STN/SICONFI", "years": [
            {"year": year, "files": len(list((RREO / str(year)).rglob("*.json")))}
            for year in range(2022, 2027)
        ]},
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.split("?")[0] != "/api/overview":
            self.send_error(404, "Rota não encontrada")
            return
        try:
            payload = json.dumps(overview(), ensure_ascii=False).encode("utf-8")
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8505)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"BI Factory API em http://0.0.0.0:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
