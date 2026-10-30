"""MCP contract test (real stdio server) + ADK flow test for write approval."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from adk_shared.config import REPO_ROOT
from adk_shared.guardrails import ConfirmationGate, extract_payload
from adk_shared.mcp_connections import local_mcp_toolset
from adk_shared.testing import (
    ScriptedLlm,
    call,
    confirmation_reply,
    function_calls,
    function_responses,
    run_turn,
    text,
    user_text,
)
from agents.bug_assistant.mcp_server.store import TicketStore
from agents.bug_assistant.toolsets import WRITE_TOOLS, github_read_only

EXPECTED = {"search_tickets", "get_ticket", "list_tickets", "find_duplicate_candidates",
            "create_ticket", "update_ticket_status", "update_ticket_priority", "add_comment",
            "mark_duplicate"}


async def test_bug_tracker_mcp_contract(tmp_path: Path):
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "agents.bug_assistant.mcp_server"],
        cwd=str(REPO_ROOT), env={"PATH": os.environ.get("PATH", ""),
                                 "LOCAL_STATE_DIR": str(tmp_path),
                                 "PYTHONPATH": str(REPO_ROOT)})
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = {t.name: t for t in (await session.list_tools()).tools}
        assert set(tools) == EXPECTED
        for name in EXPECTED - WRITE_TOOLS:
            assert tools[name].annotations.read_only_hint is True, name
        for name in WRITE_TOOLS:
            assert tools[name].annotations.read_only_hint is False, name
        assert set(tools["create_ticket"].input_schema["required"]) == {
            "title", "description", "priority", "component"}
        result = await session.call_tool("search_tickets", {"query": "redirect loop cookie"})
        payload = extract_payload(result.model_dump(by_alias=True, exclude_none=True))
        assert payload["results"][0]["id"] == 2
        missing = await session.call_tool("get_ticket", {"ticket_id": 4242})
        payload = extract_payload(missing.model_dump(by_alias=True, exclude_none=True))
        assert payload["error"]["code"] == "NOT_FOUND"


@pytest.fixture
async def bug_harness(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOCAL_STATE_DIR", str(tmp_path))
    toolset = local_mcp_toolset("agents.bug_assistant.mcp_server")
    llm = ScriptedLlm()
    agent = LlmAgent(name="bugs", model=llm, tools=[toolset],
                     before_tool_callback=ConfirmationGate(WRITE_TOOLS))
    runner = InMemoryRunner(agent=agent, app_name="bugs")
    session = await runner.session_service.create_session(app_name="bugs", user_id="dev")
    yield llm, runner, session, TicketStore(tmp_path / "bug_tracker.sqlite")
    await toolset.close()


async def test_reads_run_freely_but_writes_need_approval(bug_harness):
    llm, runner, session, store = bug_harness
    llm.script = [call("search_tickets", query="negative inventory concurrent"),
                  call("add_comment", ticket_id=6, body="Seen again during the Oct 29 sale."),
                  text("Waiting for approval.")]
    events = await run_turn(runner, "dev", session.id, user_text("Add a note to the stock bug"))
    names = [c.name for c in function_calls(events)]
    assert names[:2] == ["search_tickets", "add_comment"]
    assert "adk_request_confirmation" in names
    assert len(store.get(6)["comments"]) == 1  # not written yet

    confirmation_id = next(c.id for c in function_calls(events)
                           if c.name == "adk_request_confirmation")
    llm.script = [text("Comment added.")]
    events = await run_turn(runner, "dev", session.id, confirmation_reply(confirmation_id, True))
    added = [r.response for r in function_responses(events) if r.name == "add_comment"]
    assert extract_payload(added[0])["ok"] is True
    assert store.get(6)["comments"][-1]["body"] == "Seen again during the Oct 29 sale."


class _Named:
    def __init__(self, name: str) -> None:
        self.name = name


@pytest.mark.parametrize("name,allowed", [("search_issues", True), ("issue_read", True),
                                          ("github_list_issues", True),
                                          ("create_issue", False), ("merge_pull_request", False),
                                          ("delete_file", False)])
def test_github_mcp_filter_is_read_only(name, allowed):
    assert github_read_only(_Named(name)) is allowed
