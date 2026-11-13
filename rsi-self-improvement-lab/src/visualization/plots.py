"""Figures generated from saved experiment results (``experiments/results/<config>/``)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.benchmarks import protocol as P
from src.core import candidate as cand
from src.core.config import ROOT, ExperimentConfig
from src.core.metrics import resample_curve
from src.core.problem import NEAREST_NEIGHBOR, build_tour, make_instances

FIG_ROOT = ROOT / "artifacts" / "figures"
# Okabe-Ito colour-blind-safe palette; RSI methods saturated, baselines muted.
COLORS = {
    "initial": "#999999",
    "random_search": "#bbbbbb",
    "hill_climb": "#8c8c6b",
    "aide_style": "#6b6b4f",
    "fixed_tree": "#555555",
    "hill_climb_matched": "#a0a070",
    "fixed_tree_matched": "#777777",
    "dream_rsi": "#0072B2",
    "budget_rsi": "#D55E00",
    "so_rsi": "#009E73",
}
LABELS = {
    "initial": "Initial (NN)",
    "random_search": "Random search",
    "hill_climb": "Hill-climb",
    "aide_style": "AIDE-style tree",
    "fixed_tree": "Fixed tree search",
    "hill_climb_matched": "Hill-climb (+adapt budget)",
    "fixed_tree_matched": "Fixed tree (+adapt budget)",
    "dream_rsi": "Dream-RSI",
    "budget_rsi": "Budget RSI",
    "so_rsi": "SO-RSI",
}


def fig_dir(name: str) -> Path:
    d = FIG_ROOT if name == "default" else FIG_ROOT / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _style(ax: plt.Axes, xlabel: str, ylabel: str, title: str) -> None:
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=11, loc="left")
    ax.grid(alpha=0.25)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def _color(m: str) -> str:
    return COLORS.get(m, "#CC79A7")


def anytime_curves(rows: list[dict[str, Any]], out: Path) -> Path:
    methods = [m for m in P.MAIN_METHODS if m != "initial" and any(r["method"] == m for r in rows)]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    max_c = max(r["curve"][-1][0] for r in rows if r["curve"])
    grid = np.linspace(0, max_c, 120)
    for m in methods:
        rs = [r for r in rows if r["method"] == m]
        mat = np.array([resample_curve([tuple(p) for p in r["curve"]], grid, r["initial_train"]) for r in rs])
        mean, se = mat.mean(0), mat.std(0) / np.sqrt(len(rs))
        ax.plot(grid, mean, label=LABELS[m], color=_color(m), lw=2.2 if m in P.RSI_METHODS else 1.4)
        ax.fill_between(grid, mean - se, mean + se, color=_color(m), alpha=0.12)
    _style(
        ax,
        "evaluator budget spent on the held-out task (instance-evaluations)",
        "best train score so far (higher = better)",
        "Anytime performance during deployment (mean ± s.e. over seeds × tasks)",
    )
    ax.legend(fontsize=8, ncol=2, frameon=False)
    fig.tight_layout()
    path = out / "anytime_curves.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def final_comparison(rows: list[dict[str, Any]], out: Path) -> Path:
    summary = [s for s in P.summarize(rows) if s["method"] in P.MAIN_METHODS]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ys = np.arange(len(summary))[::-1]
    for y, s in zip(ys, summary):
        ax.barh(y, s["final"], color=_color(s["method"]), alpha=0.9)
        ax.plot([s["final_ci_lo"], s["final_ci_hi"]], [y, y], color="black", lw=1.2)
    ax.set_yticks(ys, [LABELS[s["method"]] for s in summary])
    ax.axvline(summary[0]["initial"], color="#999", ls="--", lw=1)
    _style(
        ax,
        "held-out TEST score = -100 × (tour / 2-opt reference - 1)   (higher = better)",
        "",
        "Final test score by method (mean, 95% bootstrap CI)",
    )
    fig.tight_layout()
    path = out / "final_comparison.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def paired_improvement(rows: list[dict[str, Any]], out: Path, reference: str = "fixed_tree") -> Path:
    methods = [m for m in P.MAIN_METHODS if m not in ("initial", reference) and any(r["method"] == m for r in rows)]
    fig, ax = plt.subplots(figsize=(8, 4.4))
    for i, m in enumerate(methods[::-1]):
        d = P.paired_vs(rows, m, reference)
        ax.errorbar(
            d["mean_diff"],
            i,
            xerr=[[d["mean_diff"] - d["ci_lo"]], [d["ci_hi"] - d["mean_diff"]]],
            fmt="o",
            color=_color(m),
            capsize=3,
        )
    ax.set_yticks(range(len(methods)), [LABELS[m] for m in methods[::-1]])
    ax.axvline(0, color="black", lw=1)
    _style(
        ax,
        f"paired Δ test score vs {LABELS[reference]} (same seed & task)",
        "",
        "Improvement over the fixed-policy baseline (mean, 95% CI)",
    )
    fig.tight_layout()
    path = out / "improvement_over_baseline.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def compute_quality(rows: list[dict[str, Any]], out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(7, 4.6))
    for s in P.summarize(rows):
        if s["method"] not in P.MAIN_METHODS or s["method"] == "initial":
            continue
        ax.scatter(s["total_units"], s["final"], s=70, color=_color(s["method"]), zorder=3)
        ax.annotate(LABELS[s["method"]], (s["total_units"], s["final"]), fontsize=7, xytext=(4, 4), textcoords="offset points")
    _style(
        ax,
        "total evaluator units per held-out task (deployment + amortised adaptation)",
        "final test score",
        "Compute / quality trade-off",
    )
    fig.tight_layout()
    path = out / "compute_quality.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def dream_policy_evolution(logs: list[dict[str, Any]], out: Path) -> Path | None:
    runs = [lg["log"] for lg in logs if lg["method"] == "dream_rsi"]
    if not runs:
        return None
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    params = ["temperature", "explore_c", "restart_prob", "batch", "patience"]
    n_gen = len(runs[0]["generations"])
    start = {"temperature": 2.0, "explore_c": 0.0, "restart_prob": 0.1, "batch": 1, "patience": 1000.0}
    for p in params:
        vals = np.array([[start[p]] + [g["candidate_policies"][g["chosen"]][p] for g in r["generations"]] for r in runs])
        scale = 1.0 if p != "patience" else 1 / 100.0
        axes[0].plot(range(n_gen + 1), vals.mean(0) * scale, marker="o", label=p + (" /100" if p == "patience" else ""))
    _style(axes[0], "generation", "mean parameter value", "Policy parameters across Dream-RSI generations")
    axes[0].legend(fontsize=7, frameon=False)
    for r in runs:
        inc = [g["replay_scores"][0] for g in r["generations"]]
        sel = [g["replay_scores"][g["chosen"]] for g in r["generations"]]
        axes[1].scatter(inc, sel, color=COLORS["dream_rsi"], alpha=0.5)
    lim = [min(axes[1].get_xlim()[0], axes[1].get_ylim()[0]), max(axes[1].get_xlim()[1], axes[1].get_ylim()[1])]
    axes[1].plot(lim, lim, "k--", lw=1)
    _style(axes[1], "incumbent policy replay score", "selected policy replay score", "Replay-world score: selected vs incumbent")
    chosen = np.array([g["chosen"] for r in runs for g in r["generations"]])
    axes[2].bar(range(4), [(chosen == i).mean() for i in range(4)], color=COLORS["dream_rsi"])
    axes[2].set_xticks(
        range(4), ["keep\nincumbent", "revision 1\n(evidence)", "revision 2\n(+stopping)", "revision 3\n(jitter)"], fontsize=8
    )
    _style(axes[2], "", "share of generations selected", "Which candidate won the replay?")
    fig.tight_layout()
    path = out / "dream_policy_evolution.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def budget_readout(logs: list[dict[str, Any]], out: Path) -> Path | None:
    runs = [lg["log"] for lg in logs if lg["method"] == "budget_rsi"]
    if not runs:
        return None
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    names = list(runs[0]["readout"])
    w = np.array([[r["readout"][n] for n in names] for r in runs])
    axes[0].barh(names[::-1], w.mean(0)[::-1], xerr=w.std(0)[::-1], color=COLORS["budget_rsi"], alpha=0.85)
    _style(axes[0], "weight (mean ± sd over seeds)", "", "Frozen linear readout")
    pa = np.array([p for r in runs for p in r["pred_vs_actual"]])
    pa[:, 1] = np.clip(pa[:, 1], -8, 8)
    axes[1].scatter(pa[:, 0], pa[:, 1], s=8, alpha=0.35, color=COLORS["budget_rsi"])
    rho = float(np.mean([r["heldout_label_spearman"] for r in runs]))
    _style(
        axes[1],
        "readout-predicted gain of the chosen edit",
        "actual train-score gain (clipped ±8)",
        f"Deployment: predicted vs actual (label-fit Spearman ρ={rho:.2f})",
    )
    fig.tight_layout()
    path = out / "budget_rsi_readout.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def so_inquiry(logs: list[dict[str, Any]], out: Path) -> Path | None:
    runs = [lg["log"] for lg in logs if lg["method"] == "so_rsi"]
    if not runs:
        return None
    from collections import Counter

    verdicts = Counter(r["verdict"] for run in runs for r in run["memory"])
    anomalies = Counter(r["anomaly"] for run in runs for r in run["memory"])
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].bar(list(anomalies), list(anomalies.values()), color=COLORS["so_rsi"])
    _style(axes[0], "", "count over all seeds", "Structural anomalies found")
    axes[1].barh(list(verdicts)[::-1], list(verdicts.values())[::-1], color=COLORS["so_rsi"])
    _style(axes[1], "count over all seeds", "", "Probe verdicts (diagnosed mechanisms)")
    fig.tight_layout()
    path = out / "so_rsi_inquiry.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def ablation_plot(rows: list[dict[str, Any]], out: Path) -> Path | None:
    pairs = [
        ("dream_rsi", ["dream_no_replay", "dream_no_evolution"]),
        ("budget_rsi", ["budget_parent_only", "budget_no_screen"]),
        ("so_rsi", ["naive_rsi", "so_no_probes", "so_no_memory"]),
    ]
    have = {r["method"] for r in rows}
    if not any(a in have for _, abl in pairs for a in abl):
        return None
    summ = {s["method"]: s for s in P.summarize(rows)}
    fig, ax = plt.subplots(figsize=(8, 4.8))
    names, y = [], 0
    for full, abls in pairs:
        for m in [full, *abls]:
            if m in summ:
                s = summ[m]
                ax.barh(y, s["final"], color=_color(full), alpha=1.0 if m == full else 0.5)
                ax.plot([s["final_ci_lo"], s["final_ci_hi"]], [y, y], color="black", lw=1)
                names.append(m)
                y += 1
        y += 0.6
    ax.set_yticks([i + (0.6 * (k)) for k, i in enumerate(range(len(names)))][:0] or [], [])
    ax.set_yticks(_ytick_positions(pairs, have), names)
    ax.invert_yaxis()
    _style(ax, "final test score (mean, 95% CI)", "", "Ablations (lighter = component removed)")
    fig.tight_layout()
    path = out / "ablations.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _ytick_positions(pairs: list[tuple[str, list[str]]], have: set[str]) -> list[float]:
    pos, y = [], 0.0
    for full, abls in pairs:
        for m in [full, *abls]:
            if m in have:
                pos.append(y)
                y += 1
        y += 0.6
    return pos


def lineage_and_solution(cfg: ExperimentConfig, out: Path) -> Path:
    """Re-run Dream-RSI seed 0 (deterministic) to draw its deployment tree and the tours it builds."""
    from src.methods.dream_rsi.dream_rsi import run_dream_rsi

    run = run_dream_rsi(cfg, cfg.seeds[0])
    dep = run.deployments[0]
    task = next(t for t in cfg.held_out_specs() if t.name == dep.task)
    tree, best = dep.tree, dep.tree.best()
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    on_path = set(tree.lineage(best.id))
    for n in tree.nodes[1:]:
        p = tree.nodes[n.parent]  # type: ignore[index]
        hot = n.id in on_path
        axes[0].plot(
            [p.cost, n.cost], [max(p.score, -40), max(n.score, -40)], color="#0072B2" if hot else "#cccccc", lw=2 if hot else 0.6
        )  # type: ignore[type-var]
    axes[0].scatter([n.cost for n in tree.nodes], [max(n.score, -40) for n in tree.nodes], s=8, color="#555")  # type: ignore[type-var]
    _style(
        axes[0], "evaluator budget spent", "train score (clipped at -40)", f"Candidate lineage ({dep.task}); best lineage in blue"
    )
    inst = make_instances(task, "test")[0]
    for ax, expr, title in (
        (axes[1], NEAREST_NEIGHBOR, "Initial: Nearest-Neighbour"),
        (axes[2], best.expr, "Discovered by Dream-RSI"),
    ):
        tour = build_tour(inst, expr)
        pts = inst.coords[tour + [tour[0]]]
        ax.plot(pts[:, 0], pts[:, 1], "-", color=COLORS["dream_rsi"] if expr is best.expr else "#777", lw=1.3)
        ax.scatter(inst.coords[:, 0], inst.coords[:, 1], s=14, color="black", zorder=3)
        length = float(sum(inst.dist[a, b] for a, b in zip(tour, tour[1:] + tour[:1])))
        ax.set_title(f"{title}\nlength {length:.3f}  (2-opt ref {inst.reference_length:.3f})", fontsize=9, loc="left")
        ax.set_aspect("equal")
        ax.axis("off")
    fig.text(0.68, 0.01, "program: " + cand.to_str(best.expr)[:110], fontsize=7)
    fig.tight_layout()
    path = out / "lineage_and_solution.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def make_all_figures(name: str) -> list[str]:
    rows = P.load_rows(name)
    out = fig_dir(name)
    logs_path = P.RESULTS_DIR / name / "method_logs.json"
    logs = json.loads(logs_path.read_text()) if logs_path.exists() else []
    cfg = ExperimentConfig.from_dict(json.loads((P.RESULTS_DIR / name / "config.json").read_text()))
    made = [
        anytime_curves(rows, out),
        final_comparison(rows, out),
        paired_improvement(rows, out),
        compute_quality(rows, out),
        dream_policy_evolution(logs, out),
        budget_readout(logs, out),
        so_inquiry(logs, out),
        ablation_plot(rows, out),
        lineage_and_solution(cfg, out),
    ]
    return [str(p.relative_to(ROOT)) for p in made if p]
