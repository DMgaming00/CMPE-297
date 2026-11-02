"""A simple, measured cost model for draft and verify steps.

The simulator needs per-step times. We measure them on YOUR hardware
(`ltdmini profile`) and fit small linear models:

    draft_step(L)     = d0 + d1 * L                 one draft forward pass, 1 token
    verify(k, L)      = v0 + v1 * k + v2 * L        one target forward pass over k+1 tokens
    ar_step(L)        = a0 + a1 * L                 one target forward pass, 1 token (baseline)

L is the current context length. All times are seconds.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np


@dataclass
class TimingModel:
    d0: float
    d1: float
    v0: float
    v1: float
    v2: float
    a0: float
    a1: float
    device: str = "unknown"
    note: str = ""

    def draft_step(self, L: float) -> float:
        return max(self.d0 + self.d1 * L, 1e-6)

    def draft_total(self, k: int, L: float) -> float:
        return sum(self.draft_step(L + j) for j in range(k))

    def verify(self, k: int, L: float) -> float:
        return max(self.v0 + self.v1 * k + self.v2 * L, 1e-6)

    def ar_step(self, L: float) -> float:
        return max(self.a0 + self.a1 * L, 1e-6)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: str | Path) -> TimingModel:
        return cls(**json.loads(Path(path).read_text()))

    @classmethod
    def synthetic(cls) -> TimingModel:
        """Plausible ratios for a small draft/target pair (draft ~5x cheaper than target,
        verification of a few extra tokens nearly free: decode is memory-bound).
        Used only for smoke tests and documentation examples."""
        return cls(d0=0.004, d1=1e-7, v0=0.020, v1=0.0012, v2=2e-6,
                   a0=0.019, a1=2e-6, device="synthetic", note="illustrative, not measured")


def fit_linear(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Least-squares fit with an intercept column already included in X."""
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return coef


def fit_timing_model(draft_samples: list[tuple[float, float]],
                     verify_samples: list[tuple[int, float, float]],
                     ar_samples: list[tuple[float, float]],
                     device: str) -> TimingModel:
    """Fit the three linear models.

    draft_samples:  (L, seconds)
    verify_samples: (k, L, seconds)
    ar_samples:     (L, seconds)
    """
    dL = np.array([s[0] for s in draft_samples]); dy = np.array([s[1] for s in draft_samples])
    d0, d1 = fit_linear(np.c_[np.ones_like(dL), dL], dy)
    vk = np.array([s[0] for s in verify_samples], dtype=float)
    vL = np.array([s[1] for s in verify_samples]); vy = np.array([s[2] for s in verify_samples])
    v0, v1, v2 = fit_linear(np.c_[np.ones_like(vk), vk, vL], vy)
    aL = np.array([s[0] for s in ar_samples]); ay = np.array([s[1] for s in ar_samples])
    a0, a1 = fit_linear(np.c_[np.ones_like(aL), aL], ay)
    return TimingModel(float(d0), float(d1), float(v0), float(v1), float(v2), float(a0), float(a1),
                       device=device, note="fitted from measured samples")
