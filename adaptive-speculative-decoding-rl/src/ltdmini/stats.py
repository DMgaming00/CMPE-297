"""Uncertainty for small-sample results: bootstrap CIs and paired comparisons."""
from __future__ import annotations

import numpy as np


def bootstrap_ci(values, stat=np.mean, n_boot: int = 10_000, alpha: float = 0.05, seed: int = 0):
    v = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(v), size=(n_boot, len(v)))
    stats = np.apply_along_axis(stat, 1, v[idx])
    lo, hi = np.quantile(stats, [alpha / 2, 1 - alpha / 2])
    return float(stat(v)), float(lo), float(hi)


def ratio_bootstrap_ci(num, den, n_boot: int = 10_000, alpha: float = 0.05, seed: int = 0):
    """CI for sum(num)/sum(den), resampling sequences (e.g. total AR time / total SD time)."""
    num, den = np.asarray(num, float), np.asarray(den, float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(num), size=(n_boot, len(num)))
    r = num[idx].sum(1) / den[idx].sum(1)
    lo, hi = np.quantile(r, [alpha / 2, 1 - alpha / 2])
    return float(num.sum() / den.sum()), float(lo), float(hi)


def paired_bootstrap_diff(a, b, n_boot: int = 10_000, alpha: float = 0.05, seed: int = 0):
    """CI for mean(a - b) over paired items, plus the fraction of items where a > b."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = a - b
    mean, lo, hi = bootstrap_ci(d, n_boot=n_boot, alpha=alpha, seed=seed)
    return {"mean_diff": mean, "ci_low": lo, "ci_high": hi, "win_rate": float((d > 0).mean()),
            "significant": bool(lo > 0 or hi < 0)}
