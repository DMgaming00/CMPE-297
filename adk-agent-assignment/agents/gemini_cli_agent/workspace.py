"""Temporary, isolated repository workspaces for Gemini CLI runs."""

from __future__ import annotations

import re
import shutil
import tempfile
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

from adk_shared.config import env_int

from .runner import run_bounded
from .security import RepoRef, build_clone_argv, git_env

# Files that let a repository configure or instruct Gemini CLI.  A cloned repository is
# untrusted, so they are deleted before the CLI starts (defence in depth: the folder is
# also never marked trusted).
UNTRUSTED_CONFIG_NAMES = {"GEMINI.md", ".geminiignore"}
UNTRUSTED_CONFIG_DIRS = {".gemini"}
_PATH_TOKEN = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)*[\w.-]+\.[A-Za-z0-9]{1,8})(?::\d+)?")


class WorkspaceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Workspace:
    root: Path
    repo: RepoRef
    commit: str = ""
    file_count: int = 0
    size_bytes: int = 0
    languages: dict[str, int] = field(default_factory=dict)
    removed_untrusted: list[str] = field(default_factory=list)


def _scan(root: Path, max_files: int, max_bytes: int) -> tuple[int, int, dict[str, int]]:
    count, size, langs = 0, 0, Counter()
    for path in root.rglob("*"):
        if ".git" in path.relative_to(root).parts or path.is_symlink() or not path.is_file():
            continue
        count += 1
        size += path.stat().st_size
        if path.suffix:
            langs[path.suffix.lower()] += 1
        if count > max_files or size > max_bytes:
            raise WorkspaceError("REPO_TOO_LARGE",
                                 f"Repository exceeds limits ({max_files} files / "
                                 f"{max_bytes // 1_000_000} MB).")
    return count, size, dict(langs.most_common(8))


def strip_untrusted_config(root: Path) -> list[str]:
    removed = []
    for path in sorted(root.rglob("*"), reverse=True):
        rel = path.relative_to(root)
        if ".git" in rel.parts[:1]:
            continue
        if path.is_dir() and path.name in UNTRUSTED_CONFIG_DIRS and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)
            removed.append(rel.as_posix() + "/")
        elif path.name in UNTRUSTED_CONFIG_NAMES and (path.is_file() or path.is_symlink()):
            path.unlink(missing_ok=True)
            removed.append(rel.as_posix())
    return sorted(removed)


def verify_cited_paths(root: Path, text: str, limit: int = 40) -> dict[str, list[str]]:
    """Split file paths mentioned in CLI output into those that exist in the clone and
    those that do not (possible hallucinations)."""
    verified, unverified = [], []
    for match in dict.fromkeys(m.group(1) for m in _PATH_TOKEN.finditer(text or "")):
        if match.startswith(("http", "www.")) or match.count(".") > 4:
            continue
        candidate = (root / match).resolve()
        inside = candidate.is_relative_to(root.resolve())
        (verified if inside and candidate.is_file() else unverified).append(match)
        if len(verified) + len(unverified) >= limit:
            break
    return {"verified": verified, "unverified": unverified}


@asynccontextmanager
async def cloned_repository(repo: RepoRef, ref: str | None = None) -> AsyncIterator[Workspace]:
    """Shallow-clone ``repo`` into a private temp dir that is always deleted afterwards."""
    tmp = tempfile.mkdtemp(prefix="adk-gemini-")
    try:
        root = Path(tmp) / "repo"
        result = await run_bounded(
            build_clone_argv(repo, str(root), ref), cwd=tmp, env=git_env(),
            timeout_s=env_int("GIT_CLONE_TIMEOUT_SECONDS", 90, minimum=10, maximum=600),
            max_stdout=10_000, max_stderr=4_000)
        if result.not_found:
            raise WorkspaceError("GIT_NOT_FOUND", "git is not installed on this host.")
        if result.timed_out:
            raise WorkspaceError("CLONE_TIMEOUT", "git clone timed out.")
        if result.returncode != 0 or not root.is_dir():
            stderr = result.stderr.strip().splitlines()[-1:] or ["unknown error"]
            raise WorkspaceError("CLONE_FAILED", f"git clone failed: {stderr[0][:300]}")
        workspace = Workspace(root=root, repo=repo)
        workspace.removed_untrusted = strip_untrusted_config(root)
        workspace.file_count, workspace.size_bytes, workspace.languages = _scan(
            root, env_int("REPO_MAX_FILES", 20_000, minimum=100),
            env_int("REPO_MAX_MB", 300, minimum=1) * 1_000_000)
        head = await run_bounded(["git", "-C", str(root), "rev-parse", "HEAD"], cwd=tmp,
                                 env=git_env(), timeout_s=10, max_stdout=200)
        workspace.commit = head.stdout.strip()[:40]
        yield workspace
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
