"""Deterministic scoring/qualification tests (no LLM, no network)."""

from __future__ import annotations

from datetime import date

import pytest

from agents.lead_research.models import CandidateLead, ExpansionPattern, Signal
from agents.lead_research.scoring import (
    normalize_company,
    parse_month,
    rank_leads,
    recency,
    valid_source,
)

TODAY = date(2026, 10, 1)
PATTERNS = [
    ExpansionPattern(pattern_id="P1", signal_type="local_hiring", description="hires",
                     supporting_companies=["A", "B"], predictive_strength="high"),
    ExpansionPattern(pattern_id="P2", signal_type="partnership", description="partners",
                     supporting_companies=["A", "C"], predictive_strength="medium"),
    ExpansionPattern(pattern_id="P3", signal_type="regulatory_approval", description="licence",
                     supporting_companies=["B"], predictive_strength="low"),
]


def sig(kind, url="https://news.example.com/a", when="2026-08", ev="fact"):
    return Signal(signal_type=kind, description=kind, observed_date=when, source_url=url,
                  evidence_type=ev)


def lead(name, signals, in_market=False):
    return CandidateLead(company=name, headquarters_country="US", description="d",
                         already_in_target_market=in_market, signals=signals)


def _rank(cands, **kw):
    kw.setdefault("historical_companies", [])
    kw.setdefault("exclusions", [])
    kw.setdefault("grounded_domains", set())
    return rank_leads(cands, PATTERNS, today=TODAY, **kw)


def test_full_pattern_coverage_with_fresh_sourced_facts_scores_tier_a():
    [top] = _rank([lead("Acme", [sig("local_hiring"), sig("partnership"),
                                 sig("regulatory_approval")])])
    assert top.score == 100.0 and top.tier == "A" and top.rank == 1
    assert top.matched_patterns == ["P1", "P2", "P3"]


def test_ranking_prefers_more_and_stronger_patterns():
    ranked = _rank([lead("Weak", [sig("regulatory_approval")]),
                    lead("Strong", [sig("local_hiring"), sig("partnership")])])
    assert [r.company for r in ranked] == ["Strong", "Weak"]
    assert ranked[0].score > ranked[1].score


def test_inference_and_unsourced_signals_reduce_score():
    good = _rank([lead("G", [sig("local_hiring")])])[0]
    inferred = _rank([lead("I", [sig("local_hiring"), sig("partnership", ev="inference")])])[0]
    unsourced = _rank([lead("U", [sig("local_hiring"), sig("partnership", url="")])])[0]
    assert good.score > 0 and inferred.tier != "disqualified" and unsourced.tier != "disqualified"
    assert _rank([lead("X", [sig("local_hiring", ev="inference")])])[0].tier == "disqualified"


def test_grounded_sources_get_bonus_and_are_counted():
    signals = [sig("local_hiring", url="https://www.reuters.com/x", ev="fact")]
    plain = _rank([lead("A", signals)])[0]
    grounded = _rank([lead("A", signals)], grounded_domains={"reuters.com"})[0]
    assert grounded.grounded_signals == 1 and plain.grounded_signals == 0
    assert grounded.score >= plain.score


@pytest.mark.parametrize("kwargs,company,in_market,reason", [
    ({}, "Already", True, "already operates"),
    ({"historical_companies": ["Stripe, Inc."]}, "stripe", False, "historical entrants"),
    ({"exclusions": ["Globex Corp"]}, "Globex", False, "excluded"),
])
def test_disqualification_rules(kwargs, company, in_market, reason):
    [r] = _rank([lead(company, [sig("local_hiring")], in_market)], **kwargs)
    assert r.tier == "disqualified" and r.score == 0 and reason in r.disqualification_reason
    assert r.rank == 0


def test_duplicates_collapse_and_limit_applies():
    cands = [lead("Acme Inc.", [sig("local_hiring")]),
             lead("ACME", [sig("local_hiring"), sig("partnership")]),
             lead("Beta", [sig("partnership")]), lead("Gamma", [sig("regulatory_approval")])]
    ranked = _rank(cands, limit=2)
    names = [r.company for r in ranked]
    assert names == ["ACME", "Beta"]  # Acme de-duplicated (best kept), Gamma cut by limit


def test_scoring_is_deterministic():
    cands = [lead("A", [sig("local_hiring")]), lead("B", [sig("partnership")])]
    assert [r.model_dump() for r in _rank(cands)] == [r.model_dump() for r in _rank(cands)]


def test_helpers():
    assert normalize_company("Globex Corporation Ltd.") == normalize_company("globex")
    assert valid_source("https://example.org/x") and not valid_source("not a url")
    assert not valid_source("javascript:alert(1)") and not valid_source("ftp://x.org/f")
    assert parse_month("2025-03") == date(2025, 3, 1) and parse_month("soon") is None
    assert recency(sig("other", when="2026-09"), TODAY) == 1.0
    assert recency(sig("other", when="2025-06"), TODAY) == 0.6
    assert recency(sig("other", when="2020"), TODAY) == 0.3
    assert recency(sig("other", when="2030-01"), TODAY) == 0.4  # future-dated: suspicious
