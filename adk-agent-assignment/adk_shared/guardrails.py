"""Tool-level guardrails implemented as ADK callbacks.

These run *outside* the model, so a prompt-injected or confused LLM cannot skip them:

* ``ConfirmationGate``  - human-in-the-loop approval (ADK tool confirmation) for
  consequential tools, regardless of whether the tool is a local function, an MCP
  tool (``McpToolset``) or an MCP Toolbox tool (``ToolboxToolset``).
* ``IdentityBinder``    - overwrites identity arguments (e.g. ``user_id``) with the
  authenticated session identity, so the model cannot act on behalf of another user.
* ``extract_payload``   - normalises results from function tools, MCP ``CallToolResult``
  dicts and Toolbox JSON strings into plain Python data.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Any

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from .logging_utils import get_logger, log_tool_event

logger = get_logger(__name__)

HintBuilder = Callable[[str, dict[str, Any], ToolContext], str | None]
BeforeToolCallback = Callable[[BaseTool, dict[str, Any], ToolContext], Any]


def extract_payload(tool_response: Any) -> Any:
    """Return the structured payload from any tool result shape used in this repo."""
    if isinstance(tool_response, str):
        try:
            return json.loads(tool_response)
        except json.JSONDecodeError:
            return tool_response
    if isinstance(tool_response, dict):
        if "structuredContent" in tool_response and tool_response["structuredContent"] is not None:
            structured = tool_response["structuredContent"]
            # MCPServer wraps non-object return values as {"result": ...}
            if isinstance(structured, dict) and set(structured) == {"result"}:
                return structured["result"]
            return structured
        content = tool_response.get("content")
        looks_like_mcp = isinstance(content, list) and (
            "isError" in tool_response
            or (bool(content) and isinstance(content[0], dict) and "type" in content[0])
        )
        if looks_like_mcp:
            texts = [c.get("text", "") for c in content if isinstance(c, dict)]
            joined = "\n".join(t for t in texts if t)
            if tool_response.get("isError"):
                return {"error": joined or "MCP tool reported an error"}
            try:
                return json.loads(joined)
            except (json.JSONDecodeError, TypeError):
                return joined
        if set(tool_response) == {"result"}:
            return extract_payload(tool_response["result"])
    return tool_response


class ConfirmationGate:
    """``before_tool_callback`` that requires explicit human approval.

    First call: requests an ADK tool confirmation (ADK Web renders an approve/reject
    prompt; API clients receive an ``adk_request_confirmation`` function call) and
    short-circuits the tool.  After the user responds, ADK re-invokes the tool with
    ``tool_context.tool_confirmation`` populated and the gate lets it through only if
    ``confirmed`` is true.
    """

    def __init__(self, tool_names: Iterable[str], hint_builder: HintBuilder | None = None,
                 precondition: Callable[[str, dict[str, Any], ToolContext], str | None]
                 | None = None) -> None:
        self.tool_names = frozenset(tool_names)
        self.hint_builder = hint_builder
        self.precondition = precondition

    def __call__(self, tool: BaseTool, args: dict[str, Any],
                 tool_context: ToolContext) -> dict[str, Any] | None:
        if tool.name not in self.tool_names:
            return None
        if self.precondition is not None:
            problem = self.precondition(tool.name, args, tool_context)
            if problem:
                log_tool_event(logger, "tool_blocked", tool=tool.name, reason=problem)
                return {"status": "blocked", "error": problem}
        confirmation = tool_context.tool_confirmation
        if confirmation is None:
            hint = None
            if self.hint_builder is not None:
                hint = self.hint_builder(tool.name, args, tool_context)
            hint = hint or f"Approve call to {tool.name} with arguments {json.dumps(args)}?"
            tool_context.request_confirmation(hint=hint, payload={"tool": tool.name,
                                                                  "args": args})
            log_tool_event(logger, "confirmation_requested", tool=tool.name, args=args)
            return {
                "status": "awaiting_user_confirmation",
                "message": "This action needs explicit user approval. Nothing has been "
                           "executed yet. Wait for the user's decision.",
            }
        if not confirmation.confirmed:
            log_tool_event(logger, "confirmation_rejected", tool=tool.name)
            return {"status": "rejected_by_user", "message": "The user declined. Nothing "
                                                             "was executed."}
        log_tool_event(logger, "confirmation_granted", tool=tool.name)
        return None


class IdentityBinder:
    """``before_tool_callback`` that forces identity arguments to the session identity.

    The model may *see* a ``user_id`` parameter in the tool schema, but whatever value it
    supplies is discarded and replaced with ``resolve_identity(tool_context)``.
    """

    def __init__(self, param_name: str, resolve_identity: Callable[[ToolContext], str]) -> None:
        self.param_name = param_name
        self.resolve_identity = resolve_identity

    def __call__(self, tool: BaseTool, args: dict[str, Any],
                 tool_context: ToolContext) -> None:
        if self.param_name not in _declared_params(tool, args):
            return None
        identity = self.resolve_identity(tool_context)
        supplied = args.get(self.param_name)
        if supplied not in (None, "", identity):
            log_tool_event(logger, "identity_override", tool=tool.name,
                           model_supplied=str(supplied), enforced=identity)
        args[self.param_name] = identity
        return None


def _declared_params(tool: BaseTool, args: dict[str, Any]) -> set[str]:
    names = set(args)
    try:
        declaration = tool._get_declaration()
    except Exception:  # pragma: no cover - defensive; declarations are optional
        declaration = None
    if declaration is not None:
        schema = declaration.parameters_json_schema or {}
        if isinstance(schema, dict):
            names |= set((schema.get("properties") or {}).keys())
        if declaration.parameters is not None and declaration.parameters.properties:
            names |= set(declaration.parameters.properties.keys())
    return names


def chain_before_tool(*callbacks: BeforeToolCallback) -> BeforeToolCallback:
    """Run callbacks in order; the first non-None result short-circuits the tool."""

    async def _chained(tool: BaseTool, args: dict[str, Any], tool_context: ToolContext) -> Any:
        for callback in callbacks:
            result = callback(tool, args, tool_context)
            if hasattr(result, "__await__"):
                result = await result
            if result is not None:
                return result
        return None

    return _chained
