from __future__ import annotations

from types import SimpleNamespace

from adk_shared.guardrails import ConfirmationGate, IdentityBinder, extract_payload
from adk_shared.redaction import redact_secrets


class FakeTool:
    def __init__(self, name: str, params: tuple[str, ...] = ()) -> None:
        self.name = name
        self._params = params

    def _get_declaration(self):
        return SimpleNamespace(parameters_json_schema={"properties": {p: {} for p in
                                                                      self._params}},
                               parameters=None)


class FakeContext:
    def __init__(self, confirmation=None, user_id="user") -> None:
        self.tool_confirmation = confirmation
        self.user_id = user_id
        self.state: dict = {}
        self.requested: list = []

    def request_confirmation(self, *, hint=None, payload=None):
        self.requested.append((hint, payload))


def test_extract_payload_shapes():
    mcp_result = {"content": [{"type": "text", "text": '{"ok": true}'}], "isError": False}
    assert extract_payload(mcp_result) == {"ok": True}
    assert extract_payload({"structuredContent": {"result": [1, 2]}, "content": []}) == [1, 2]
    assert extract_payload({"content": [{"type": "text", "text": "boom"}], "isError": True}) \
        == {"error": "boom"}
    assert extract_payload('[{"quote_id": "Q"}]') == [{"quote_id": "Q"}]
    assert extract_payload({"plain": 1}) == {"plain": 1}


def test_gate_ignores_other_tools_and_requests_confirmation_once():
    gate = ConfirmationGate({"place_order"})
    ctx = FakeContext()
    assert gate(FakeTool("search_products"), {}, ctx) is None
    result = gate(FakeTool("place_order"), {"quote_id": "Q1"}, ctx)
    assert result["status"] == "awaiting_user_confirmation" and len(ctx.requested) == 1


def test_gate_honours_decision():
    gate = ConfirmationGate({"place_order"})
    approved = FakeContext(SimpleNamespace(confirmed=True))
    rejected = FakeContext(SimpleNamespace(confirmed=False))
    assert gate(FakeTool("place_order"), {}, approved) is None
    assert gate(FakeTool("place_order"), {}, rejected)["status"] == "rejected_by_user"


def test_gate_precondition_blocks_before_asking():
    gate = ConfirmationGate({"place_order"}, precondition=lambda *a: "no quote")
    ctx = FakeContext()
    assert gate(FakeTool("place_order"), {}, ctx)["status"] == "blocked"
    assert ctx.requested == []


def test_identity_binder_overrides_model_supplied_identity():
    binder = IdentityBinder("user_id", lambda ctx: "cust-alice")
    args = {"user_id": "cust-bob", "order_id": "ORD-1"}
    binder(FakeTool("get_order_status", ("user_id", "order_id")), args, FakeContext())
    assert args["user_id"] == "cust-alice"
    args = {}
    binder(FakeTool("list_my_orders", ("user_id",)), args, FakeContext())
    assert args == {"user_id": "cust-alice"}  # injected even if the model omitted it
    other = {"sku": "X"}
    binder(FakeTool("search_products", ("query",)), other, FakeContext())
    assert "user_id" not in other


def test_redaction():
    key = "AIza" + "B" * 35
    text = f"key={key} url=https://bob:pw@example.com/x"
    redacted = redact_secrets(text)
    assert key not in redacted and "bob:pw" not in redacted
