"""Environment-driven configuration shared by every agent.

All agents read configuration from environment variables (optionally loaded from a
repository-level ``.env`` file).  Nothing in this module contacts a network service.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "demo"
CONFIG_DIR = REPO_ROOT / "configs"

# Load the repository .env once (ADK's CLI also loads per-agent .env files).
load_dotenv(REPO_ROOT / ".env", override=False)

# Model defaults verified against https://ai.google.dev/gemini-api/docs/models on
# 2026-10-29.  Override them in .env if your project/region exposes different models.
DEFAULT_FAST_MODEL = "gemini-3.8-flash"
DEFAULT_ADVANCED_MODEL = "gemini-3.8-flash"


def env_str(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int, *, minimum: int | None = None,
            maximum: int | None = None) -> int:
    raw = os.getenv(name)
    try:
        value = int(raw) if raw is not None and raw.strip() else default
    except ValueError:
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def fast_model() -> str:
    """Model for extraction/formatting/tool-routing stages."""
    return env_str("GEMINI_FAST_MODEL", DEFAULT_FAST_MODEL)


def advanced_model() -> str:
    """Model for reasoning-heavy stages (synthesis, security review, pattern discovery)."""
    return env_str("GEMINI_ADVANCED_MODEL", DEFAULT_ADVANCED_MODEL)


def state_dir() -> Path:
    """Writable directory for local demo databases (SQLite).  Never committed."""
    path = Path(env_str("LOCAL_STATE_DIR", str(REPO_ROOT / ".local_state")))
    path.mkdir(parents=True, exist_ok=True)
    return path
