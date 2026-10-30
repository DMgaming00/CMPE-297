"""Deterministic scoring stage (custom ADK agent, no model call)."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types
from pydantic import ValidationError

from .callbacks import grounded_domains
from .models import CandidateLeads, PatternSet, ResearchBrief, ScoredLead
from .scoring import rank_leads


def leads_markdown(leads: list[ScoredLead]) -> str:
    if not leads:
        return "No candidate leads were found."
    lines = ["| Rank | Company | HQ | Tier | Score | Patterns | Sourced/grounded | Notes |",
             "|---|---|---|---|---|---|---|---|"]
    for lead in leads:
        rank = str(lead.rank) if lead.rank else "-"
        note = lead.disqualification_reason or lead.rationale
        lines.append(f"| {rank} | {lead.company} | {lead.headquarters_country} | {lead.tier} "
                     f"| {lead.score} | {', '.join(lead.matched_patterns) or '-'} "
                     f"| {lead.sourced_signals}/{lead.grounded_signals} | {note} |")
    details = []
    for lead in leads:
        if lead.tier == "disqualified":
            continue
        ev = "\n".join(f"  - [{s.evidence_type.upper()}] {s.signal_type}: {s.description} "
                       f"({s.observed_date or 'date unknown'}) {s.source_url or '(no source)'}"
                       for s in lead.evidence)
        details.append(f"**{lead.rank}. {lead.company}** - evidence:\n{ev}")
    return "\n".join(lines) + "\n\n" + "\n\n".join(details)


class LeadScoringAgent(BaseAgent):
    """Qualifies, de-duplicates, scores and ranks candidate leads deterministically."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        problems: list[str] = []

        def parse(model, key, default):
            try:
                return model.model_validate(state.get(key) or {})
            except ValidationError:
                problems.append(f"{key} missing or invalid")
                return default

        brief = parse(ResearchBrief, "research_brief", None)
        patterns = parse(PatternSet, "expansion_patterns", PatternSet(patterns=[]))
        candidates = parse(CandidateLeads, "candidate_leads", CandidateLeads(candidates=[]))
        historical = [e.get("company", "") for e in
                      (state.get("historical_entrants") or {}).get("entrants", [])]
        ranked = rank_leads(candidates.candidates, patterns.patterns,
                            historical_companies=historical,
                            exclusions=brief.exclusions if brief else [],
                            grounded_domains=grounded_domains(dict(state)),
                            limit=brief.lead_count if brief else 5)
        qualified = sum(lead.tier != "disqualified" for lead in ranked)
        md = leads_markdown(ranked)
        if problems:
            md = "Pipeline warnings: " + "; ".join(problems) + "\n\n" + md
        yield Event(
            invocation_id=ctx.invocation_id, author=self.name, branch=ctx.branch,
            actions=EventActions(state_delta={
                "scored_leads": [lead.model_dump() for lead in ranked],
                "scored_leads_md": md}),
            content=types.Content(role="model", parts=[types.Part(
                text=f"Scored {len(ranked)} candidate(s): {qualified} qualified.")]))
