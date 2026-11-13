"""Plain-text and Markdown tables for terminal output and README generation."""

from __future__ import annotations

from typing import Any

COLUMNS = [
    ("method", "Method", "{}"),
    ("initial", "Initial", "{:.2f}"),
    ("final", "Final", "{:.2f}"),
    ("improvement", "Improvement", "{:+.2f}"),
    ("success_rate", "Success", "{:.0%}"),
    ("adapt_units", "Adapt units", "{:.0f}"),
    ("deploy_units", "Deploy units", "{:.0f}"),
    ("wall_s", "Time (s)", "{:.2f}"),
]


def summary_table(summary: list[dict[str, Any]], markdown: bool = False) -> str:
    header = [c[1] for c in COLUMNS]
    body = [[fmt.format(row[key]) for key, _, fmt in COLUMNS] for row in summary]
    if markdown:
        lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] + ["---:"] * (len(header) - 1)) + "|"]
        lines += ["| " + " | ".join(r) + " |" for r in body]
        return "\n".join(lines)
    widths = [max(len(h), *(len(r[i]) for r in body)) for i, h in enumerate(header)]
    fmt_row = lambda r: "  ".join(c.ljust(widths[i]) if i == 0 else c.rjust(widths[i]) for i, c in enumerate(r))
    return "\n".join([fmt_row(header), "  ".join("-" * w for w in widths), *map(fmt_row, body)])
