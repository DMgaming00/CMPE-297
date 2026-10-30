"""OPT-IN integration test against the REAL Gemini CLI and GitHub.

Run with:  RUN_GEMINI_CLI_INTEGRATION=1 pytest -m integration agents/gemini_cli_agent
Requires: `gemini` on PATH and authenticated (GEMINI_API_KEY or Vertex AI), network access.
"""

import os

import pytest

from agents.gemini_cli_agent.tools import run_gemini_cli_analysis

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_GEMINI_CLI_INTEGRATION") != "1",
                       reason="set RUN_GEMINI_CLI_INTEGRATION=1 to run the real Gemini CLI"),
]


async def test_real_gemini_cli_on_small_public_repo():
    result = await run_gemini_cli_analysis("https://github.com/pallets/markupsafe",
                                           "explain_architecture",
                                           focus="Summarise the package layout.")
    assert result["ok"], result.get("error")
    assert result["cited_paths"]["verified"], "expected at least one real file path"
