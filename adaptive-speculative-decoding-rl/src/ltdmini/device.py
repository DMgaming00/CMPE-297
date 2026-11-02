"""Device, dtype and timing helpers (Apple Silicon MPS, CUDA, or CPU)."""
from __future__ import annotations

import time

import torch


def pick_device(pref: str = "auto") -> torch.device:
    if pref != "auto":
        return torch.device(pref)
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def pick_dtype(pref: str, device: torch.device) -> torch.dtype:
    if pref != "auto":
        return {"float32": torch.float32, "float16": torch.float16, "bfloat16": torch.bfloat16}[pref]
    # fp16 on accelerators halves memory traffic (decode is memory-bound); fp32 on CPU for exactness.
    return torch.float16 if device.type in ("mps", "cuda") else torch.float32


def synchronize(device: torch.device) -> None:
    """GPU work is asynchronous; always synchronize before reading the clock."""
    if device.type == "cuda":
        torch.cuda.synchronize()
    elif device.type == "mps":
        torch.mps.synchronize()


class Stopwatch:
    def __init__(self, device: torch.device):
        self.device = device

    def now(self) -> float:
        synchronize(self.device)
        return time.perf_counter()
