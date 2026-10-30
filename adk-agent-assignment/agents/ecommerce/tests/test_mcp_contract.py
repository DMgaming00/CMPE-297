"""Contract tests over the REAL MCP stdio transport (spawns the local MCP server)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from adk_shared.config import REPO_ROOT
from adk_shared.guardrails import extract_payload

EXPECTED_TOOLS = {
    "search_products", "get_product_details", "check_inventory", "find_stores",
    "prepare_order", "place_order", "list_my_orders", "get_order_status", "cancel_order",
}


async def test_mcp_server_exposes_annotated_tools_and_structured_results(tmp_path: Path):
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "agents.ecommerce.mcp_server"], cwd=str(REPO_ROOT),
        env={"PATH": os.environ.get("PATH", ""), "LOCAL_STATE_DIR": str(tmp_path),
             "PYTHONPATH": str(REPO_ROOT)})
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = {t.name: t for t in (await session.list_tools()).tools}
        assert set(tools) == EXPECTED_TOOLS
        assert tools["search_products"].annotations.read_only_hint is True
        assert tools["place_order"].annotations.destructive_hint is True
        assert tools["cancel_order"].annotations.destructive_hint is True

        result = await session.call_tool("search_products", {"query": "tent"})
        payload = extract_payload(result.model_dump(by_alias=True, exclude_none=True))
        assert payload["products"][0]["sku"] == "OUT-201"

        bad = await session.call_tool("prepare_order", {"user_id": "cust-alice",
                                                        "sku": "FTW-101", "quantity": 50})
        payload = extract_payload(bad.model_dump(by_alias=True, exclude_none=True))
        assert payload["ok"] is False and payload["error"]["code"] == "INVALID_QUANTITY"
        assert "Traceback" not in json.dumps(payload)
