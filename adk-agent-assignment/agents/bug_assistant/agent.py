"""C) Software bug assistant: ADK agent whose ticket operations go through MCP.

Tool inventory (and what each one really is):
* bug-tracker MCP toolset - MCP stdio server (local) or MCP Toolbox (production)
* GitHub MCP toolset     - optional remote MCP server, read-only
* assess_severity        - local deterministic Python function (not MCP)
* get_current_date       - local Python function (not MCP)
* web_research_agent     - ADK sub-agent wrapped as a tool (Google Search grounding)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.tool_context import ToolContext

from adk_shared.config import advanced_model, fast_model
from adk_shared.guardrails import ConfirmationGate

from .prompts import BUG_ASSISTANT_INSTRUCTION, WEB_RESEARCH_INSTRUCTION
from .severity import assess_severity
from .toolsets import WRITE_TOOLS, backend, build_toolsets


def get_current_date() -> dict:
    """Return today's date (UTC) so ticket ages and timelines can be reasoned about."""
    return {"date": datetime.now(UTC).date().isoformat()}


def _write_hint(tool_name: str, args: dict[str, Any], tool_context: ToolContext) -> str:
    summary = {k: v for k, v in args.items() if k != "description"}
    if "description" in args:
        summary["description"] = str(args["description"])[:200]
    return f"Approve bug-tracker write '{tool_name}' with {json.dumps(summary)}?"


web_research_agent = LlmAgent(
    name="web_research_agent",
    model=fast_model(),
    description="Searches the public web for explanations and fixes for an error message.",
    instruction=WEB_RESEARCH_INSTRUCTION,
    tools=[google_search],
)

root_agent = LlmAgent(
    name="software_bug_assistant",
    model=advanced_model(),
    description="Triages bug reports: searches tickets over MCP, detects duplicates, "
                "assesses severity, plans debugging and performs approved ticket updates.",
    instruction=BUG_ASSISTANT_INSTRUCTION + f"\n(Bug tracker backend: {backend()}.)\n",
    tools=[*build_toolsets(), assess_severity, get_current_date, AgentTool(web_research_agent)],
    before_tool_callback=ConfirmationGate(WRITE_TOOLS, hint_builder=_write_hint),
)
