"""Structured (key=value) logging used by the CLI and experiment runner."""

from __future__ import annotations

import logging
import sys


def get_logger(name: str = "rsi", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s", "%H:%M:%S"))
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


def kv(**fields: object) -> str:
    """Format fields as ``k=v`` pairs for structured log lines."""
    return " ".join(f"{k}={v}" for k, v in fields.items())
