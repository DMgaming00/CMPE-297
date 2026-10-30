"""Deterministic (non-LLM) pipeline stages implemented as custom ADK agents."""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from .analyzers import analyze_files, render_listing
from .models import SEVERITY_ORDER, Finding, SpecialistReview, StaticReport
from .tools import FILES_KEY, FIX_FILES_KEY

SPECIALIST_KEYS = {
    "correctness_review": "correctness",
    "security_review": "security",
    "testing_review": "testing",
    "maintainability_review": "maintainability",
}
MAX_REPORTED_FINDINGS = 25


def _event(agent: BaseAgent, ctx: InvocationContext, message: str, state: dict[str, Any],
           escalate: bool = False) -> Event:
    return Event(invocation_id=ctx.invocation_id, author=agent.name, branch=ctx.branch,
                 actions=EventActions(state_delta=state, escalate=escalate or None),
                 content=types.Content(role="model", parts=[types.Part(text=message)]))


def findings_markdown(findings: list[Finding]) -> str:
    if not findings:
        return "No findings."
    rows = ["| # | Severity | Category | Location | Finding | Source |",
            "|---|---|---|---|---|---|"]
    details = []
    for i, f in enumerate(findings, start=1):
        rows.append(f"| {i} | {f.severity} | {f.category} | `{f.file}:{f.line}` | {f.title} "
                    f"| {f.source}/{f.confidence} |")
        details.append(f"**{i}. [{f.severity}] {f.title}** (`{f.file}:{f.line}`, id "
                       f"`{f.id}`)\n- Why: {f.explanation}\n- Fix: {f.recommendation}")
    return "\n".join(rows) + "\n\n" + "\n\n".join(details)


def verdict_for(findings: list[Finding]) -> str:
    severities = {f.severity for f in findings}
    if severities & {"P0", "P1"}:
        return "REQUEST_CHANGES"
    if "P2" in severities:
        return "COMMENT"
    return "APPROVE"


def start_new_review(callback_context: CallbackContext) -> None:
    """before_agent_callback for intake: each review pipeline run starts from scratch."""
    callback_context.state[FILES_KEY] = {}
    return None


def skip_specialist_if_no_code(callback_context: CallbackContext) -> types.Content | None:
    """before_agent_callback: skip the model call (schema-valid empty review) if no code."""
    if not callback_context.state.get("review_ready"):
        empty = SpecialistReview(summary="Skipped: no code submitted.").model_dump_json()
        return types.Content(role="model", parts=[types.Part(text=empty)])
    return None


def skip_if_no_code(callback_context: CallbackContext) -> types.Content | None:
    """before_agent_callback for text agents: answer directly when no code was given."""
    if not callback_context.state.get("review_ready"):
        return types.Content(role="model", parts=[types.Part(
            text="I need code to review: paste Python code, or name a file from the review "
                 "workspace (ask me to list the available files).")])
    return None


class StaticAnalysisAgent(BaseAgent):
    """Runs AST/security/style/test-gap analyzers over the submitted files."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        files: dict[str, str] = ctx.session.state.get(FILES_KEY) or {}
        if not files:
            yield _event(self, ctx, "No code was submitted for review.",
                         {"review_ready": False, "review_listing": "", "static_findings_md": "",
                          "static_report": {}, "test_plan_md": ""})
            return
        report = analyze_files(files)
        plan = "\n".join(f"- {fn}: " + "; ".join(ideas) for fn, ideas in
                         report.test_plan.items()) or "- (no untested public functions)"
        counts = {s: sum(f.severity == s for f in report.findings) for s in SEVERITY_ORDER}
        yield _event(self, ctx,
                     f"Static analysis of {len(files)} file(s): {len(report.findings)} findings "
                     f"({', '.join(f'{k}={v}' for k, v in counts.items())}).",
                     {"review_ready": True,
                      "fix_files": {}, "fix_attempts": 0, "fix_feedback": "",
                      "review_listing": render_listing(files),
                      "static_report": report.model_dump(),
                      "static_findings_md": findings_markdown(report.findings),
                      "test_plan_md": plan})


def _normalise(code: str) -> str:
    return re.sub(r"\s+", "", code)


def validate_specialist_findings(review: SpecialistReview, files: dict[str, str]
                                 ) -> tuple[list[Finding], list[str]]:
    """Keep only LLM findings that point at real lines and quote real code."""
    accepted, dropped = [], []
    for item in review.findings:
        source = files.get(item.file)
        if source is None:
            dropped.append(f"{item.title}: unknown file {item.file}")
            continue
        lines = source.splitlines()
        if not 1 <= item.line <= len(lines):
            dropped.append(f"{item.title}: line {item.line} out of range")
            continue
        evidence = _normalise(item.evidence)
        window = _normalise("\n".join(lines[max(0, item.line - 4):item.line + 3]))
        if evidence and evidence not in _normalise(source):
            dropped.append(f"{item.title}: evidence not found in {item.file}")
            continue
        confidence = item.confidence if evidence and evidence in window else "low"
        accepted.append(Finding(
            rule_id=f"LLM-{item.category[:3].upper()}", title=item.title,
            severity=item.severity, category=item.category, file=item.file, line=item.line,
            explanation=item.explanation, recommendation=item.recommendation,
            confidence=confidence, source="llm"))
    return accepted, dropped


def synthesize(state: dict[str, Any]) -> dict[str, Any]:
    files: dict[str, str] = state.get(FILES_KEY) or {}
    static = StaticReport.model_validate(state.get("static_report") or
                                         {"findings": [], "metrics": []})
    findings = list(static.findings)
    by_id = {f.id: f for f in findings}
    dropped: list[str] = []
    disputed: list[str] = []
    llm_findings: list[Finding] = []
    for key, specialty in SPECIALIST_KEYS.items():
        raw = state.get(key)
        if not raw:
            continue
        try:
            review = SpecialistReview.model_validate(raw)
        except ValueError:
            dropped.append(f"{key}: malformed specialist output ignored")
            continue
        for fid in review.rejected_static_finding_ids:
            finding = by_id.get(fid)
            if finding is None or finding.category != specialty:
                continue
            # Code comments can try to talk a model out of a real finding, so a model can
            # never remove a high-confidence P0/P1 static finding - it is only marked disputed.
            if finding.confidence == "high" and finding.severity in {"P0", "P1"}:
                finding.explanation += f" (Disputed by the {specialty} reviewer; kept.)"
                disputed.append(fid)
            else:
                findings.remove(finding)
                by_id.pop(fid)
                dropped.append(f"{fid}: rejected by {specialty} reviewer")
        accepted, rejected = validate_specialist_findings(review, files)
        llm_findings += accepted
        dropped += rejected
    for candidate in llm_findings:
        overlaps = any(f.file == candidate.file and abs(f.line - candidate.line) <= 2
                       and f.category == candidate.category for f in findings)
        if not overlaps:
            findings.append(candidate)
    findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.file, f.line))
    reported = findings[:MAX_REPORTED_FINDINGS]
    counts = {s: sum(f.severity == s for f in findings) for s in SEVERITY_ORDER}
    return {
        "verdict": verdict_for(findings),
        "counts": counts,
        "findings": [f.model_dump() for f in reported],
        "omitted": max(0, len(findings) - len(reported)),
        "dropped_llm_or_rejected": dropped,
        "disputed": disputed,
        "metrics": [m.model_dump() for m in static.metrics],
    }


class FindingsSynthesisAgent(BaseAgent):
    """Merges static + specialist findings, de-duplicates, ranks and picks the verdict."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        if not ctx.session.state.get("review_ready"):
            yield _event(self, ctx, "Nothing to synthesise.", {"review_result": {},
                                                               "review_findings_md": ""})
            return
        result = synthesize(dict(ctx.session.state))
        findings = [Finding.model_validate(f) for f in result["findings"]]
        md = findings_markdown(findings)
        if result["omitted"]:
            md += f"\n\n_{result['omitted']} lower-severity finding(s) omitted._"
        yield _event(self, ctx, f"Verdict: {result['verdict']} {result['counts']}",
                     {"review_result": result, "review_verdict": result["verdict"],
                      "review_findings_md": md})


class FixValidationAgent(BaseAgent):
    """Re-runs static analysis on proposed fixes; exits the loop when P0/P1 are gone."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        originals: dict[str, str] = ctx.session.state.get(FILES_KEY) or {}
        fixes: dict[str, str] = ctx.session.state.get(FIX_FILES_KEY) or {}
        attempts = int(ctx.session.state.get("fix_attempts", 0)) + 1
        if not fixes:
            yield _event(self, ctx, "No fix submitted yet.",
                         {"fix_attempts": attempts,
                          "fix_feedback": "No fixed code was submitted. Call submit_fixed_code."})
            return
        before = analyze_files(originals)
        after = analyze_files({**originals, **fixes})
        blocking = [f for f in after.findings if f.severity in {"P0", "P1"}]
        parse_errors = [m.file for m in after.metrics if m.parse_error]
        resolved = sorted({f.rule_id for f in before.findings} - {f.rule_id for f in
                                                                  after.findings})
        done = not blocking and not parse_errors
        status = {
            "attempt": attempts, "done": done,
            "before": {s: sum(f.severity == s for f in before.findings) for s in SEVERITY_ORDER},
            "after": {s: sum(f.severity == s for f in after.findings) for s in SEVERITY_ORDER},
            "resolved_rules": resolved,
            "remaining_blocking": [f"{f.id}: {f.title}" for f in blocking],
            "parse_errors": parse_errors,
        }
        feedback = ("All P0/P1 findings resolved." if done else
                    "Still blocking:\n" + "\n".join(f"- {b}" for b in
                                                     status["remaining_blocking"] + parse_errors))
        yield _event(self, ctx, f"Fix attempt {attempts}: {'PASS' if done else 'RETRY'}",
                     {"fix_attempts": attempts, "fix_status": status, "fix_feedback": feedback,
                      "fixed_listing": render_listing(fixes)},
                     escalate=done)
