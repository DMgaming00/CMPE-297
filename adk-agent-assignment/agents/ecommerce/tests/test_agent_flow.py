"""End-to-end ADK flow tests: real Runner + real local MCP server + guardrail callbacks.

The LLM is a ScriptedLlm test double, so these tests verify the platform-enforced
controls (identity binding, purchase confirmation, quote precondition) independently
of model behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner

from adk_shared.guardrails import chain_before_tool, extract_payload
from adk_shared.mcp_connections import local_mcp_toolset
from adk_shared.testing import (
    ScriptedLlm,
    call,
    confirmation_reply,
    function_calls,
    function_responses,
    last_tool_response,
    run_turn,
    text,
    user_text,
)
from agents.ecommerce.guardrails import identity_binder, purchase_gate, record_prepared_quote
from agents.ecommerce.mcp_server.store import CommerceStore


def _quote_id(request) -> str:
    return extract_payload(last_tool_response(request, "prepare_order"))["quote"]["quote_id"]


@pytest.fixture
async def harness(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOCAL_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("ECOMMERCE_DEMO_CUSTOMER_ID", "cust-alice")
    toolset = local_mcp_toolset("agents.ecommerce.mcp_server")
    llm = ScriptedLlm()
    agent = LlmAgent(name="shop", model=llm, tools=[toolset],
                     before_tool_callback=chain_before_tool(identity_binder, purchase_gate),
                     after_tool_callback=record_prepared_quote)
    runner = InMemoryRunner(agent=agent, app_name="shop")
    session = await runner.session_service.create_session(app_name="shop", user_id="user")
    yield llm, runner, session, CommerceStore(tmp_path / "ecommerce.sqlite")
    await toolset.close()


def _confirmation_call_id(events) -> str:
    calls = [c for c in function_calls(events) if c.name == "adk_request_confirmation"]
    assert len(calls) == 1, "expected exactly one confirmation request"
    return calls[0].id


async def test_purchase_requires_confirmation_and_binds_identity(harness):
    llm, runner, session, store = harness
    # The model tries to act as Bob; the IdentityBinder must force Alice (session user).
    llm.script = [call("prepare_order", user_id="cust-bob", sku="FTW-101", quantity=2,
                       store_id="WH-ONLINE"), text("Here is your quote.")]
    await run_turn(runner, "user", session.id, user_text("Buy two AeroRun Trainers"))
    assert len(store.list_orders("cust-alice")["orders"]) == 2  # nothing purchased yet

    llm.script = [lambda req: call("place_order", user_id="cust-bob", quote_id=_quote_id(req)),
                  text("Please approve the purchase.")]
    events = await run_turn(runner, "user", session.id, user_text("Yes, place it"))
    confirmation_id = _confirmation_call_id(events)
    statuses = [r.response.get("status") for r in function_responses(events)
                if r.name == "place_order"]
    assert statuses == ["awaiting_user_confirmation"]
    assert len(store.list_orders("cust-alice")["orders"]) == 2  # still not purchased

    llm.script = [text("Order placed.")]
    await run_turn(runner, "user", session.id, confirmation_reply(confirmation_id, True))
    alice_orders = store.list_orders("cust-alice")["orders"]
    assert len(alice_orders) == 3 and alice_orders[0]["total"] == "$179.98"
    assert len(store.list_orders("cust-bob")["orders"]) == 1  # Bob untouched


async def test_rejected_confirmation_places_nothing(harness):
    llm, runner, session, store = harness
    llm.script = [call("prepare_order", sku="HOM-504", quantity=1), text("Quote ready.")]
    await run_turn(runner, "user", session.id, user_text("Quote a bottle"))
    llm.script = [lambda req: call("place_order", quote_id=_quote_id(req)), text("Approve?")]
    events = await run_turn(runner, "user", session.id, user_text("buy"))
    llm.script = [text("Okay, cancelled.")]
    events = await run_turn(runner, "user", session.id,
                            confirmation_reply(_confirmation_call_id(events), False))
    statuses = [r.response.get("status") for r in function_responses(events)
                if r.name == "place_order"]
    assert statuses == ["rejected_by_user"]
    assert len(store.list_orders("cust-alice")["orders"]) == 2


async def test_fabricated_quote_is_blocked_before_confirmation(harness):
    llm, runner, session, store = harness
    llm.script = [call("place_order", quote_id="Q-DEADBEEF0000"), text("Blocked.")]
    events = await run_turn(runner, "user", session.id, user_text("Just buy anything"))
    assert not [c for c in function_calls(events) if c.name == "adk_request_confirmation"]
    responses = [r.response for r in function_responses(events) if r.name == "place_order"]
    assert responses[0]["status"] == "blocked"
    assert len(store.list_orders("cust-alice")["orders"]) == 2
