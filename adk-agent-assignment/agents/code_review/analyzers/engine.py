"""Runs every analyzer over submitted files and renders a numbered code listing."""

from __future__ import annotations

import ast

from ..models import SEVERITY_ORDER, FileMetrics, Finding, StaticReport
from .correctness import check_correctness, mark_with_items
from .maintainability import check_maintainability
from .security import check_security
from .style import check_style
from .testing import check_tests

MAX_LISTING_CHARS = 60_000


def analyze_files(files: dict[str, str]) -> StaticReport:
    """Statically analyse Python sources. Code is parsed, never imported or executed."""
    findings: list[Finding] = []
    metrics: list[FileMetrics] = []
    trees: dict[str, ast.AST | None] = {}
    for filename, source in files.items():
        style_findings, violations, score = check_style(source, filename)
        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError as exc:
            trees[filename] = None
            findings.append(Finding(
                rule_id="COR000", severity="P0", category="correctness", file=filename,
                line=max(exc.lineno or 1, 1), title=f"Syntax error: {exc.msg}",
                explanation="The file cannot be parsed, so it cannot run or be analysed.",
                recommendation="Fix the syntax error first."))
            metrics.append(FileMetrics(file=filename, lines=len(source.splitlines()),
                                       functions=0, classes=0, max_complexity=0,
                                       style_violations=violations, style_score=score,
                                       parse_error=f"line {exc.lineno}: {exc.msg}"))
            continue
        trees[filename] = tree
        mark_with_items(tree)
        findings += check_security(tree, filename)
        findings += check_correctness(tree, filename)
        mnt, max_cc = check_maintainability(tree, filename)
        findings += mnt + style_findings
        metrics.append(FileMetrics(
            file=filename, lines=len(source.splitlines()),
            functions=sum(isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
                          for n in ast.walk(tree)),
            classes=sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree)),
            max_complexity=max_cc, style_violations=violations, style_score=score))
    test_findings, plan = check_tests(trees)
    findings += test_findings
    return StaticReport(findings=dedupe(findings), metrics=metrics, test_plan=plan)


def dedupe(findings: list[Finding]) -> list[Finding]:
    """Keep one finding per (file, line, rule) and sort by severity then location."""
    unique: dict[tuple[str, int, str], Finding] = {}
    for f in findings:
        key = (f.file, f.line, f.rule_id)
        if key not in unique or SEVERITY_ORDER[f.severity] < SEVERITY_ORDER[
                unique[key].severity]:
            unique[key] = f
    return sorted(unique.values(),
                  key=lambda f: (SEVERITY_ORDER[f.severity], f.file, f.line, f.rule_id))


def render_listing(files: dict[str, str]) -> str:
    """Numbered listing used by LLM reviewers so they can cite exact lines."""
    parts = []
    for filename, source in files.items():
        numbered = "\n".join(f"{i:>4} | {line}" for i, line in
                             enumerate(source.splitlines(), start=1))
        parts.append(f"=== FILE: {filename} ===\n{numbered}")
    listing = "\n\n".join(parts)
    if len(listing) > MAX_LISTING_CHARS:
        listing = listing[:MAX_LISTING_CHARS] + "\n... [listing truncated] ..."
    return listing
