"""Backend selection for the e-commerce agent.

ECOMMERCE_BACKEND=local   (default) LOCAL MCP MODE: ADK -> MCP stdio -> repository MCP
                          server -> SQLite.  Real MCP protocol, development storage.
ECOMMERCE_BACKEND=toolbox PRODUCTION MODE: ADK -> MCP Toolbox for Databases (HTTP) ->
                          parameterised SQL -> PostgreSQL / AlloyDB.
"""

from __future__ import annotations

from typing import Any

from adk_shared.config import env_str
from adk_shared.mcp_connections import local_mcp_toolset


def backend() -> str:
    value = env_str("ECOMMERCE_BACKEND", "local").lower()
    if value not in {"local", "toolbox"}:
        raise ValueError("ECOMMERCE_BACKEND must be 'local' or 'toolbox'")
    return value


def _id_token(ctx: Any) -> str:
    """Google ID token of the end user, supplied by the front end via session state.

    Toolbox verifies the token (authServices: google-signin) and fills the hidden
    ``user_email`` parameter from its ``email`` claim, so the LLM never controls identity.
    """
    token = ""
    state = getattr(ctx, "state", None)
    if state is not None:
        token = state.get("temp:google_id_token", "") or ""
    return token or env_str("ECOMMERCE_GOOGLE_ID_TOKEN")


def build_toolsets() -> list[Any]:
    if backend() == "toolbox":
        from google.adk.tools.toolbox_toolset import ToolboxToolset  # optional extra

        return [ToolboxToolset(
            server_url=env_str("TOOLBOX_URL", "http://127.0.0.1:5000"),
            toolset_name="commerce",
            auth_token_getters={"google-signin": _id_token},
        )]
    return [local_mcp_toolset("agents.ecommerce.mcp_server")]
