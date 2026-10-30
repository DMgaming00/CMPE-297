"""MCP connections for the bug assistant.

BUG_TRACKER_BACKEND=local   LOCAL MCP MODE: ADK -> MCP stdio -> repository bug-tracker MCP
                            server -> SQLite (seeded with fictional tickets).
BUG_TRACKER_BACKEND=toolbox PRODUCTION MODE: ADK -> MCP Toolbox for Databases -> Postgres
                            (configs/toolbox/bug_tracker_tools.yaml).
GITHUB_PERSONAL_ACCESS_TOKEN set -> also attach GitHub's remote MCP server in READ-ONLY
                            mode (issues / pull requests of real repositories).
"""

from __future__ import annotations

from typing import Any

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.base_tool import BaseTool

from adk_shared.config import env_str
from adk_shared.mcp_connections import local_mcp_toolset

WRITE_TOOLS = frozenset({"create_ticket", "update_ticket_status", "update_ticket_priority",
                         "add_comment", "mark_duplicate"})
GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"
_GITHUB_READ_PREFIXES = ("search_", "list_", "get_", "issue_read", "pull_request_read")


def backend() -> str:
    value = env_str("BUG_TRACKER_BACKEND", "local").lower()
    if value not in {"local", "toolbox"}:
        raise ValueError("BUG_TRACKER_BACKEND must be 'local' or 'toolbox'")
    return value


def github_read_only(tool: BaseTool, readonly_context: ReadonlyContext | None = None) -> bool:
    """Expose only read-style GitHub MCP tools (defence in depth with X-MCP-Readonly)."""
    return tool.name.removeprefix("github_").startswith(_GITHUB_READ_PREFIXES)


def build_toolsets() -> list[Any]:
    toolsets: list[Any] = []
    if backend() == "toolbox":
        from google.adk.tools.toolbox_toolset import ToolboxToolset  # optional extra

        url = env_str("BUG_TRACKER_TOOLBOX_URL") or env_str("TOOLBOX_URL",
                                                             "http://127.0.0.1:5001")
        toolsets.append(ToolboxToolset(server_url=url, toolset_name="bug-tracker"))
    else:
        toolsets.append(local_mcp_toolset("agents.bug_assistant.mcp_server"))

    token = env_str("GITHUB_PERSONAL_ACCESS_TOKEN")
    if token:
        from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

        toolsets.append(McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=GITHUB_MCP_URL,
                headers={"Authorization": f"Bearer {token}", "X-MCP-Readonly": "true"},
            ),
            tool_filter=github_read_only,
            tool_name_prefix="github",
        ))
    return toolsets
