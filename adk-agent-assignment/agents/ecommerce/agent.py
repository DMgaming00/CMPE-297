"""E) Production-style e-commerce agent: ADK + MCP (local server or MCP Toolbox) + DB.

Read tools run freely.  Consequential tools (place_order, cancel_order) pass through two
deterministic guards that the model cannot bypass:

1. IdentityBinder   - the order tools always act for the authenticated customer;
2. ConfirmationGate - ADK tool confirmation (human approval) + "quote must exist" check.
"""

from google.adk.agents import LlmAgent

from adk_shared.config import fast_model
from adk_shared.guardrails import chain_before_tool

from .guardrails import identity_binder, purchase_gate, record_prepared_quote
from .prompts import COMMERCE_INSTRUCTION
from .toolsets import backend, build_toolsets

root_agent = LlmAgent(
    name="ecommerce_agent",
    model=fast_model(),
    description="Shopping assistant with catalog search, inventory, stores and confirmed, "
                "user-scoped ordering over MCP.",
    instruction=COMMERCE_INSTRUCTION + f"\n(Backend mode: {backend()}.)\n",
    tools=build_toolsets(),
    before_tool_callback=chain_before_tool(identity_binder, purchase_gate),
    after_tool_callback=record_prepared_quote,
)
