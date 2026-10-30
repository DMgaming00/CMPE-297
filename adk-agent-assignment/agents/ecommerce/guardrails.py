"""E-commerce specific guardrails: identity binding, quote tracking and purchase approval."""

from __future__ import annotations

from typing import Any

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from adk_shared.config import env_str
from adk_shared.guardrails import ConfirmationGate, IdentityBinder, extract_payload

CONSEQUENTIAL_TOOLS = frozenset({"place_order", "cancel_order"})
QUOTES_STATE_KEY = "ecommerce_prepared_quotes"


def resolve_customer_id(tool_context: ToolContext) -> str:
    """Map the ADK session user to a store customer.

    LOCAL DEMO ONLY: ``adk web`` sessions use the user id "user", so unknown ids fall back
    to ECOMMERCE_DEMO_CUSTOMER_ID.  Real deployments authenticate the end user and, in
    Toolbox mode, the identity comes from a verified Google ID token instead.
    """
    session_user = getattr(tool_context, "user_id", "") or ""
    if session_user.startswith("cust-"):
        return session_user
    return env_str("ECOMMERCE_DEMO_CUSTOMER_ID", "cust-alice")


identity_binder = IdentityBinder("user_id", resolve_customer_id)


def record_prepared_quote(tool: BaseTool, args: dict[str, Any], tool_context: ToolContext,
                          tool_response: Any) -> None:
    """after_tool_callback: remember quotes created in this session (for approval hints)."""
    if tool.name != "prepare_order":
        return None
    payload = extract_payload(tool_response)
    if isinstance(payload, list) and payload:  # Toolbox returns a list of rows
        payload = {"ok": True, "quote": payload[0]}
    if isinstance(payload, dict) and payload.get("ok") and isinstance(payload.get("quote"), dict):
        quote = payload["quote"]
        quotes = dict(tool_context.state.get(QUOTES_STATE_KEY) or {})
        quotes[str(quote.get("quote_id", "")).upper()] = quote
        tool_context.state[QUOTES_STATE_KEY] = quotes
    return None


def _require_known_quote(tool_name: str, args: dict[str, Any],
                         tool_context: ToolContext) -> str | None:
    if tool_name != "place_order":
        return None
    quote_id = str(args.get("quote_id", "")).upper()
    if quote_id not in (tool_context.state.get(QUOTES_STATE_KEY) or {}):
        return ("place_order is only allowed for a quote created by prepare_order in this "
                "conversation. Call prepare_order first and show the quote to the customer.")
    return None


def _purchase_hint(tool_name: str, args: dict[str, Any], tool_context: ToolContext) -> str:
    if tool_name == "cancel_order":
        return f"Cancel order {args.get('order_id')}? Stock will be returned to the store."
    quote = (tool_context.state.get(QUOTES_STATE_KEY) or {}).get(
        str(args.get("quote_id", "")).upper(), {})
    return (f"Place order: {quote.get('quantity')} x {quote.get('product_name')} "
            f"({quote.get('sku')}) from {quote.get('store_id')} at {quote.get('unit_price')} "
            f"each - total {quote.get('total')}. Approve this purchase?")


purchase_gate = ConfirmationGate(CONSEQUENTIAL_TOOLS, hint_builder=_purchase_hint,
                                 precondition=_require_known_quote)
