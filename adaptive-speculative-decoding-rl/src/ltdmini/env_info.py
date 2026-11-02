"""Record the environment with every result so runs are reproducible."""
from __future__ import annotations

import platform
import subprocess
import sys
from datetime import datetime, timezone


def git_info() -> dict:
    def run(*cmd):
        try:
            return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
        except (OSError, subprocess.CalledProcessError):
            return None
    return {"commit": run("git", "rev-parse", "HEAD"),
            "dirty": bool(run("git", "status", "--porcelain")) if run("git", "rev-parse", "HEAD") else None}


def environment() -> dict:
    info = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        **{"git_" + k: v for k, v in git_info().items()},
    }
    for mod in ("numpy", "torch", "transformers", "stable_baselines3", "gymnasium"):
        try:
            info[mod] = __import__(mod).__version__
        except (ImportError, AttributeError):
            info[mod] = None
    try:
        import torch
        info["mps_available"] = bool(torch.backends.mps.is_available())
        info["cuda_available"] = bool(torch.cuda.is_available())
    except (ImportError, AttributeError):
        pass  # torch absent or too old to expose backends
    return info
