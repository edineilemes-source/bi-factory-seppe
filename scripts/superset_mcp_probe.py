#!/usr/bin/env python3
"""Probe the Superset 6.1 MCP tool-search interface.

Run from the BI Factory repo:
  docker exec -i superset_app python - < scripts/superset_mcp_probe.py
"""
import asyncio
import json
from fastmcp import Client

MCP_URL = "http://127.0.0.1:5008/mcp"
TARGET_DATASET = "vw_execucao_orcamentaria"


def plain(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [plain(v) for v in value]
    return value


def dump(label, value):
    print(f"\n=== {label} ===")
    try:
        print(json.dumps(plain(value), ensure_ascii=False, indent=2, default=str))
    except Exception:
        print(value)


async def proxy(client, name, arguments=None):
    """Invoke a hidden Superset tool through the 6.1 call_tool proxy."""
    result = await client.call_tool(
        "call_tool",
        {"name": name, "arguments": arguments or {}},
    )
    dump(name, result)
    return result


async def search(client, query=None):
    args = {} if query is None else {"query": query}
    result = await client.call_tool("search_tools", args)
    dump(f"SEARCH {query or 'ALL'}", result)
    return result


async def main():
    async with Client(MCP_URL) as client:
        visible = await client.list_tools()
        dump("VISIBLE MCP TOOLS", [t.name for t in visible])

        # Pinned tool: proves transport + Superset context.
        health = await client.call_tool("health_check", {})
        dump("health_check", health)

        # Superset 6.1 hides most tools behind search_tools/call_tool by default.
        # Discover only the capabilities needed by the BI Factory.
        queries = [
            "list datasets",
            "dataset info",
            "chart type schema",
            "generate chart",
            "generate dashboard",
            "chart preview data",
        ]
        for query in queries:
            await search(client, query)

        # Exercise read-only hidden tools through the proxy.
        await proxy(client, "list_datasets", {"search": TARGET_DATASET})

        # Discover installed-version configuration contracts. Some chart type
        # identifiers vary; failures are printed and do not stop the probe.
        for chart_type in ("big_number", "echarts_timeseries_line", "table", "treemap_v2"):
            try:
                await proxy(
                    client,
                    "get_chart_type_schema",
                    {"chart_type": chart_type},
                )
            except Exception as exc:
                print(f"\n[WARN] get_chart_type_schema({chart_type}): {exc}")

        print("\nPROBE_OK")


if __name__ == "__main__":
    asyncio.run(main())
