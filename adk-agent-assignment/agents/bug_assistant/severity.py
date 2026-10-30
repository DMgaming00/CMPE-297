"""Deterministic severity rubric (a LOCAL Python function tool - not an MCP tool).

The LLM extracts impact facts from the report; this function turns them into a
priority using a fixed, auditable policy, so equal facts always give equal priority.
"""

from __future__ import annotations

from typing import Literal

UsersAffected = Literal["all", "many", "some", "few", "single"]

SLA = {"P0": "page on-call now; mitigate within 4 hours",
       "P1": "fix within 2 business days",
       "P2": "schedule in the current or next sprint",
       "P3": "backlog / opportunistic fix"}


def assess_severity(
    users_affected: UsersAffected,
    production: bool,
    security_impact: bool = False,
    data_loss_or_corruption: bool = False,
    financial_impact: bool = False,
    workaround_available: bool = False,
    blocks_release: bool = False,
    is_regression: bool = False,
) -> dict:
    """Compute a P0-P3 priority from impact facts using the team's triage policy.

    Args:
        users_affected: Breadth of impact: all, many, some, few or single.
        production: True if the problem occurs in production.
        security_impact: Data exposure, auth bypass, credential leak, injection.
        data_loss_or_corruption: Data lost, corrupted or inconsistent (e.g. negative stock).
        financial_impact: Wrong charges/totals, lost orders or revenue.
        workaround_available: A reasonable workaround exists for affected users.
        blocks_release: Blocks a scheduled release or deployment.
        is_regression: Worked before a recent change.

    Returns:
        priority, numeric score, the contributing factors and the response SLA.
    """
    breadth = {"all": 4, "many": 3, "some": 2, "few": 1, "single": 0}.get(users_affected, 1)
    score = breadth
    factors = [f"breadth={users_affected} (+{breadth})"]
    for flag, weight, label in (
        (production, 2, "production"),
        (security_impact, 4, "security impact"),
        (data_loss_or_corruption, 4, "data loss/corruption"),
        (financial_impact, 3, "financial impact"),
        (blocks_release, 2, "blocks release"),
        (is_regression, 1, "regression"),
    ):
        if flag:
            score += weight
            factors.append(f"{label} (+{weight})")
    if workaround_available:
        score -= 2
        factors.append("workaround available (-2)")

    if production and (security_impact or data_loss_or_corruption):
        priority = "P0"  # hard rule: prod security/data integrity issues are always P0
        factors.append("rule: production security/data-integrity issue => P0")
    elif score >= 9:
        priority = "P0"
    elif score >= 6:
        priority = "P1"
    elif score >= 3:
        priority = "P2"
    else:
        priority = "P3"
    return {"priority": priority, "score": score, "factors": factors, "sla": SLA[priority]}
