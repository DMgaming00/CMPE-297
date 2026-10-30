"""Pipeline tests: callbacks, structure, and a full scripted run through ADK's Runner."""

from __future__ import annotations

import json
from types import SimpleNamespace

from google.adk.agents import LlmAgent
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import types

from adk_shared.testing import ScriptedLlm, run_turn, text, user_text
from agents.lead_research import agent as lead_agent
from agents.lead_research.callbacks import capture_grounding, grounded_domains, make_slot_guard


def _walk(node):
    yield node
    for sub in getattr(node, "sub_agents", []):
        yield from _walk(sub)


def test_pipeline_structure():
    names = [n.name for n in _walk(lead_agent.root_agent)]
    order = ["brief_planner", "historical_researcher", "historical_formatter",
             "signal_research_panel", "signal_formatter", "pattern_synthesizer",
             "lead_researcher", "lead_formatter", "lead_scoring", "report_writer"]
    assert [n for n in names if n in order] == order
    for node in _walk(lead_agent.root_agent):
        if isinstance(node, LlmAgent):
            uses_search = any(getattr(t, "name", "") == "google_search" for t in node.tools)
            assert uses_search == node.name.endswith("researcher") or "signal_researcher" in \
                node.name, node.name
            if node.name.endswith("formatter") or node.name in {"brief_planner",
                                                                 "pattern_synthesizer"}:
                assert node.output_schema is not None, node.name


def test_capture_grounding_records_domains():
    state: dict = {}
    ctx = SimpleNamespace(state=state, agent_name="lead_researcher")
    response = LlmResponse(grounding_metadata=types.GroundingMetadata(
        grounding_chunks=[types.GroundingChunk(web=types.GroundingChunkWeb(
            title="reuters.com", uri="https://vertexaisearch.cloud.google.com/redirect/1")),
            types.GroundingChunk(web=types.GroundingChunkWeb(title="www.ft.com", uri="u"))],
        web_search_queries=["saas india expansion"]))
    capture_grounding(ctx, response)
    assert grounded_domains(state) == {"reuters.com", "ft.com"}
    assert state["search_queries"] == ["saas india expansion"]


def test_slot_guard_skips_missing_companies():
    state = {"historical_entrants": {"entrants": [{"company": "A"}, {"company": "B"}]},
             "research_brief": {"seed_company_count": 3}}
    ctx = SimpleNamespace(state=state)
    assert make_slot_guard(1)(ctx) is None
    assert make_slot_guard(2)(ctx).parts[0].text == "NO_COMPANY"


def _j(obj) -> types.Part:
    return text(json.dumps(obj))


async def test_full_pipeline_with_scripted_models():
    """Exercises every stage, schema and state hand-off. Search is disabled and models are
    scripted - this proves the orchestration, not research quality."""
    src = "https://www.reuters.com/x"
    sig = {"signal_type": "local_hiring", "description": "Hiring in Bengaluru",
           "observed_date": "2026-08", "source_url": src, "evidence_type": "fact"}
    scripts = {
        "brief_planner": [_j({"target_market": "India", "industry": "B2B SaaS",
                              "seed_company_count": 2, "lead_count": 2})],
        "historical_researcher": [text("Alpha opened Bengaluru office 2024 ...")],
        "historical_formatter": [_j({"entrants": [
            {"company": "Alpha", "headquarters_country": "US", "entry_event": "office",
             "entry_date": "2024-05", "source_urls": [src]},
            {"company": "Beta", "headquarters_country": "UK", "entry_event": "entity",
             "entry_date": "2023", "source_urls": [src]}]})],
        "signal_researcher_1": [text("Alpha hired locally 6 months before")],
        "signal_researcher_2": [text("Beta partnered with Infosys")],
        "signal_formatter": [_j({"companies": [{"company": "Alpha", "signals": [sig]}]})],
        "pattern_synthesizer": [_j({"patterns": [
            {"pattern_id": "P1", "signal_type": "local_hiring", "description": "hire first",
             "supporting_companies": ["Alpha", "Beta"], "predictive_strength": "high"}]})],
        "lead_researcher": [text("Gamma is hiring in India; Alpha too")],
        "lead_formatter": [_j({"candidates": [
            {"company": "Gamma", "headquarters_country": "DE", "description": "d",
             "already_in_target_market": False, "signals": [sig]},
            {"company": "Alpha", "headquarters_country": "US", "description": "d",
             "already_in_target_market": True, "signals": [sig]}]})],
        "report_writer": [text("# Lead Intelligence Report")],
    }
    for node in _walk(lead_agent.root_agent):
        if isinstance(node, LlmAgent):
            node.model = ScriptedLlm(script=list(scripts.get(node.name, [])))
            node.tools = []  # no live Google Search in unit tests

    runner = InMemoryRunner(agent=lead_agent.root_agent, app_name="leads")
    session = await runner.session_service.create_session(app_name="leads", user_id="u")
    await run_turn(runner, "u", session.id, user_text("Find SaaS companies likely to enter "
                                                      "India"))
    state = (await runner.session_service.get_session(app_name="leads", user_id="u",
                                                      session_id=session.id)).state
    ranked = state["scored_leads"]
    assert ranked[0]["company"] == "Gamma" and ranked[0]["rank"] == 1
    assert ranked[1]["tier"] == "disqualified"
    assert state["signal_notes_2"] == "NO_COMPANY" or "signal_notes_2" not in state
    called = {n.name for n in _walk(lead_agent.root_agent)
              if isinstance(n, LlmAgent) and n.model.requests}
    assert "signal_researcher_3" not in called  # skipped slot made no model call
