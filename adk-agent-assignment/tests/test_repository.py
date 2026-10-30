"""Repository-level checks: agents load, docs exist, no video/secret artifacts."""

from __future__ import annotations

import re
import subprocess
import sys

import pytest

from adk_shared.config import REPO_ROOT

AGENTS = {"lead_research": "deep_research_lead_agent",
          "gemini_cli_agent": "gemini_cli_orchestrator",
          "bug_assistant": "software_bug_assistant",
          "code_review": "code_review_assistant",
          "ecommerce": "ecommerce_agent"}


@pytest.mark.parametrize("package,root_name", AGENTS.items())
def test_agents_load_like_adk_web(package, root_name):
    """Import each agent in a fresh interpreter, the way `adk web agents` does."""
    code = (f"import sys; sys.path.insert(0, 'agents'); import {package}.agent as a; "
            f"print(a.root_agent.name)")
    out = subprocess.run([sys.executable, "-W", "ignore", "-c", code], cwd=REPO_ROOT,
                         capture_output=True, text=True, timeout=120, check=True,
                         stdin=subprocess.DEVNULL)
    assert out.stdout.strip().splitlines()[-1] == root_name


@pytest.mark.parametrize("package", AGENTS)
def test_each_agent_has_readme(package):
    readme = REPO_ROOT / "agents" / package / "README.md"
    assert readme.exists() and len(readme.read_text()) > 1500


def test_no_video_or_recording_material():
    pattern = re.compile(r"(youtube|video|recording|script)[^/]*\.md$", re.I)
    offenders = [p for p in REPO_ROOT.rglob("*.md")
                 if ".venv" not in p.parts and pattern.search(p.name)]
    assert not offenders, offenders


def test_env_example_contains_only_placeholders():
    text = (REPO_ROOT / ".env.example").read_text()
    assert not re.search(r"AIza[0-9A-Za-z_\-]{35}|gh[pousr]_[0-9A-Za-z]{30,}|ya29\.", text)
    assert "GOOGLE_API_KEY=your-gemini-api-key" in text


def test_gitignore_covers_secrets_and_local_state():
    text = (REPO_ROOT / ".gitignore").read_text()
    for entry in (".env", ".venv/", "__pycache__/", ".local_state/", "*.sqlite"):
        assert entry in text
