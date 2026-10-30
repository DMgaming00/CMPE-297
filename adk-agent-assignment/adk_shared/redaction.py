"""Best-effort secret redaction for anything that may be logged or returned to a model."""

from __future__ import annotations

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"AIza[0-9A-Za-z_\-]{35}"), "[REDACTED_GOOGLE_API_KEY]"),
    (re.compile(r"\bgh[pousr]_[0-9A-Za-z]{36,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bgithub_pat_[0-9A-Za-z_]{40,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\bya29\.[0-9A-Za-z_\-]{20,}"), "[REDACTED_OAUTH_TOKEN]"),
    (re.compile(r"\bxox[abprs]-[0-9A-Za-z\-]{10,}"), "[REDACTED_SLACK_TOKEN]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
     "[REDACTED_PRIVATE_KEY]"),
    # user:password@ in URLs
    (re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+@"), "[REDACTED_CREDENTIALS]@"),
]


def redact_secrets(text: str) -> str:
    """Replace well-known credential formats with placeholders."""
    if not text:
        return text
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
