"""Function tools for intake and fixing. Submitted code is stored as text, never executed."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from google.adk.tools.tool_context import ToolContext

from adk_shared.config import REPO_ROOT, env_str

FILES_KEY = "review_files"
FIX_FILES_KEY = "fix_files"
MAX_FILE_BYTES = 200_000
MAX_FILES = 20
_FILENAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-/]{0,120}\.py$")


def workspace_root() -> Path:
    """Directory the reviewer may read from (default: the demo fixtures)."""
    return Path(env_str("REVIEW_WORKSPACE_ROOT",
                        str(REPO_ROOT / "data" / "demo" / "code_review"))).resolve()


def _valid_name(filename: str) -> str:
    filename = (filename or "submission.py").strip().replace("\\", "/")
    if not _FILENAME.fullmatch(filename) or ".." in filename.split("/"):
        raise ValueError("filename must be a relative .py path without '..'")
    return filename


def submit_code_for_review(code: str, filename: str, tool_context: ToolContext) -> dict:
    """Register Python source code pasted by the user for review.

    Args:
        code: The exact source code to review, copied verbatim from the user's message.
        filename: A short file name for it, e.g. "payments.py" (default submission.py).
    """
    try:
        filename = _valid_name(filename)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    if not code.strip():
        return {"ok": False, "error": "code is empty"}
    if len(code.encode()) > MAX_FILE_BYTES:
        return {"ok": False, "error": f"file exceeds {MAX_FILE_BYTES} bytes"}
    files = dict(tool_context.state.get(FILES_KEY) or {})
    if filename not in files and len(files) >= MAX_FILES:
        return {"ok": False, "error": f"at most {MAX_FILES} files per review"}
    files[filename] = code
    tool_context.state[FILES_KEY] = files
    return {"ok": True, "filename": filename, "lines": len(code.splitlines()),
            "files_registered": sorted(files)}


def load_workspace_files(paths: list[str], tool_context: ToolContext) -> dict:
    """Load .py files from the configured review workspace (read-only, sandboxed).

    Args:
        paths: Relative paths inside the workspace, e.g. ["vulnerable_app.py"].
    """
    root = workspace_root()
    files = dict(tool_context.state.get(FILES_KEY) or {})
    loaded, errors = [], []
    for raw in paths[:MAX_FILES]:
        try:
            name = _valid_name(raw)
            target = (root / name).resolve()
            if not target.is_relative_to(root):  # blocks traversal and symlink escapes
                raise ValueError("path escapes the review workspace")
            if not target.is_file():
                raise ValueError("file not found in the review workspace")
            if target.stat().st_size > MAX_FILE_BYTES:
                raise ValueError("file too large")
            files[name] = target.read_text(encoding="utf-8", errors="replace")
            loaded.append(name)
        except (OSError, ValueError) as exc:
            errors.append({"path": raw, "error": str(exc)})
    tool_context.state[FILES_KEY] = files
    available = sorted(p.relative_to(root).as_posix() for p in root.rglob("*.py"))[:50]
    return {"ok": not errors, "loaded": loaded, "errors": errors,
            "available_files": available if errors else []}


def list_workspace_files() -> dict[str, Any]:
    """List the .py files available in the review workspace."""
    root = workspace_root()
    return {"workspace": root.name,
            "files": sorted(p.relative_to(root).as_posix() for p in root.rglob("*.py"))[:200]}


def submit_fixed_code(filename: str, code: str, tool_context: ToolContext) -> dict:
    """Submit the complete corrected source for one reviewed file.

    Args:
        filename: Must match a file under review.
        code: The full corrected file contents (not a diff).
    """
    originals = tool_context.state.get(FILES_KEY) or {}
    if filename not in originals:
        return {"ok": False, "error": f"unknown file; reviewed files: {sorted(originals)}"}
    if len(code.encode()) > MAX_FILE_BYTES or not code.strip():
        return {"ok": False, "error": "code is empty or too large"}
    fixes = dict(tool_context.state.get(FIX_FILES_KEY) or {})
    fixes[filename] = code
    tool_context.state[FIX_FILES_KEY] = fixes
    return {"ok": True, "filename": filename, "lines": len(code.splitlines())}
