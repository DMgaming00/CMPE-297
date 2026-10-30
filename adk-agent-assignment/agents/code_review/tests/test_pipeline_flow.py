"""Full review + fix pipeline through ADK's Runner with scripted (fake) models."""

from __future__ import annotations

import json

import pytest
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner

from adk_shared.testing import ScriptedLlm, call, run_turn, text, user_text
from agents.code_review import agent as review_agent

FIXED = '''"""Fixed."""


def average_price(prices):
    """Average of prices; empty input is an error."""
    if not prices:
        raise ValueError("prices must not be empty")
    return sum(prices) / len(prices)
'''


def _walk(agent):
    yield agent
    for sub in getattr(agent, "sub_agents", []):
        yield from _walk(sub)


def _script(scripts: dict[str, list]):
    for node in _walk(review_agent.root_agent):
        if isinstance(node, LlmAgent):
            node.model = ScriptedLlm(script=list(scripts.get(node.name, [])))


def _empty_review() -> str:
    return json.dumps({"summary": "ok", "findings": [], "rejected_static_finding_ids": []})


@pytest.fixture
async def runner():
    r = InMemoryRunner(agent=review_agent.root_agent, app_name="review")
    session = await r.session_service.create_session(app_name="review", user_id="dev")
    return r, session


async def test_review_then_fix_loop(runner):
    r, session = runner
    code = "def average_price(prices):\n    return sum(prices) / len(prices)\n"
    _script({
        "code_review_assistant": [call("transfer_to_agent", agent_name="review_pipeline")],
        "intake": [call("submit_code_for_review", code=code, filename="prices.py"),
                   text("Registered prices.py")],
        "correctness_reviewer": [text(_empty_review())],
        "security_reviewer": [text(_empty_review())],
        "testing_reviewer": [text(_empty_review())],
        "maintainability_reviewer": [text(_empty_review())],
        "report_writer": [text("# Code Review - REQUEST_CHANGES")],
    })
    await run_turn(r, "dev", session.id, user_text(f"Review this:\n{code}"))
    state = (await r.session_service.get_session(app_name="review", user_id="dev",
                                                 session_id=session.id)).state
    assert state["review_verdict"] == "REQUEST_CHANGES"
    assert any(f["rule_id"] == "COR006" for f in state["review_result"]["findings"])
    assert state["correctness_review"]["summary"] == "ok"  # structured output stored

    _script({
        "code_review_assistant": [call("transfer_to_agent", agent_name="fix_pipeline")],
        "fixer": [call("submit_fixed_code", filename="prices.py", code=FIXED),
                  text("submitted")],
        "fix_reporter": [text("All blocking findings resolved.")],
    })
    await run_turn(r, "dev", session.id, user_text("Fix it"))
    state = (await r.session_service.get_session(app_name="review", user_id="dev",
                                                 session_id=session.id)).state
    assert state["fix_status"]["done"] is True
    assert state["fix_status"]["attempt"] == 1  # loop exited early via escalate
    assert "COR006" in state["fix_status"]["resolved_rules"]


async def test_no_code_skips_specialists(runner):
    r, session = runner
    _script({
        "code_review_assistant": [call("transfer_to_agent", agent_name="review_pipeline")],
        "intake": [text("Please paste code or name a file.")],
    })
    await run_turn(r, "dev", session.id, user_text("review my code please"))
    for node in _walk(review_agent.root_agent):
        if node.name.endswith("_reviewer"):
            assert node.model.requests == [], f"{node.name} should not call the model"
