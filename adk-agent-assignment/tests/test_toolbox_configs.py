"""Static validation of the PRODUCTION MCP Toolbox configurations.

These checks run without a Toolbox binary or database. They do NOT prove the SQL
executes; see docs/TESTING.md for the manual Toolbox + PostgreSQL verification steps.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from adk_shared.config import CONFIG_DIR
from adk_shared.seed import SEED_FILES

CONFIGS = {
    "ecommerce_tools.yaml": {"toolset": "commerce", "local_module": "agents.ecommerce",
                             "user_scoped": {"prepare_order", "place_order", "list_my_orders",
                                             "get_order_status", "cancel_order"}},
    "bug_tracker_tools.yaml": {"toolset": "bug-tracker", "local_module": "agents.bug_assistant",
                               "user_scoped": set()},
}
LOCAL_TOOLS = {
    "agents.ecommerce": {"search_products", "get_product_details", "check_inventory",
                         "find_stores", "prepare_order", "place_order", "list_my_orders",
                         "get_order_status", "cancel_order"},
    "agents.bug_assistant": {"search_tickets", "get_ticket", "list_tickets",
                             "find_duplicate_candidates", "create_ticket",
                             "update_ticket_status", "update_ticket_priority", "add_comment",
                             "mark_duplicate"},
}


def _docs(name: str) -> list[dict]:
    return [d for d in yaml.safe_load_all((CONFIG_DIR / "toolbox" / name).read_text()) if d]


@pytest.mark.parametrize("name", CONFIGS)
def test_manifest_shape(name):
    docs = _docs(name)
    for doc in docs:
        assert doc["kind"] in {"source", "tool", "toolset", "authService"}, doc
        assert "name" in doc
    sources = {d["name"] for d in docs if d["kind"] == "source"}
    tools = {d["name"]: d for d in docs if d["kind"] == "tool"}
    for tool in tools.values():
        assert tool["type"] == "postgres-sql" and tool["source"] in sources
        assert tool["description"].strip()
    toolsets = {d["name"]: d["tools"] for d in docs if d["kind"] == "toolset"}
    assert set(toolsets[CONFIGS[name]["toolset"]]) == set(tools)


@pytest.mark.parametrize("name", CONFIGS)
def test_placeholders_match_parameters_and_sql_is_parameterised(name):
    for tool in (d for d in _docs(name) if d["kind"] == "tool"):
        params = tool.get("parameters", [])
        used = {int(n) for n in re.findall(r"\$(\d+)", tool["statement"])}
        assert used == set(range(1, len(params) + 1)), (tool["name"], used, len(params))
        assert "{{" not in tool["statement"] and "templateParameters" not in tool


@pytest.mark.parametrize("name", CONFIGS)
def test_tool_names_match_local_mcp_server(name):
    tools = {d["name"] for d in _docs(name) if d["kind"] == "tool"}
    assert tools == LOCAL_TOOLS[CONFIGS[name]["local_module"]]


def test_user_scoped_tools_take_identity_from_verified_token():
    docs = _docs("ecommerce_tools.yaml")
    auth = {d["name"] for d in docs if d["kind"] == "authService"}
    for tool in (d for d in docs if d["kind"] == "tool"):
        auth_params = [p for p in tool.get("parameters", []) if p.get("authServices")]
        if tool["name"] in CONFIGS["ecommerce_tools.yaml"]["user_scoped"]:
            assert len(auth_params) == 1, tool["name"]
            assert auth_params[0]["authServices"][0]["name"] in auth
            assert auth_params[0]["authServices"][0]["field"] == "email"
            assert not [p for p in tool["parameters"] if p["name"] == "user_id"]
        else:
            assert not auth_params, tool["name"]


@pytest.mark.parametrize("name", CONFIGS)
def test_no_plaintext_credentials(name):
    for doc in _docs(name):
        if doc["kind"] in {"source", "authService"}:
            for key in ("password", "user", "host", "clientId"):
                if key in doc:
                    assert str(doc[key]).startswith("${"), (doc["name"], key)


def test_postgres_seed_files_are_in_sync_with_json():
    for path, render in SEED_FILES.items():
        assert Path(path).read_text() == render(), "run scripts/seed_demo_data.py --postgres"
