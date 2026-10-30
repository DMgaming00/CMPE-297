#!/usr/bin/env python3
"""Local readiness check. Never calls an LLM or a paid service.

Exit code 1 only when something required for LOCAL development is missing; optional
production tooling (Gemini CLI, gcloud, Toolbox, credentials) produces WARN.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
RESULTS: list[tuple[str, str, str]] = []


def check(status: str, name: str, detail: str = "") -> None:
    RESULTS.append((status, name, detail))


def version_of(cmd: list[str]) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (out.stdout or out.stderr).strip().splitlines()[0] if out.returncode == 0 else ""


def main() -> int:
    ok_py = sys.version_info >= (3, 11)
    check("PASS" if ok_py else "FAIL", "Python >= 3.11", sys.version.split()[0])

    for module, label in (("google.adk", "google-adk"), ("mcp", "mcp SDK"),
                          ("pycodestyle", "pycodestyle"), ("dotenv", "python-dotenv")):
        check("PASS" if find_spec(module) else "FAIL", f"import {label}")
    if find_spec("google.adk"):
        from google.adk import version

        major = int(version.__version__.split(".")[0])
        check("PASS" if major == 2 else "WARN", "google-adk version", version.__version__)
    if find_spec("mcp"):
        check("PASS" if find_spec("mcp.server.mcpserver") else "FAIL", "mcp >= 2 (MCPServer)")
    check("PASS" if find_spec("toolbox_adk") else "WARN", "toolbox-adk (production extra)",
          "" if find_spec("toolbox_adk") else 'pip install -e ".[production]"')

    try:
        for name in ("lead_research", "gemini_cli_agent", "bug_assistant", "code_review",
                     "ecommerce"):
            __import__(f"agents.{name}.agent")
        check("PASS", "all five agents import and build root_agent")
    except Exception as exc:
        check("FAIL", "agent import", f"{type(exc).__name__}: {exc}")

    for rel in ("data/demo/ecommerce.json", "data/demo/bug_tickets.json",
                "data/demo/code_review/vulnerable_app.py",
                "configs/toolbox/ecommerce_tools.yaml", "configs/toolbox/bug_tracker_tools.yaml",
                "database/postgres/ecommerce_schema.sql"):
        check("PASS" if (ROOT / rel).exists() else "FAIL", f"file {rel}")
    for rel in ("data/demo/ecommerce.json", "data/demo/bug_tickets.json"):
        try:
            json.loads((ROOT / rel).read_text())
        except (OSError, ValueError) as exc:
            check("FAIL", f"valid JSON {rel}", str(exc))

    env_file = ROOT / ".env"
    check("PASS" if env_file.exists() else "WARN", ".env present",
          "" if env_file.exists() else "cp .env.example .env")
    from adk_shared.config import advanced_model, fast_model  # loads .env

    has_key = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
    vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in {"1", "true"}
    placeholder = os.getenv("GOOGLE_API_KEY", "").startswith("your-")
    if vertex and os.getenv("GOOGLE_CLOUD_PROJECT", "your-project-id") != "your-project-id":
        check("PASS", "model credentials", "Vertex AI mode")
    elif has_key and not placeholder:
        check("PASS", "model credentials", "API key set")
    else:
        check("WARN", "model credentials", "needed to chat with agents (not for tests)")
    check("PASS", "models", f"fast={fast_model()} advanced={advanced_model()}")

    check("PASS" if shutil.which("git") else "FAIL", "git", version_of(["git", "--version"]))
    gemini = os.getenv("GEMINI_CLI_PATH", "gemini")
    gv = version_of([gemini, "--version"]) if shutil.which(gemini) else ""
    check("PASS" if gv else "WARN", "Gemini CLI (Agent B)",
          gv or "npm install -g @google/gemini-cli")
    node = version_of(["node", "--version"]) if shutil.which("node") else ""
    check("PASS" if node else "WARN", "Node.js (for Gemini CLI)", node or "install Node 20+")
    check("PASS" if shutil.which("gcloud") else "WARN", "gcloud (Vertex/Cloud Run)",
          "" if shutil.which("gcloud") else "only needed for Google Cloud")
    check("PASS" if shutil.which("toolbox") else "WARN", "MCP Toolbox binary (production)",
          "" if shutil.which("toolbox") else "only needed for *_BACKEND=toolbox")
    for var in ("ECOMMERCE_BACKEND", "BUG_TRACKER_BACKEND"):
        value = os.getenv(var, "local")
        check("PASS" if value in {"local", "toolbox"} else "FAIL", var, value)

    width = max(len(n) for _, n, _ in RESULTS)
    for status, name, detail in RESULTS:
        print(f"{status:<4}  {name:<{width}}  {detail}")
    fails = sum(s == "FAIL" for s, _, _ in RESULTS)
    warns = sum(s == "WARN" for s, _, _ in RESULTS)
    print(f"\n{len(RESULTS)} checks: {len(RESULTS) - fails - warns} PASS, {warns} WARN, "
          f"{fails} FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
