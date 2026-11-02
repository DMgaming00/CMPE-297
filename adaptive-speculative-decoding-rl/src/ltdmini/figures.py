"""All report figures, in one consistent style.

Color follows the entity, never its rank: the three PPO reward variants always wear the same hue, tuned baselines are
neutral gray. The three hues are the first three slots of the validated reference palette (all-pairs CVD and
normal-vision checks pass; aqua is below 3:1 contrast on white, so every bar/point also carries a direct value label).
Each function writes one PNG into `<run>/figures/` and returns its relative path, or None if its inputs are missing.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8b8a85", "#e6e5e1"
C_THR, C_ACC, C_TIME = "#eb6834", "#2a78d6", "#1baf7a"
C_BASE, C_BEST = "#b8b7b1", "#52514e"
REWARD_COLOR = {"throughput": C_THR, "acceptance": C_ACC, "time": C_TIME}
SHORT = {"ltd-mini-throughput": "LTD-Mini · throughput", "ltd-mini-acceptance": "LTD-Mini · acceptance",
         "ltd-mini-time": "LTD-Mini · time"}


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "text.color": INK, "axes.titlecolor": INK, "axes.titleweight": "bold", "axes.titlesize": 11,
        "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
        "font.size": 9, "legend.frameon": False, "hatch.linewidth": 1.0,
    })
    return plt


def _color(name: str, best: str | None = None) -> str:
    if name.startswith("ltd-mini-"):
        return REWARD_COLOR.get(name.split("-", 2)[2], C_THR)
    return C_BEST if name == best else C_BASE


def _label(name: str) -> str:
    return SHORT.get(name, name)


def _save(fig, res: Path, name: str) -> str:
    d = res / "figures"
    d.mkdir(exist_ok=True)
    fig.savefig(d / name, dpi=170, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return f"figures/{name}"


def _load(res: Path, name: str):
    p = res / name
    return json.loads(p.read_text()) if p.exists() else None


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def _pooled_real(res: Path) -> dict[str, list[dict]]:
    """policy -> one row per prompt, with speedup / tau averaged over all independent MPS wall-clock runs."""
    files = [f for f in sorted(res.glob("real_results*.jsonl")) if "backup" not in f.name]
    acc: dict[str, dict[str, list[dict]]] = {}
    for f in files:
        for r in _rows(f):
            acc.setdefault(r["policy"], {}).setdefault(r["prompt"], []).append(r)
    return {pol: [{"prompt": q, "speedup": float(np.mean([x["speedup"] for x in v])),
                   "tau": float(np.mean([x["tau"] for x in v]))} for q, v in d.items()] for pol, d in acc.items()}


# ---------------------------------------------------------------------------------------------------------------
def fig_headline(res: Path) -> str | None:
    sim = _load(res, "sim_results.json")
    if not sim:
        return None
    plt = _plt()
    best = sim.get("best_baseline")
    names = sorted(sim["table"], key=lambda n: sim["table"][n]["overall"]["speedup"])
    v = [sim["table"][n]["overall"] for n in names]
    fig, ax = plt.subplots(figsize=(7.4, 0.5 * len(names) + 1.4))
    y = np.arange(len(names))
    ax.barh(y, [x["speedup"] for x in v], color=[_color(n, best) for n in names], height=0.62)
    for i, x in enumerate(v):
        ax.plot([x["ci_low"], x["ci_high"]], [i, i], color=INK, lw=1.4, solid_capstyle="round")
        ax.text(x["ci_high"] + 0.02, i, f"{x['speedup']:.2f}×   τ {x['tau']:.1f}", va="center", fontsize=8.5, color=INK2)
    ax.axvline(1.0, color=MUTED, ls="--", lw=1)
    ax.set_yticks(y, [_label(n) + ("  (best tuned baseline)" if n == best else "") for n in names])
    ax.set_xlim(0.8, max(x["ci_high"] for x in v) + 0.55)
    ax.set_xlabel("speedup over autoregressive decoding (simulator, held-out test prompts; bar = mean, line = 95% CI)")
    ax.set_title("Throughput-trained policy vs tuned baselines", pad=10)
    ax.grid(axis="y", visible=False)
    return _save(fig, res, "headline_speedup.png")


def fig_by_dataset(res: Path) -> str | None:
    sim = _load(res, "sim_results.json")
    if not sim:
        return None
    plt = _plt()
    groups = [g for g in sim["groups"] if g != "overall"]
    best = sim.get("best_baseline")
    names = sorted(sim["table"], key=lambda n: -sim["table"][n]["overall"]["speedup"])
    fig, axes = plt.subplots(1, len(groups), figsize=(2.55 * len(groups) + 2.2, 3.4), sharey=True, sharex=True)
    axes = np.atleast_1d(axes)
    y = np.arange(len(names))[::-1]
    for ax, g in zip(axes, groups, strict=True):
        for yi, n in zip(y, names, strict=True):
            c = sim["table"][n][g]
            ax.plot([c["ci_low"], c["ci_high"]], [yi, yi], color=_color(n, best), lw=2, solid_capstyle="round")
            ax.scatter(c["speedup"], yi, s=34, color=_color(n, best), zorder=3, edgecolor="white", linewidth=0.8)
        ax.axvline(1.0, color=MUTED, ls="--", lw=1)
        ax.set_title(f"{g} (n={sim['table'][names[0]][g]['n']})", fontsize=10)
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(y, [_label(n) for n in names])
    fig.supxlabel("speedup over autoregressive (simulator, 95% CI)", fontsize=9, color=INK2, y=-0.02)
    fig.suptitle("Where does each policy help? Per test set", x=0.01, ha="left", fontweight="bold", fontsize=11, y=1.03)
    fig.tight_layout()
    return _save(fig, res, "by_dataset.png")


def fig_reward_ablation(res: Path) -> str | None:
    sim = _load(res, "sim_results.json")
    if not sim:
        return None
    rewards = [r for r in ("throughput", "acceptance", "time") if f"ltd-mini-{r}" in sim["table"]]
    if not rewards:
        return None
    plt = _plt()
    pooled = _pooled_real(res)
    real = {r: pooled.get(f"ltd-mini-{r}", []) for r in rewards}
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.5))
    for ax, key, title in zip(axes, ("speedup", "tau"), ("Speedup (higher is better)", "τ: tokens per cycle"), strict=True):
        for i, r in enumerate(rewards):
            s = sim["table"][f"ltd-mini-{r}"]["overall"]
            ax.bar(i - 0.2, s[key], 0.36, color=REWARD_COLOR[r])
            ax.text(i - 0.2, s[key] + 0.04, f"{s[key]:.2f}", ha="center", fontsize=8.5, color=INK2)
            if real[r]:
                m = float(np.mean([x[key] for x in real[r]]))
                ax.bar(i + 0.2, m, 0.36, color="white", edgecolor=REWARD_COLOR[r], hatch="////", linewidth=1.2)
                ax.text(i + 0.2, m + 0.04, f"{m:.2f}", ha="center", fontsize=8.5, color=INK2)
        ax.set_xticks(range(len(rewards)), [f"reward =\n{r}" for r in rewards])
        ax.set_title(title)
        ax.grid(axis="x", visible=False)
        if key == "speedup":
            ax.axhline(1.0, color=MUTED, ls="--", lw=1)
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(facecolor=MUTED, label="simulator (120 test prompts)"),
                        Patch(facecolor="white", edgecolor=MUTED, hatch="////", label="wall clock (real decoding)")],
               loc="lower center", ncol=2, fontsize=8.5, bbox_to_anchor=(0.5, -0.06))
    fig.suptitle("Reward ablation: optimizing acceptance length buys τ, not speed", x=0.01, ha="left",
                 fontweight="bold", fontsize=11, y=1.02)
    fig.tight_layout()
    return _save(fig, res, "reward_ablation.png")


def fig_training(res: Path) -> str | None:
    hist = sorted(res.glob("train_history_*.json"))
    if not hist:
        return None
    plt = _plt()
    base = _load(res, "baselines.json") or {}
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    for h in hist:
        d = json.loads(h.read_text())
        r = d["reward"]
        xs = [x["timesteps"] for x in d["history"]]
        ax.plot(xs, [x["speedup"] for x in d["history"]], color=REWARD_COLOR.get(r, INK2), lw=1.8, marker="o", ms=3.5,
                label=f"reward = {r}")
    if base:
        best = max(v["val_speedup"] for v in base.values())
        ax.axhline(best, color=C_BEST, ls="--", lw=1.2)
        ax.text(ax.get_xlim()[1], best - 0.012, "best tuned baseline (validation)", ha="right", va="top", fontsize=8,
                color=C_BEST)
    ax.set_xlabel("PPO timesteps")
    ax.set_ylabel("validation speedup (simulator)")
    ax.set_title("PPO training curves (checkpoint chosen on validation)")
    ax.legend(loc="center right", fontsize=8.5)
    return _save(fig, res, "training_curves.png")


def fig_behaviour(res: Path) -> str | None:
    b = _load(res, "behaviour.json")
    sim = _load(res, "sim_results.json")
    if not b:
        return None
    plt = _plt()
    best = (sim or {}).get("best_baseline")
    show = [n for n in b["policies"] if n.startswith(("ltd-mini", "fixed")) or n == best]
    mid = (np.array(b["bin_edges"][:-1]) + np.array(b["bin_edges"][1:])) / 2
    fig, axes = plt.subplots(1, 3, figsize=(12.6, 3.7))
    for n in show:
        p = b["policies"][n]
        ls = "-" if n.startswith("ltd") else ("--" if n == best else ":")
        for ax, key in zip(axes[:2], ("continue_rate_by_top1", "cycle_depth_by_first_top1"), strict=True):
            ys = [np.nan if v is None else v for v in p[key]]
            ax.plot(mid, ys, color=_color(n, best), ls=ls, lw=2 if n.startswith("ltd") else 1.5, marker="o", ms=3.5,
                    label=_label(n) + (" (best baseline)" if n == best else ""))
        dm = np.arange(1, b["dmax"] + 1)
        h = np.array(p["depth_histogram"], float)
        axes[2].plot(dm, 100 * h / h.sum(), color=_color(n, best), ls=ls, lw=2 if n.startswith("ltd") else 1.5,
                     marker="o", ms=3.5)
    axes[0].set_title("P(keep drafting) vs draft confidence")
    axes[0].set_xlabel("draft top-1 probability of the latest drafted token")
    axes[0].set_ylabel("fraction of decisions that continue")
    axes[1].set_title("Chosen depth vs first-token confidence")
    axes[1].set_xlabel("top-1 probability of the first drafted token of the cycle")
    axes[1].set_ylabel("mean depth chosen for that cycle")
    axes[2].set_title("Distribution of chosen depths")
    axes[2].set_xlabel("draft depth in a cycle")
    axes[2].set_ylabel("% of cycles")
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=len(lab), fontsize=8.5, bbox_to_anchor=(0.5, -0.07))
    fig.suptitle("What the learned policies actually do (held-out test traces, simulator)", x=0.01, ha="left",
                 fontweight="bold", fontsize=11, y=1.03)
    fig.tight_layout()
    return _save(fig, res, "policy_behaviour.png")


def fig_seeds(res: Path) -> str | None:
    rb = _load(res, "robustness/robustness.json")
    if not rb or "main" not in rb["variants"]:
        return None
    plt = _plt()
    main = rb["variants"]["main"]["rewards"]
    rewards = [r for r in ("throughput", "acceptance", "time") if r in main]
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    base12 = rb["baselines"].get("12") or next(iter(rb["baselines"].values()))
    best = max(base12.values())
    for i, r in enumerate(rewards):
        m = main[r]
        xs = i + np.linspace(-0.12, 0.12, len(m["runs"]))
        ys = [x["speedup"] for x in m["runs"]]
        ax.scatter(xs, ys, s=44, color=REWARD_COLOR[r], zorder=3, edgecolor="white")
        ax.hlines(m["mean"], i - 0.3, i + 0.3, color=REWARD_COLOR[r], lw=2.4)
        sd = f" ± {m['std']:.3f}" if m["std"] is not None else ""
        ax.text(i, max(ys) + 0.035, f"mean {m['mean']:.3f}{sd}", ha="center", fontsize=8.5, color=INK2)
    ax.axhline(best, color=C_BEST, ls="--", lw=1.2)
    ax.text(len(rewards) - 0.55, best + 0.012, "best tuned baseline (test)", ha="right", fontsize=8, color=C_BEST)
    ax.set_xticks(range(len(rewards)), rewards)
    ax.set_xlabel("PPO reward")
    ax.set_xlim(-0.55, len(rewards) - 0.45)
    ax.set_ylim(1.28, 1.93)
    ax.set_ylabel("test speedup (simulator)")
    ax.set_title(f"PPO seed variance ({rb['n_seeds']} seeds per reward)")
    ax.grid(axis="x", visible=False)
    return _save(fig, res, "seeds.png")


def fig_ablations(res: Path) -> str | None:
    rb = _load(res, "robustness/robustness.json")
    if not rb:
        return None
    plt = _plt()
    labels = {"main": "default", "no_history": "no history\nfeatures", "no_timing_noise": "no timing noise\nin training",
              "dmax8": "dmax = 8"}
    vs = [v for v in labels if v in rb["variants"] and "throughput" in rb["variants"][v]["rewards"]]
    fig, ax = plt.subplots(figsize=(7.6, 3.7))
    for i, v in enumerate(vs):
        m = rb["variants"][v]["rewards"]["throughput"]
        xs = i + np.linspace(-0.12, 0.12, len(m["runs"]))
        ax.scatter(xs, [x["speedup"] for x in m["runs"]], s=42, color=C_THR, zorder=3, edgecolor="white")
        ax.hlines(m["mean"], i - 0.28, i + 0.28, color=C_THR, lw=2.4)
        ax.text(i, 0.97, f"mean {m['mean']:.3f}", ha="center", va="top", fontsize=8.5, color=INK2,
                transform=ax.get_xaxis_transform())
        bl = rb["baselines"][str(rb["variants"][v]["dmax"])]
        bb = max(bl.values())
        ax.hlines(bb, i - 0.34, i + 0.34, color=C_BEST, ls="--", lw=1.3)
    ax.set_xticks(range(len(vs)), [labels[v] for v in vs])
    ax.set_ylabel("test speedup (simulator)")
    ax.set_ylim(1.77, 1.865)
    ax.set_title("Ablations of the throughput-reward policy")
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], marker="o", color=C_THR, lw=0, label="one PPO seed"),
                       Line2D([], [], color=C_THR, lw=2.4, label="mean over seeds"),
                       Line2D([], [], color=C_BEST, ls="--", label="best tuned baseline at that dmax")],
              fontsize=8, loc="lower left")
    ax.grid(axis="x", visible=False)
    return _save(fig, res, "ablations.png")


OFFSETS = {"ltd-mini-throughput": (14, 38), "cumulative-h0.65": (-110, 34), "confidence-h0.70": (-120, -26),
           "entropy-h0.087": (18, -42)}


def fig_sim_vs_real(res: Path) -> str | None:
    sim = _load(res, "sim_results.json")
    pooled = _pooled_real(res)
    if not sim or not pooled:
        return None
    from .stats import bootstrap_ci
    plt = _plt()
    best = sim.get("best_baseline")
    fig, ax = plt.subplots(figsize=(6.2, 5.6))
    pts = []
    for n in sim["table"]:
        rs = [r["speedup"] for r in pooled.get(n, [])]
        if rs:
            m, lo, hi = bootstrap_ci(rs)
            s = sim["table"][n]["overall"]
            pts.append((n, s["speedup"], s["ci_low"], s["ci_high"], m, lo, hi))
    for n, s, slo, shi, m, lo, hi in pts:
        c = _color(n, best)
        ax.errorbar(s, m, xerr=[[s - slo], [shi - s]], yerr=[[m - lo], [hi - m]], fmt="o", color=c, ms=6.5,
                    mec="white", elinewidth=1.2, capsize=0, zorder=3)
        dx, dy = OFFSETS.get(n, (8, -12))
        ax.annotate(_label(n), (s, m), fontsize=7.5, xytext=(dx, dy), textcoords="offset points", color=INK2,
                    arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.6, "shrinkA": 0, "shrinkB": 3})
    lim = [min(min(p[1], p[4]) for p in pts) - 0.15, max(max(p[1], p[4]) for p in pts) + 0.15]
    ax.plot(lim, lim, "--", color=MUTED, lw=1)
    ax.text(lim[0] + 0.12, lim[0] + 0.07, "y = x (perfect prediction)", rotation=45, rotation_mode="anchor",
            fontsize=8, color=MUTED)
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_aspect("equal")
    ax.set_xlabel("simulated speedup (120 test prompts)")
    ax.set_ylabel(f"measured speedup (wall clock, {len(next(iter(pooled.values())))} prompts, runs averaged)")
    ax.set_title("Does the simulator predict reality?")
    return _save(fig, res, "sim_vs_real.png")


def fig_timing(res: Path) -> str | None:
    raw = _load(res, "timing_raw.json")
    if not raw or not (res / "timing.json").exists():
        return None
    from .timing import TimingModel
    tm = TimingModel.load(res / "timing.json")
    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.5))
    Ls = np.linspace(min(L for L, _ in raw["ar"]), max(L for L, _ in raw["ar"]), 50)
    ax = axes[0]
    ax.scatter(*zip(*[(L, t * 1e3) for L, t in raw["ar"]], strict=True), color=C_BEST, s=36, zorder=3, label="target, 1 token (measured)")
    ax.plot(Ls, [tm.ar_step(L) * 1e3 for L in Ls], color=C_BEST, lw=1.6)
    ax.scatter(*zip(*[(L, t * 1e3) for L, t in raw["draft"]], strict=True), color=C_THR, s=36, zorder=3, label="draft, 1 token (measured)")
    ax.plot(Ls, [tm.draft_step(L) * 1e3 for L in Ls], color=C_THR, lw=1.6)
    ax.set_xlabel("context length L (tokens)")
    ax.set_ylabel("step time (ms)")
    ax.set_ylim(bottom=0)
    ax.set_title("Draft step vs target step")
    ax.legend(fontsize=8, loc="center right")
    ax = axes[1]
    Lset = sorted({L for _, L, _ in raw["verify"]})
    shades = ["#2a78d6", "#7aaae8", "#b7d0f2"][: len(Lset)]
    for L, c in zip(Lset[::-1], shades, strict=False):
        pts = sorted((k, t * 1e3) for k, LL, t in raw["verify"] if LL == L)
        ax.scatter(*zip(*pts, strict=True), s=22, color=c, zorder=3)
        ks = np.arange(1, max(k for k, _ in pts) + 1)
        ax.plot(ks, [tm.verify(int(k), L) * 1e3 for k in ks], color=c, lw=1.5, label=f"L = {L}")
    ax.set_xlabel("k = drafted tokens verified in one target pass")
    ax.set_ylabel("verify time (ms)")
    ax.set_ylim(bottom=0)
    ax.set_title("Verification cost grows slowly with k")
    ax.legend(title="points = measured, lines = fit", fontsize=8, title_fontsize=8, loc="lower right")
    fig.tight_layout()
    return _save(fig, res, "timing_fit.png")


def fig_repeatability(res: Path) -> str | None:
    files = sorted(res.glob("real_results*.jsonl"))
    files = [f for f in files if "backup" not in f.name and "cpu" not in f.name]
    if len(files) < 2:
        return None
    plt = _plt()
    runs = [_rows(f) for f in files]
    pols = sorted({r["policy"] for r in runs[0]}, key=lambda n: -np.mean([r["speedup"] for r in runs[0] if r["policy"] == n]))
    best = (_load(res, "sim_results.json") or {}).get("best_baseline")
    marks = ["o", "s", "^", "D"]
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    for i, n in enumerate(pols):
        for j, rr in enumerate(runs):
            m = float(np.mean([r["speedup"] for r in rr if r["policy"] == n]))
            ax.scatter(i + (j - (len(runs) - 1) / 2) * 0.16, m, marker=marks[j % 4], s=40, color=_color(n, best), zorder=3,
                       edgecolor="white")
    ax.set_xticks(range(len(pols)), [_label(n).replace("LTD-Mini · ", "LTD · ") for n in pols], rotation=25, ha="right")
    ax.set_ylabel("mean wall-clock speedup (same 32 prompts)")
    ax.set_title(f"Wall-clock repeatability: {len(runs)} independent runs")
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], marker=marks[j % 4], color=MUTED, lw=0, label=f"run {j + 1}") for j in range(len(runs))],
              fontsize=8, loc="lower left", ncol=len(runs))
    ax.grid(axis="x", visible=False)
    return _save(fig, res, "repeatability.png")


def make_all(res: Path) -> list[str]:
    figs = [fig_headline, fig_by_dataset, fig_reward_ablation, fig_training, fig_behaviour, fig_seeds, fig_ablations,
            fig_sim_vs_real, fig_timing, fig_repeatability]
    out = []
    for f in figs:
        try:
            p = f(res)
        except Exception as e:  # noqa: BLE001 - a broken optional figure must not block the report; say so loudly
            print(f"[figures] {f.__name__} failed: {e!r}")
            continue
        if p:
            out.append(p)
    return out
