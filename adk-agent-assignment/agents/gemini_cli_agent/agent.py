"""B) Gemini CLI engineering agent: ADK orchestrates, Gemini CLI is a tool.

User -> ADK orchestrator (plan) -> run_gemini_cli_analysis tool
     -> validate URL -> hardened shallow clone (temp dir) -> strip untrusted CLI config
     -> `gemini --prompt ... --output-format json --approval-mode plan` (argv, no shell)
     -> parse JSON, redact, verify cited paths -> temp dir deleted
     -> ADK synthesis -> user
"""

from google.adk.agents import LlmAgent

from adk_shared.config import advanced_model

from .prompts import ORCHESTRATOR_INSTRUCTION
from .tools import get_gemini_cli_status, run_gemini_cli_analysis

root_agent = LlmAgent(
    name="gemini_cli_orchestrator",
    model=advanced_model(),
    description="Engineering agent that runs the real Gemini CLI on a cloned GitHub "
                "repository and synthesises the results.",
    instruction=ORCHESTRATOR_INSTRUCTION,
    tools=[run_gemini_cli_analysis, get_gemini_cli_status],
)
