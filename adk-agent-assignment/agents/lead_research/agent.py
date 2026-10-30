"""A) Deep-research lead generation agent.

Phase 1 - learn from the past
  brief_planner -> historical_researcher (Google Search) -> historical_formatter
  -> signal_research_panel (parallel, one researcher per historical company)
  -> signal_formatter -> pattern_synthesizer
Phase 2 - predict
  lead_researcher (Google Search) -> lead_formatter
  -> lead_scoring (deterministic) -> report_writer
Every *_formatter / brief / pattern stage has a Pydantic output_schema; search stages
record grounding metadata so the scorer can tell retrieved sources from invented ones.
"""

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.tools import google_search

from adk_shared.config import advanced_model, fast_model

from . import prompts
from .callbacks import capture_grounding, make_slot_guard
from .models import CandidateLeads, HistoricalEntrants, HistoricalSignals, PatternSet, ResearchBrief
from .stages import LeadScoringAgent

MAX_SEED_COMPANIES = 5


def _structured(name: str, instruction, schema, output_key: str, model: str | None = None
                ) -> LlmAgent:
    return LlmAgent(name=name, model=model or fast_model(), instruction=instruction,
                    output_schema=schema, output_key=output_key, include_contents="none")


def _researcher(name: str, instruction, output_key: str, **kwargs) -> LlmAgent:
    return LlmAgent(name=name, model=fast_model(), instruction=instruction,
                    tools=[google_search], output_key=output_key, include_contents="none",
                    after_model_callback=capture_grounding, **kwargs)


brief_planner = LlmAgent(name="brief_planner", model=fast_model(),
                         instruction=prompts.BRIEF_PLANNER, output_schema=ResearchBrief,
                         output_key="research_brief")

signal_research_panel = ParallelAgent(
    name="signal_research_panel",
    sub_agents=[_researcher(f"signal_researcher_{i + 1}", prompts.make_signal_researcher(i),
                            f"signal_notes_{i}", before_agent_callback=make_slot_guard(i))
                for i in range(MAX_SEED_COMPANIES)],
)

pattern_discovery = SequentialAgent(
    name="pattern_discovery",
    sub_agents=[
        _researcher("historical_researcher", prompts.historical_researcher,
                    "historical_research_notes"),
        _structured("historical_formatter", prompts.historical_formatter, HistoricalEntrants,
                    "historical_entrants"),
        signal_research_panel,
        _structured("signal_formatter", prompts.signal_formatter, HistoricalSignals,
                    "historical_signals"),
        _structured("pattern_synthesizer", prompts.pattern_synthesizer, PatternSet,
                    "expansion_patterns", model=advanced_model()),
    ],
)

lead_generation = SequentialAgent(
    name="lead_generation",
    sub_agents=[
        _researcher("lead_researcher", prompts.lead_researcher, "lead_research_notes"),
        _structured("lead_formatter", prompts.lead_formatter, CandidateLeads,
                    "candidate_leads"),
        LeadScoringAgent(name="lead_scoring"),
        LlmAgent(name="report_writer", model=advanced_model(),
                 instruction=prompts.report_writer, include_contents="none"),
    ],
)

root_agent = SequentialAgent(
    name="deep_research_lead_agent",
    description="Learns pre-expansion signals from companies that entered a market, then "
                "finds and scores new companies showing the same signals.",
    sub_agents=[brief_planner, pattern_discovery, lead_generation],
)
