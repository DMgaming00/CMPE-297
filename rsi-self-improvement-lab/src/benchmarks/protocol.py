"""The shared experimental protocol.

Every method gets: the same initial program (Nearest-Neighbour), the same training tasks
for adaptation, the same held-out tasks for deployment, the same evaluator and the same
per-task deployment budget, and the same seeds. Selection inside a run uses the TRAIN
instance split only; the reported ``final_test`` score uses a disjoint TEST split that no
agent ever queries.
"""

from __future__ import annotations

import csv
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from src.benchmarks.baselines import run_baseline
from src.core import candidate as cand
from src.core.config import ROOT, ExperimentConfig
from src.core.evaluator import score_expr
from src.core.metrics import bootstrap_ci, cost_to_reach, improvement_efficiency
from src.core.problem import NEAREST_NEIGHBOR
from src.core.results import MethodRun
from src.methods.budget_rsi.budget_rsi import run_budget_rsi
from src.methods.dream_rsi.dream_rsi import run_dream_rsi
from src.methods.so_rsi.so_rsi import run_so_rsi

BASELINES = ["initial", "random_search", "hill_climb", "aide_style", "fixed_tree", "hill_climb_matched", "fixed_tree_matched"]
RSI_METHODS = ["dream_rsi", "budget_rsi", "so_rsi"]
ABLATIONS = [
    "dream_no_replay",
    "dream_no_evolution",
    "budget_parent_only",
    "budget_no_screen",
    "naive_rsi",
    "so_no_probes",
    "so_no_memory",
]
MAIN_METHODS = BASELINES + RSI_METHODS
RESULTS_DIR = ROOT / "experiments" / "results"


def run_method(name: str, cfg: ExperimentConfig, seed: int) -> MethodRun:
    if name in BASELINES:
        return run_baseline(name, cfg, seed)
    dispatch = {
        "dream_rsi": lambda: run_dream_rsi(cfg, seed),
        "dream_no_replay": lambda: run_dream_rsi(cfg, seed, use_replay=False),
        "dream_no_evolution": lambda: run_dream_rsi(cfg, seed, evolve=False),
        "budget_rsi": lambda: run_budget_rsi(cfg, seed, "full"),
        "budget_parent_only": lambda: run_budget_rsi(cfg, seed, "parent_only"),
        "budget_no_screen": lambda: run_budget_rsi(cfg, seed, "no_screen"),
        "so_rsi": lambda: run_so_rsi(cfg, seed, "so_rsi"),
        "naive_rsi": lambda: run_so_rsi(cfg, seed, "naive_rsi"),
        "so_no_probes": lambda: run_so_rsi(cfg, seed, "so_no_probes"),
        "so_no_memory": lambda: run_so_rsi(cfg, seed, "so_no_memory"),
    }
    if name not in dispatch:
        raise KeyError(f"unknown method {name!r}; choose from {MAIN_METHODS + ABLATIONS}")
    return dispatch[name]()


def to_rows(run: MethodRun, cfg: ExperimentConfig, wall_total: float) -> list[dict[str, Any]]:
    """Score each deployment on the hidden TEST split and flatten to rows."""
    specs = {t.name: t for t in cfg.held_out_specs()}
    rows = []
    for dep in run.deployments:
        task = specs[dep.task]
        best = dep.tree.best()
        initial_test = score_expr(task, NEAREST_NEIGHBOR, "test").score
        final_test = score_expr(task, best.expr, "test")
        rows.append(
            {
                "method": run.method,
                "seed": run.seed,
                "task": dep.task,
                "initial_test": initial_test,
                "final_test": final_test.score,
                "improvement": final_test.score - initial_test,
                "final_train": best.score,
                "initial_train": dep.tree.root.score,
                "test_solved": final_test.solved,
                "test_n": final_test.n,
                "adapt_units": run.adapt_units,
                "deploy_units": dep.units_used,
                "total_units": run.adapt_units / len(run.deployments) + dep.units_used,  # adaptation amortised over tasks
                "evals": len(dep.tree.nodes),
                "wall_s": wall_total / len(run.deployments),
                "best_program": cand.to_str(best.expr),
                "curve": [[round(c, 1), round(s, 4)] for c, s in dep.tree.best_curve()],
            }
        )
    return rows


def _job(args: tuple[str, dict[str, Any], int]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    name, cfg_dict, seed = args
    cfg = ExperimentConfig.from_dict(cfg_dict)
    t0 = time.time()
    run = run_method(name, cfg, seed)
    rows = to_rows(run, cfg, time.time() - t0)
    return rows, {"method": run.method, "seed": seed, "log": run.log}


def run_experiment(
    cfg: ExperimentConfig, methods: list[str], out_dir: Path | None = None, workers: int | None = None, quiet: bool = False
) -> list[dict[str, Any]]:
    """Run ``methods`` x ``cfg.seeds`` (in parallel), save JSON/CSV, return flat rows."""
    jobs = [(m, cfg.to_dict(), s) for m in methods for s in cfg.seeds]
    workers = workers or min(os.cpu_count() or 1, 8)
    t0 = time.time()
    if workers <= 1:
        results = [_job(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_job, jobs))
    rows = [r for rs, _ in results for r in rs]
    logs = [lg for _, lg in results]
    out_dir = out_dir or RESULTS_DIR / cfg.name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "runs.json").write_text(json.dumps(rows))
    (out_dir / "method_logs.json").write_text(json.dumps(logs, default=_json_default))
    (out_dir / "config.json").write_text(json.dumps(cfg.to_dict(), indent=2))
    write_summary(summarize(rows), out_dir)
    if not quiet:
        print(f"[{cfg.name}] {len(jobs)} runs in {time.time() - t0:.1f}s -> {out_dir}")
    return rows


def _json_default(o: Any) -> Any:
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, (set, tuple)):
        return list(o)
    raise TypeError(f"not serialisable: {type(o)}")


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One summary row per method (means over seeds x held-out tasks, bootstrap CI on final_test)."""
    out = []
    for method in dict.fromkeys(r["method"] for r in rows):
        rs = [r for r in rows if r["method"] == method]
        imp = [r["improvement"] for r in rs]
        lo, hi = bootstrap_ci([r["final_test"] for r in rs])
        out.append(
            {
                "method": method,
                "n": len(rs),
                "initial": float(np.mean([r["initial_test"] for r in rs])),
                "final": float(np.mean([r["final_test"] for r in rs])),
                "final_ci_lo": lo,
                "final_ci_hi": hi,
                "improvement": float(np.mean(imp)),
                "success_rate": float(np.mean([r["improvement"] >= 1.0 for r in rs])),
                "adapt_units": float(np.mean([r["adapt_units"] for r in rs])),
                "deploy_units": float(np.mean([r["deploy_units"] for r in rs])),
                "total_units": float(np.mean([r["total_units"] for r in rs])),
                "wall_s": float(np.mean([r["wall_s"] for r in rs])),
                "efficiency": improvement_efficiency(0.0, float(np.mean(imp)), float(np.mean([r["total_units"] for r in rs]))),
            }
        )
    return out


def paired_vs(rows: list[dict[str, Any]], method: str, reference: str) -> dict[str, float]:
    """Paired (same seed, same task) difference in final_test: method - reference."""
    key = lambda r: (r["seed"], r["task"])
    a = {key(r): r["final_test"] for r in rows if r["method"] == method}
    b = {key(r): r["final_test"] for r in rows if r["method"] == reference}
    diffs = [a[k] - b[k] for k in a if k in b]
    lo, hi = bootstrap_ci(diffs)
    return {
        "mean_diff": float(np.mean(diffs)),
        "ci_lo": lo,
        "ci_hi": hi,
        "win_rate": float(np.mean([d > 1e-9 for d in diffs])),
        "n": len(diffs),
    }


def cost_to_match(rows: list[dict[str, Any]], reference: str = "fixed_tree") -> dict[str, dict[str, float]]:
    """Per method: how often, and how cheaply, it matches the reference's final TRAIN score (same seed & task).

    ``deploy_units`` is the median budget needed on the held-out task; ``incl_adapt`` adds the
    amortised adaptation cost, i.e. what an RSI method really spent to get there.
    """
    ref = {(r["seed"], r["task"]): r["final_train"] for r in rows if r["method"] == reference}
    out: dict[str, dict[str, float]] = {}
    for m in dict.fromkeys(r["method"] for r in rows):
        costs, incl = [], []
        total = 0
        for r in (x for x in rows if x["method"] == m):
            target = ref.get((r["seed"], r["task"]))
            if target is None:
                continue
            total += 1
            c = cost_to_reach([tuple(p) for p in r["curve"]], target)
            if c is not None:
                costs.append(c)
                incl.append(c + r["adapt_units"] / len([1 for x in rows if x["method"] == m and x["seed"] == r["seed"]]))
        out[m] = {
            "match_rate": len(costs) / total if total else 0.0,
            "deploy_units": float(np.median(costs)) if costs else float("nan"),
            "incl_adapt": float(np.median(incl)) if incl else float("nan"),
        }
    return out


def write_summary(summary: list[dict[str, Any]], out_dir: Path) -> None:
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    with open(out_dir / "summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)


def load_rows(name: str) -> list[dict[str, Any]]:
    path = RESULTS_DIR / name / "runs.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: run `python -m src.cli compare --config {name}` first")
    return json.loads(path.read_text())
