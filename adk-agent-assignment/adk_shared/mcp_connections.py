"""Factories for the MCP connections used by agents C and E.

Two genuinely-MCP transports are supported:

* LOCAL MCP MODE   - ADK spawns a repository MCP server (``python -m ...mcp_server``)
  as a subprocess and talks to it over the MCP stdio transport (``McpToolset``).
  Storage is SQLite; the protocol boundary is real.
* PRODUCTION MODE  - ADK connects to a running MCP Toolbox for Databases server
  (``ToolboxToolset``) whose tools are parameterised SQL over PostgreSQL/AlloyDB.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence

from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

from .config import REPO_ROOT, env_int

# Environment variables forwarded to local MCP server subprocesses.  Everything else
# (API keys, DB passwords, tokens) is withheld: the servers do not need them.
_FORWARDED_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT", "LOCAL_STATE_DIR",
                  "LOG_LEVEL", "PYTHONPATH")


def local_mcp_toolset(module: str, *, extra_env: dict[str, str] | None = None,
                      tool_filter: Sequence[str] | None = None) -> McpToolset:
    """Connect to a repository MCP server over stdio."""
    env = {k: v for k, v in os.environ.items() if k in _FORWARDED_ENV}
    env.setdefault("PYTHONPATH", str(REPO_ROOT))
    if extra_env:
        env.update(extra_env)
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=["-m", module],
                cwd=str(REPO_ROOT),
                env=env,
            ),
            timeout=float(env_int("MCP_STDIO_TIMEOUT_SECONDS", 20, minimum=5, maximum=120)),
        ),
        tool_filter=list(tool_filter) if tool_filter else None,
    )
