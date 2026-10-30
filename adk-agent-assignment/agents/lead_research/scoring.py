"""Deterministic lead qualification and scoring.

The LLM finds and describes evidence; this module decides the ranking, so the same
evidence always yields the same score and every point is explainable.

score (0-100) = 55 * pattern_coverage + 25 * evidence_quality + 20 * recency
  pattern_coverage  weighted share of discovered patterns the lead matches
                    (high=3, medium=2, low=1)
  evidence_quality  mean per-signal quality: fact with a valid source URL = 1.0,
                    fact without URL = 0.4, inference = 0.2; +0.1 bonus (capped at 1.0)
                    when the URL's domain appeared in Google Search grounding metadata
  recency           mean per-signal recency: <=12 months 1.0, <=24 months 0.6,
                    older 0.3, unknown 0.4
Disqualified (score 0): already in the target market, one of the historical companies
studied, excluded by the user, or no fact-type signal with a source URL.
Tiers: A >= 65, B >= 45, otherwise C.
"""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlsplit

from .models import CandidateLead, ExpansionPattern, ScoredLead, Signal

STRENGTH_WEIGHT = {"high": 3.0, "medium": 2.0, "low": 1.0}
_SUFFIXES = re.compile(r"\b(inc|incorporated|ltd|limited|llc|plc|gmbh|ag|sa|corp|"
                       r"corporation|co|company|holdings|group)\b\.?")


def normalize_company(name: str) -> str:
    name = _SUFFIXES.sub("", name.lower())
    return re.sub(r"[^a-z0-9]+", "", name)


def valid_source(url: str) -> bool:
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return False
    return parts.scheme in {"http", "https"} and "." in (parts.hostname or "")


def domain(url: str) -> str:
    host = (urlsplit(url.strip()).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def parse_month(value: str) -> date | None:
    match = re.match(r"^\s*(\d{4})(?:-(\d{1,2}))?", value or "")
    if not match:
        return None
    year, month = int(match.group(1)), int(match.group(2) or 6)
    if not 1990 <= year <= 2100 or not 1 <= month <= 12:
        return None
    return date(year, month, 1)


def signal_quality(signal: Signal, grounded_domains: set[str]) -> tuple[float, bool]:
    sourced = valid_source(signal.source_url)
    quality = 0.2 if signal.evidence_type == "inference" else 1.0 if sourced else 0.4
    grounded = sourced and _is_grounded(signal.source_url, grounded_domains)
    if grounded and signal.evidence_type == "fact":
        quality = min(1.0, quality + 0.1)
    return quality, grounded


def _is_grounded(url: str, grounded_domains: set[str]) -> bool:
    d = domain(url)
    return any(d == g or d.endswith("." + g) or g.endswith("." + d) for g in grounded_domains)


def recency(signal: Signal, today: date) -> float:
    observed = parse_month(signal.observed_date)
    if observed is None:
        return 0.4
    months = (today.year - observed.year) * 12 + (today.month - observed.month)
    if months < -1:
        return 0.4  # future-dated evidence is suspicious
    if months <= 12:
        return 1.0
    return 0.6 if months <= 24 else 0.3


def score_lead(lead: CandidateLead, patterns: list[ExpansionPattern], *,
               historical: set[str], exclusions: set[str], grounded_domains: set[str],
               today: date) -> ScoredLead:
    key = normalize_company(lead.company)
    total_weight = sum(STRENGTH_WEIGHT[p.predictive_strength] for p in patterns) or 1.0
    lead_types = {s.signal_type for s in lead.signals}
    matched = [p for p in patterns if p.signal_type in lead_types]
    coverage = sum(STRENGTH_WEIGHT[p.predictive_strength] for p in matched) / total_weight

    qualities, groundings = [], 0
    for s in lead.signals:
        q, g = signal_quality(s, grounded_domains)
        qualities.append(q)
        groundings += g
    quality = sum(qualities) / len(qualities) if qualities else 0.0
    fresh = (sum(recency(s, today) for s in lead.signals) / len(lead.signals)
             if lead.signals else 0.0)
    facts = sum(s.evidence_type == "fact" for s in lead.signals)
    sourced_facts = sum(s.evidence_type == "fact" and valid_source(s.source_url)
                        for s in lead.signals)
    sourced = sum(valid_source(s.source_url) for s in lead.signals)

    reason = ""
    if lead.already_in_target_market:
        reason = "already operates in the target market"
    elif key in historical:
        reason = "is one of the historical entrants used to learn the patterns"
    elif key in exclusions:
        reason = "excluded by the user"
    elif sourced_facts == 0:
        reason = "no sourced, factual signal (only inferences or unsourced claims)"

    score = 0.0 if reason else round(55 * coverage + 25 * quality + 20 * fresh, 1)
    tier = "disqualified" if reason else ("A" if score >= 65 else "B" if score >= 45 else "C")
    rationale = (
        f"Matches {len(matched)}/{len(patterns)} patterns "
        f"({', '.join(p.pattern_id for p in matched) or 'none'}); "
        f"{sourced_facts} sourced fact(s), {groundings} grounded in search results; "
        f"coverage={coverage:.2f}, quality={quality:.2f}, recency={fresh:.2f}."
    )
    return ScoredLead(rank=0, company=lead.company,
                      headquarters_country=lead.headquarters_country, score=score, tier=tier,
                      matched_patterns=[p.pattern_id for p in matched], fact_signals=facts,
                      sourced_signals=sourced, grounded_signals=groundings,
                      rationale=rationale, disqualification_reason=reason,
                      evidence=lead.signals)


def rank_leads(candidates: list[CandidateLead], patterns: list[ExpansionPattern], *,
               historical_companies: list[str], exclusions: list[str],
               grounded_domains: set[str], today: date | None = None,
               limit: int = 10) -> list[ScoredLead]:
    today = today or date.today()
    historical = {normalize_company(c) for c in historical_companies}
    excluded = {normalize_company(c) for c in exclusions}
    best: dict[str, ScoredLead] = {}
    for lead in candidates:
        scored = score_lead(lead, patterns, historical=historical, exclusions=excluded,
                            grounded_domains=grounded_domains, today=today)
        key = normalize_company(lead.company)
        if key not in best or scored.score > best[key].score:  # de-duplicate companies
            best[key] = scored
    ordered = sorted(best.values(), key=lambda s: (s.tier == "disqualified", -s.score,
                                                   -s.sourced_signals, s.company.lower()))
    qualified = [s for s in ordered if s.tier != "disqualified"][:limit]
    disqualified = [s for s in ordered if s.tier == "disqualified"]
    for i, lead in enumerate(qualified, start=1):
        lead.rank = i
    return qualified + disqualified
