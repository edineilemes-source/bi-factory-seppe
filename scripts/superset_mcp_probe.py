#!/usr/bin/env python3
"""Probe Superset 6.1 MCP from inside the Superset container.

Run:
  docker exec -i superset_app python - < scripts/superset_mcp_probe.py
"""
import asyncio
import json
from fastmcp import Client

MCP_URL = "http://127.0.0.1:5008/mcp"
TARGET_DATASET = "vw_execucao_orcamentaria"


def dump(label, value):
    print(f"\n=== {label} ===")
    try:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
    except Exception:
        print(value)


async def call(client, name, arguments=None):
    result = await client.call_tool(name, arguments or {})
    dump(name, result)
    return result


async def main():
    async with Client(MCP_URL) as client:
        tools = await client.list_tools()
        names = [t.name for t in tools]
        dump("MCP TOOLS", names)

        required = [
            "health_check",
            "list_datasets",
            "get_dataset_info",
            "get_chart_type_schema",
            "generate_chart",
            "generate_dashboard",
        ]
        missing = [name for name in required if name not in names]
        if missing:
            raise SystemExit(f"Ferramentas MCP ausentes: {missing}")

        await call(client, "health_check")

        # Print exact schemas for the tools that the BI Factory will use.
        for tool in tools:
            if tool.name in {
                "list_datasets",
                "get_dataset_info",
                "get_chart_type_schema",
                "generate_chart",
                "generate_dashboard",
            }:
                dump(f"SCHEMA {tool.name}", getattr(tool, "inputSchema", None))

        # Discover the fiscal dataset. The output gives us the exact dataset id.
        await call(client, "list_datasets", {"search": TARGET_DATASET})

        # Ask Superset itself for the installed-version chart schemas.
        for chart_type in ("big_number", "xy", "table", "treemap_v2"):
            try:
                await call(client, "get_chart_type_schema", {"chart_type": chart_type})
            except Exception as exc:
                print(f"\n[WARN] schema {chart_type}: {exc}")

        print("\nPROBE_OK")


if __name__ == "__main__":
    asyncio.run(main())
