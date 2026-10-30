"""PEP 8 checks via pycodestyle on in-memory lines (no temp files, no imports)."""

from __future__ import annotations

from collections import Counter

import pycodestyle

from ..models import Finding


class _Collector(pycodestyle.BaseReport):
    def __init__(self, options: object) -> None:
        super().__init__(options)
        self.items: list[tuple[int, str, str]] = []

    def error(self, line_number, offset, text, check):
        code = text[:4]
        if self._ignore_code(code):
            return None
        self.items.append((line_number, code, text[5:]))
        return super().error(line_number, offset, text, check)


def check_style(source: str, filename: str, max_line_length: int = 100
                ) -> tuple[list[Finding], int, int]:
    """Return (findings, violation_count, score 0-100)."""
    style = pycodestyle.StyleGuide(quiet=True, max_line_length=max_line_length,
                                   reporter=_Collector)
    lines = source.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    checker = pycodestyle.Checker(filename=filename, lines=lines, options=style.options)
    checker.check_all()
    items = checker.report.items  # type: ignore[attr-defined]
    total = len(items)
    score = max(0, 100 - round(total * 200 / max(len(lines), 20)))
    if not items:
        return [], 0, 100
    counts = Counter(code for _, code, _ in items)
    top = ", ".join(f"{code} x{n}" for code, n in counts.most_common(5))
    examples = "; ".join(f"line {ln}: {code} {msg}" for ln, code, msg in items[:5])
    finding = Finding(rule_id="STY001", severity="P3", category="style", file=filename,
                      line=items[0][0], title=f"{total} PEP 8 violation(s) (score {score}/100)",
                      explanation=f"Most frequent: {top}. Examples: {examples}.",
                      recommendation="Run an auto-formatter (ruff format / black) and a linter "
                                     "in CI.", confidence="high")
    return [finding], total, score
