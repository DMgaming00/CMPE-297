#!/usr/bin/env python3
"""Talk to both LOCAL MCP servers over the real MCP stdio transport (no LLM, no cloud).

Lists each server's tools and makes a few read-only calls, printing the JSON-RPC results.
Uses a throw-away state directory so your demo databases are not modified.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from adk_shared.guardrails import extract_payload  # noqa: E402

CALLS = {
    "agents.ecommerce.mcp_server": [
        ("search_products", {"query": "waterproof hiking", "max_price": 150}),
        ("check_inventory", {"sku": "FTW-104"}),
        ("get_order_status", {"user_id": "cust-bob", "order_id": "ORD-1001"}),  # not Bob's
    ],
    "agents.bug_assistant.mcp_server": [
        ("search_tickets", {"query": "checkout 500 coupon"}),
        ("find_duplicate_candidates", {"title": "Stock goes negative during flash sale",
                                       "description": "two buyers got the last unit"}),
    ],
}


async def smoke(module: str, state_dir: str) -> None:
    params = StdioServerParameters(command=sys.executable, args=["-m", module], cwd=str(ROOT),
                                   env={"PATH": os.environ.get("PATH", ""),
                                        "LOCAL_STATE_DIR": state_dir,
                                        "PYTHONPATH": str(ROOT), "LOG_LEVEL": "WARNING"})
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        init = await session.initialize()
        tools = (await session.list_tools()).tools
        print(f"\n== {init.server_info.name} via MCP stdio: {len(tools)} tools")
        for tool in tools:
            ro = tool.annotations.read_only_hint if tool.annotations else None
            print(f"   - {tool.name:<28} read_only={ro}")
        for name, args in CALLS[module]:
            result = await session.call_tool(name, args)
            payload = extract_payload(result.model_dump(by_alias=True, exclude_none=True))
            text = json.dumps(payload)[:300]
            print(f"   call {name}({args}) -> {text}{'...' if len(text) == 300 else ''}")


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="mcp-smoke-") as tmp:
        for module in CALLS:
            await smoke(module, tmp)
    print("\nMCP smoke test completed.")


if __name__ == "__main__":
    asyncio.run(main())
