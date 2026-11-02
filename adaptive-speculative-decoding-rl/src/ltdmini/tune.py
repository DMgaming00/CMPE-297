"""Grid-search the training-free baselines on validation traces (fair, tuned baselines).

The paper compares against Eagle3 with grid-searched settings ("GS"); here every
baseline family gets its best setting on the validation split, chosen by simulated
speedup, before anything touches the test split.
"""
from __future__ import annotations

from .policies import DepthPolicy, baseline_grid, family
from .sim import simulate, summarize
from .timing import TimingModel
from .traces import Trace


def tune_baselines(val: list[Trace], timing: TimingModel, vocab: int, dmax: int) -> tuple[dict[str, DepthPolicy], list[dict]]:
    rows, best = [], {}
    for pol in baseline_grid(dmax):
        s = summarize(simulate(pol, val, timing, vocab, dmax))
        rows.append({"policy": pol.name, "family": family(pol), **s})
        f = family(pol)
        if f not in best or s["speedup"] > best[f][1]:
            best[f] = (pol, s["speedup"])
    return {f: p for f, (p, _) in best.items()}, rows
