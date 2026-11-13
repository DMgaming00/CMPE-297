"""Metrics shared by experiments, replay scoring and plots."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np


def best_at_cost(curve: Sequence[tuple[float, float]], cost: float, default: float) -> float:
    """Best-so-far score once ``cost`` units have been spent."""
    best = default
    for c, s in curve:
        if c <= cost + 1e-9:
            best = s
        else:
            break
    return best


def resample_curve(curve: Sequence[tuple[float, float]], grid: Sequence[float], default: float) -> list[float]:
    return [best_at_cost(curve, g, default) for g in grid]


def cost_to_reach(curve: Sequence[tuple[float, float]], target: float) -> float | None:
    for c, s in curve:
        if s >= target - 1e-12:
            return c
    return None


def frontier_hypervolume(points: Sequence[tuple[float, float]]) -> float:
    """Area dominated by (cost, quality) points in the unit square.

    Cost is minimised, quality maximised; reference point is (1, 0). The value is
    the area under the running-max quality staircase, so reaching high quality
    with few calls scores close to 1.
    """
    pts = sorted((min(max(c, 0.0), 1.0), min(max(q, 0.0), 1.0)) for c, q in points)
    area, best, prev_c = 0.0, 0.0, None
    for c, q in pts:
        if prev_c is not None:
            area += (c - prev_c) * best
        best = max(best, q)
        prev_c = c
    if prev_c is not None:
        area += (1.0 - prev_c) * best
    return area


def bootstrap_ci(values: Sequence[float], n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    """95% percentile bootstrap CI of the mean."""
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return (math.nan, math.nan)
    if arr.size == 1:
        return (float(arr[0]), float(arr[0]))
    rng = np.random.default_rng(seed)
    means = rng.choice(arr, size=(n_boot, arr.size), replace=True).mean(axis=1)
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def improvement_efficiency(initial: float, final: float, units: float) -> float:
    """Score gained per 1000 budget units."""
    return (final - initial) / max(units, 1.0) * 1000.0
