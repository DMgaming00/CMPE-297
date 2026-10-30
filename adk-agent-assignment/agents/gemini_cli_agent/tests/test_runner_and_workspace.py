from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from agents.gemini_cli_agent.runner import run_bounded
from agents.gemini_cli_agent.security import validate_repo_url
from agents.gemini_cli_agent.workspace import (
    WorkspaceError,
    cloned_repository,
    strip_untrusted_config,
    verify_cited_paths,
)


async def test_timeout_kills_process_group():
    # The child spawns a grandchild; both must die when the timeout fires.
    code = ("import subprocess, sys, time; "
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
            "print('started', flush=True); time.sleep(60)")
    start = time.monotonic()
    result = await run_bounded([sys.executable, "-c", code], cwd=None, env={}, timeout_s=1.5)
    assert result.timed_out and time.monotonic() - start < 10
    assert "started" in result.stdout  # partial output preserved


async def test_output_is_capped_without_deadlock():
    code = "import sys; sys.stdout.write('x' * 3_000_000)"
    result = await run_bounded([sys.executable, "-c", code], cwd=None, env={}, timeout_s=20,
                               max_stdout=1000)
    assert len(result.stdout) == 1000 and result.stdout_truncated and result.returncode == 0


async def test_missing_executable_is_reported():
    result = await run_bounded(["definitely-not-a-binary-xyz"], cwd=None, env={}, timeout_s=5)
    assert result.not_found and result.returncode is None


async def test_nonzero_exit_and_stderr_captured():
    code = "import sys; sys.stderr.write('boom'); sys.exit(3)"
    result = await run_bounded([sys.executable, "-c", code], cwd=None, env={}, timeout_s=5)
    assert result.returncode == 3 and result.stderr == "boom"


def test_strip_untrusted_config(tmp_path: Path):
    (tmp_path / "GEMINI.md").write_text("evil")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "GEMINI.md").write_text("evil")
    (tmp_path / ".gemini").mkdir()
    (tmp_path / ".gemini" / "settings.json").write_text("{}")
    (tmp_path / "README.md").write_text("ok")
    removed = strip_untrusted_config(tmp_path)
    assert removed == [".gemini/", "GEMINI.md", "pkg/GEMINI.md"]
    assert (tmp_path / "README.md").exists() and not (tmp_path / ".gemini").exists()


def test_verify_cited_paths(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x")
    text = "See src/app.py:12, ghost/missing.py and ../../etc/passwd.txt and https://x.io/a.js"
    result = verify_cited_paths(tmp_path, text)
    assert result["verified"] == ["src/app.py"]
    assert "ghost/missing.py" in result["unverified"]


async def test_clone_strips_config_and_always_cleans_up(local_repo, track_tempdirs):
    repo = validate_repo_url("https://github.com/example/demo")
    async with cloned_repository(repo) as ws:
        assert (ws.root / "app" / "main.py").exists()
        assert not (ws.root / "GEMINI.md").exists()
        assert ".gemini/" in ws.removed_untrusted
        assert len(ws.commit) == 40
    assert track_tempdirs and not Path(track_tempdirs[0]).exists()

    with pytest.raises(RuntimeError):
        async with cloned_repository(repo):
            raise RuntimeError("tool crashed mid-analysis")
    assert not Path(track_tempdirs[1]).exists()


async def test_clone_failure_is_reported_and_cleaned(local_repo, track_tempdirs, monkeypatch):
    repo = validate_repo_url("https://github.com/example/demo")
    with pytest.raises(WorkspaceError) as err:
        async with cloned_repository(repo, ref="no-such-branch"):
            pass
    assert err.value.code == "CLONE_FAILED"
    assert not Path(track_tempdirs[0]).exists()


async def test_repository_size_limit(local_repo, monkeypatch, track_tempdirs):
    monkeypatch.setenv("REPO_MAX_FILES", "100")
    for i in range(120):
        (local_repo / f"f{i}.txt").write_text("x")
    import os
    import subprocess

    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull}
    subprocess.run(["git", "add", "-A"], cwd=local_repo, check=True, env=env)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "commit",
                    "-qm", "more"], cwd=local_repo, check=True, env=env)
    with pytest.raises(WorkspaceError) as err:
        async with cloned_repository(validate_repo_url("https://github.com/example/demo")):
            pass
    assert err.value.code == "REPO_TOO_LARGE"
    assert not Path(track_tempdirs[0]).exists()
