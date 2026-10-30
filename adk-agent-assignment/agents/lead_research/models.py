"""Structured outputs for each stage of the lead-research pipeline."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SignalType = Literal[
    "local_hiring", "leadership_hire", "partnership", "local_entity_registration",
    "regulatory_approval", "funding", "localization", "office_or_facility", "customer_wins",
    "product_launch", "event_presence", "other",
]
EvidenceType = Literal["fact", "inference"]


class ResearchBrief(BaseModel):
    target_market: str = Field(description="Country/region the companies expand INTO.")
    industry: str = Field(description="Industry or sector, e.g. 'B2B SaaS', 'fintech'.")
    origin_region: str = Field(default="any", description="Where companies come FROM.")
    seed_company_count: int = Field(default=3, ge=1, le=5,
                                    description="Historical entrants to study (1-5).")
    lead_count: int = Field(default=5, ge=1, le=10, description="Leads to return (1-10).")
    lookback_years: int = Field(default=4, ge=1, le=10)
    exclusions: list[str] = Field(default_factory=list,
                                  description="Companies the user wants excluded.")


class HistoricalEntrant(BaseModel):
    company: str
    headquarters_country: str
    entry_event: str = Field(description="What happened, e.g. 'opened Bengaluru office'.")
    entry_date: str = Field(description="YYYY or YYYY-MM.")
    source_urls: list[str] = Field(default_factory=list)


class HistoricalEntrants(BaseModel):
    entrants: list[HistoricalEntrant]


class Signal(BaseModel):
    signal_type: SignalType
    description: str
    observed_date: str = Field(default="", description="YYYY-MM or YYYY; empty if unknown.")
    months_before_entry: float | None = Field(
        default=None, description="For historical companies: lead time before entry.")
    source_url: str = Field(default="", description="URL supporting this signal.")
    evidence_type: EvidenceType = Field(
        description="fact = directly stated by the source; inference = your interpretation.")


class CompanySignals(BaseModel):
    company: str
    signals: list[Signal]


class HistoricalSignals(BaseModel):
    companies: list[CompanySignals]


class ExpansionPattern(BaseModel):
    pattern_id: str = Field(description="Short id, e.g. P1.")
    signal_type: SignalType
    description: str
    supporting_companies: list[str]
    typical_lead_time_months: float | None = None
    predictive_strength: Literal["high", "medium", "low"]
    caveats: str = ""


class PatternSet(BaseModel):
    patterns: list[ExpansionPattern]
    methodology_notes: str = ""


class CandidateLead(BaseModel):
    company: str
    headquarters_country: str
    description: str
    already_in_target_market: bool = Field(
        description="True if the company already clearly operates in the target market.")
    signals: list[Signal]


class CandidateLeads(BaseModel):
    candidates: list[CandidateLead]


class ScoredLead(BaseModel):
    rank: int
    company: str
    headquarters_country: str
    score: float
    tier: Literal["A", "B", "C", "disqualified"]
    matched_patterns: list[str]
    fact_signals: int
    sourced_signals: int
    grounded_signals: int
    rationale: str
    disqualification_reason: str = ""
    evidence: list[Signal] = Field(default_factory=list)
