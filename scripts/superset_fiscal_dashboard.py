"""Bootstrap the fiscal Superset dashboard through the supported REST API.

Golden case: PMCG official fiscal execution.  The script is intentionally
idempotent by title and never writes directly to Superset's metadata database.
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request


def request(base, path, token=None, method="GET", payload=None, csrf_token=None):
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if csrf_token and method in {"POST", "PUT", "DELETE", "PATCH"}:
        headers["X-CSRFToken"] = csrf_token
    req = urllib.request.Request(base.rstrip("/") + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Superset API {method} {path} -> HTTP {exc.code}: {detail}"
        ) from exc


def csrf(base, token):
    return request(base, "/api/v1/security/csrf_token/", token)["result"]


def login(base, username, password):
    result = request(base, "/api/v1/security/login", method="POST", payload={
        "username": username, "password": password, "provider": "db", "refresh": True,
    })
    return result["access_token"]


def find_one(base, token, resource, column, value):
    q = urllib.parse.quote(json.dumps({"filters": [{"col": column, "opr": "eq", "value": value}]}))
    result = request(base, f"/api/v1/{resource}/?q={q}", token)
    rows = result.get("result", [])
    return rows[0] if rows else None


def create_chart(base, token, csrf_token, dataset_id, title, viz_type, params):
    existing = find_one(base, token, "chart", "slice_name", title)
    body = {
        "slice_name": title,
        "datasource_id": dataset_id,
        "datasource_type": "table",
        "viz_type": viz_type,
        "params": json.dumps(params, separators=(",", ":")),
    }
    if existing:
        request(base, f"/api/v1/chart/{existing['id']}", token, "PUT", body, csrf_token)
        return existing["id"]
    return request(base, "/api/v1/chart/", token, "POST", body, csrf_token)["id"]


def big_number_params(column, subtitle, number_format=".3s"):
    return {
        "viz_type": "big_number_total",
        "metric": {"expressionType": "SIMPLE", "column": {"column_name": column},
                   "aggregate": "MAX", "label": subtitle},
        "adhoc_filters": [{
            "expressionType": "SIMPLE", "subject": "bimestre", "operator": "==",
            "comparator": 6, "clause": "WHERE", "sqlExpression": None,
        }],
        "header_font_size": 0.4,
        "subheader": subtitle,
        "y_axis_format": number_format,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://localhost:8088")
    p.add_argument("--username", default="admin")
    p.add_argument("--password", default="admin")
    args = p.parse_args()
    token = login(args.base_url, args.username, args.password)
    csrf_token = csrf(args.base_url, token)

    dataset = find_one(args.base_url, token, "dataset", "table_name", "vw_execucao_orcamentaria")
    if not dataset:
        raise SystemExit("Dataset vw_execucao_orcamentaria não encontrado no Superset.")
    dataset_id = dataset["id"]

    specs = [
        ("Receita Realizada", "receita_realizada_acumulada", ".3s"),
        ("Despesa Empenhada", "despesa_empenhada_acumulada", ".3s"),
        ("Despesa Liquidada", "despesa_liquidada_acumulada", ".3s"),
        ("Despesa Paga", "despesa_paga_acumulada", ".3s"),
        ("Resultado Orçamentário Formal", "resultado_orcamentario_formal", ".3s"),
        ("Receita − Liquidada", "margem_receita_menos_liquidada", ".3s"),
        ("% Liquidada / Receita", "liquidada_sobre_receita_pct", ".2f"),
    ]
    chart_ids = []
    for title, column, fmt in specs:
        chart_ids.append(create_chart(args.base_url, token, csrf_token, dataset_id, title,
                                      "big_number_total", big_number_params(column, title, fmt)))

    line_params = {
        "viz_type": "echarts_timeseries_line",
        "x_axis": "bimestre",
        "time_grain_sqla": None,
        "metrics": [
            {"expressionType":"SIMPLE","column":{"column_name":c},"aggregate":"MAX","label":label}
            for label,c in [
                ("Receita Realizada","receita_realizada_acumulada"),
                ("Empenhada","despesa_empenhada_acumulada"),
                ("Liquidada","despesa_liquidada_acumulada"),
                ("Paga","despesa_paga_acumulada"),
            ]
        ],
        "adhoc_filters": [],
        "row_limit": 100,
        "order_desc": False,
        "show_legend": True,
        "y_axis_format": ".3s",
        "x_axis_time_format": "smart_date",
    }
    chart_ids.append(create_chart(args.base_url, token, csrf_token, dataset_id,
                                  "Evolução Acumulada por Bimestre",
                                  "echarts_timeseries_line", line_params))

    dashboard_title = "Execução Orçamentária — Campo Grande/MS"
    dashboard = find_one(args.base_url, token, "dashboard", "dashboard_title", dashboard_title)
    body = {"dashboard_title": dashboard_title, "published": True, "slug": "execucao-orcamentaria-campo-grande"}
    if dashboard:
        dashboard_id = dashboard["id"]
        request(args.base_url, f"/api/v1/dashboard/{dashboard_id}", token, "PUT", body, csrf_token)
    else:
        dashboard_id = request(args.base_url, "/api/v1/dashboard/", token, "POST", body, csrf_token)["id"]

    # Attach charts by updating dashboard_ids on each chart. Layout can then be
    # refined in the dashboard editor while chart definitions remain generated.
    for chart_id in chart_ids:
        request(args.base_url, f"/api/v1/chart/{chart_id}", token, "PUT", {"dashboards": [dashboard_id]}, csrf_token)

    print(f"Superset dashboard provisionado: {dashboard_title}")
    print(f"Dashboard ID: {dashboard_id}")
    print(f"Charts: {len(chart_ids)}")
    print(f"Abra: {args.base_url}/superset/dashboard/{dashboard_id}/")


if __name__ == "__main__":
    main()
