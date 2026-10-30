"""Structured, secret-safe logging helpers for tool invocations."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from .redaction import redact_secrets

_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    global _CONFIGURED
    if not _CONFIGURED:
        logging.basicConfig(
            level=os.getenv("LOG_LEVEL", "INFO").upper(),
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        _CONFIGURED = True
    return logging.getLogger(name)


def _summarize(value: Any, limit: int = 160) -> Any:
    if isinstance(value, str):
        value = redact_secrets(value)
        return value if len(value) <= limit else value[:limit] + f"...(+{len(value) - limit} chars)"
    if isinstance(value, dict):
        return {k: _summarize(v, limit) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_summarize(v, limit) for v in value[:10]]
    return value


def log_tool_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Log one JSON line with long strings truncated and secrets redacted."""
    logger.info("%s %s", event, json.dumps(_summarize(fields), default=str, sort_keys=True))
