"""Callbacks: record Google Search grounding metadata and skip unused research slots."""

from __future__ import annotations

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.genai import types

GROUNDING_PREFIX = "grounding_"
MAX_SOURCES_PER_AGENT = 100


def capture_grounding(callback_context: CallbackContext,
                      llm_response: LlmResponse) -> LlmResponse | None:
    """after_model_callback: store the web sources Google Search actually returned.

    Grounding chunk titles are source domains (the URIs are redirect links), so the
    scoring stage can check whether a cited URL's domain was really retrieved.
    """
    metadata = llm_response.grounding_metadata
    if metadata is None:
        return None
    key = GROUNDING_PREFIX + callback_context.agent_name
    sources = list(callback_context.state.get(key) or [])
    seen = {s.get("title") for s in sources}
    for chunk in metadata.grounding_chunks or []:
        web = chunk.web
        if web is None or not web.title or web.title in seen:
            continue
        sources.append({"title": web.title, "uri": web.uri or ""})
        seen.add(web.title)
    queries = list(callback_context.state.get("search_queries") or [])
    queries += [q for q in (metadata.web_search_queries or []) if q not in queries]
    callback_context.state[key] = sources[:MAX_SOURCES_PER_AGENT]
    callback_context.state["search_queries"] = queries[:50]
    return None


def grounded_domains(state: dict) -> set[str]:
    domains: set[str] = set()
    for key, value in state.items():
        if key.startswith(GROUNDING_PREFIX) and isinstance(value, list):
            for source in value:
                title = str(source.get("title", "")).lower().strip()
                if title:
                    domains.add(title[4:] if title.startswith("www.") else title)
    return domains


def make_slot_guard(index: int):
    """before_agent_callback: skip signal-research slot ``index`` if there is no company."""

    def guard(callback_context: CallbackContext) -> types.Content | None:
        entrants = (callback_context.state.get("historical_entrants") or {}).get("entrants", [])
        brief = callback_context.state.get("research_brief") or {}
        wanted = int(brief.get("seed_company_count", 3))
        if index >= min(len(entrants), wanted):
            return types.Content(role="model", parts=[types.Part(text="NO_COMPANY")])
        return None

    return guard
