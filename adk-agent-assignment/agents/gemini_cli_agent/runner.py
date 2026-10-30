"""Bounded asynchronous subprocess execution.

* argv lists only (``create_subprocess_exec``) - no shell;
* hard wall-clock timeout that kills the whole process group (Gemini CLI is a Node
  process that may spawn children);
* stdout/stderr are read incrementally and capped, so a runaway process cannot exhaust
  memory;
* stdin is /dev/null so nothing can block on input.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import time
from dataclasses import dataclass


@dataclass
class ProcessResult:
    argv0: str
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    stdout_truncated: bool
    stderr_truncated: bool
    duration_s: float
    not_found: bool = False


async def _read_capped(stream: asyncio.StreamReader, limit: int) -> tuple[bytes, bool]:
    chunks, size, truncated = [], 0, False
    while True:
        chunk = await stream.read(65536)
        if not chunk:
            break
        if size < limit:
            take = chunk[: limit - size]
            chunks.append(take)
            size += len(take)
            truncated = truncated or len(take) < len(chunk)
        else:
            truncated = True  # keep draining so the child never blocks on a full pipe
    return b"".join(chunks), truncated


def _kill_group(proc: asyncio.subprocess.Process) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        with contextlib.suppress(ProcessLookupError):
            proc.kill()


async def run_bounded(argv: list[str], *, cwd: str | None, env: dict[str, str],
                      timeout_s: float, max_stdout: int = 200_000,
                      max_stderr: int = 20_000) -> ProcessResult:
    start = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv, cwd=cwd, env=env, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            start_new_session=True)
    except FileNotFoundError:
        return ProcessResult(argv[0], None, "", f"executable not found: {argv[0]}", False,
                             False, False, 0.0, not_found=True)
    assert proc.stdout is not None and proc.stderr is not None
    readers = asyncio.gather(_read_capped(proc.stdout, max_stdout),
                             _read_capped(proc.stderr, max_stderr), proc.wait())
    timed_out = False
    try:
        (out, out_trunc), (err, err_trunc), _ = await asyncio.wait_for(
            asyncio.shield(readers), timeout_s)
    except TimeoutError:
        timed_out = True
        _kill_group(proc)
        try:
            (out, out_trunc), (err, err_trunc), _ = await asyncio.wait_for(readers, 5)
        except (TimeoutError, asyncio.CancelledError):
            out, out_trunc, err, err_trunc = b"", False, b"", False
    finally:
        if proc.returncode is None:
            _kill_group(proc)
            await proc.wait()
    return ProcessResult(argv[0], proc.returncode, out.decode("utf-8", "replace"),
                         err.decode("utf-8", "replace"), timed_out, out_trunc, err_trunc,
                         round(time.monotonic() - start, 2))
