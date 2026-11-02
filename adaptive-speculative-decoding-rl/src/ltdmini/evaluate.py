"""Simulated evaluation on held-out traces, with bootstrap CIs and paired comparisons."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from .policies import DepthPolicy
from .sim import simulate
from .stats import paired_bootstrap_diff, ratio_bootstrap_ci
from .timing import TimingModel
from .traces import Trace


def group_of(source: str) -> str:
    return source.rsplit("-", 1)[0]


def evaluate_sim(policies: dict[str, DepthPolicy], test: list[Trace], timing: TimingModel, vocab: int,
                 dmax: int, reference: str | None = None, seeds=(0, 1, 2), noise: float = 0.05) -> dict:
    """Runs each policy on every test trace (several timing-noise seeds, averaged per
    sequence), then reports per-group and overall speedup with 95% bootstrap CIs."""
    per_seq: dict[str, list] = {}
    for name, pol in policies.items():
        runs = [simulate(pol, test, timing, vocab, dmax, noise=noise, seed=s) for s in seeds]
        per_seq[name] = [
            {"source": m0.source, "group": group_of(m0.source), "n_tokens": m0.n_tokens,
             "ar_time": m0.ar_time, "sd_time": float(np.mean([r[i].sd_time for r in runs])),
             "tau": m0.mean_accept_len, "mean_depth": m0.mean_depth}
            for i, m0 in enumerate(runs[0])
        ]
    groups = sorted({r["group"] for r in next(iter(per_seq.values()))}) + ["overall"]
    table: dict[str, dict] = defaultdict(dict)
    for name, rows in per_seq.items():
        for g in groups:
            sel = rows if g == "overall" else [r for r in rows if r["group"] == g]
            sp, lo, hi = ratio_bootstrap_ci([r["ar_time"] for r in sel], [r["sd_time"] for r in sel])
            tau = float(np.average([r["tau"] for r in sel], weights=[r["n_tokens"] for r in sel]))
            table[name][g] = {"speedup": sp, "ci_low": lo, "ci_high": hi, "tau": tau,
                              "mean_depth": float(np.mean([r["mean_depth"] for r in sel])), "n": len(sel)}
    paired = {}
    if reference and reference in per_seq:
        ref = [r["ar_time"] / r["sd_time"] for r in per_seq[reference]]
        for name, rows in per_seq.items():
            if name != reference:
                paired[name] = paired_bootstrap_diff([r["ar_time"] / r["sd_time"] for r in rows], ref)
    # RQ1: each learned policy against the best TUNED BASELINE (highest overall speedup), paired over prompts.
    baselines = [n for n in per_seq if not n.startswith("ltd-mini")]
    best_base, vs_best = None, {}
    if baselines:
        best_base = max(baselines, key=lambda n: table[n]["overall"]["speedup"])
        base_sp = [r["ar_time"] / r["sd_time"] for r in per_seq[best_base]]
        for name, rows in per_seq.items():
            if name.startswith("ltd-mini"):
                vs_best[name] = paired_bootstrap_diff([r["ar_time"] / r["sd_time"] for r in rows], base_sp)
    return {"table": table, "groups": groups, "paired_vs_reference": paired, "reference": reference,
            "best_baseline": best_base, "paired_vs_best_baseline": vs_best, "per_seq": per_seq}


def save_json(obj, path: Path) -> None:
    path.write_text(json.dumps(obj, indent=2, default=float))
