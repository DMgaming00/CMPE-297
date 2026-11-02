"""Regenerate REPORT.md and figures from the files in a results directory.

Every number in the report comes from a file written by an earlier stage; the
report never computes or invents results of its own beyond aggregation.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .figures import make_all


def _fmt(x, nd=2):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def sim_table_md(sim: dict) -> str:
    groups = sim["groups"]
    head = "| Policy | " + " | ".join(groups) + " |\n|---|" + "---|" * len(groups) + "\n"
    rows = []
    for name, by_g in sorted(sim["table"].items(), key=lambda kv: -kv[1]["overall"]["speedup"]):
        cells = [f"{_fmt(v['speedup'])}× [{_fmt(v['ci_low'])}, {_fmt(v['ci_high'])}] · τ {_fmt(v['tau'])}"
                 for v in (by_g[g] for g in groups)]
        rows.append(f"| {name} | " + " | ".join(cells) + " |")
    return head + "\n".join(rows) + "\n"


def paired_md(sim: dict) -> str:
    if not sim.get("paired_vs_reference"):
        return "_No paired comparison (no reference policy)._\n"
    out = [f"Reference: **{sim['reference']}** (per-sequence speedup differences, 95% paired bootstrap CI)\n",
           "| Policy | Mean Δ speedup | 95% CI | Wins | Significant |", "|---|---|---|---|---|"]
    for name, d in sorted(sim["paired_vs_reference"].items(), key=lambda kv: -kv[1]["mean_diff"]):
        out.append(f"| {name} | {d['mean_diff']:+.3f} | [{d['ci_low']:+.3f}, {d['ci_high']:+.3f}] | "
                   f"{d['win_rate'] * 100:.0f}% | {'yes' if d['significant'] else 'no'} |")
    text = "\n".join(out) + "\n"
    if sim.get("paired_vs_best_baseline"):
        text += (f"\nLearned policies vs the best tuned baseline, **{sim['best_baseline']}** "
                 "(per-sequence speedup differences, 95% paired bootstrap CI)\n\n"
                 "| Policy | Mean Δ speedup | 95% CI | Wins | Significant |\n|---|---|---|---|---|\n")
        for name, d in sorted(sim["paired_vs_best_baseline"].items(), key=lambda kv: -kv[1]["mean_diff"]):
            text += (f"| {name} | {d['mean_diff']:+.3f} | [{d['ci_low']:+.3f}, {d['ci_high']:+.3f}] | "
                     f"{d['win_rate'] * 100:.0f}% | {'yes' if d['significant'] else 'no'} |\n")
    return text


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def _real_runs(res: Path) -> list[list[dict]]:
    files = [f for f in sorted(res.glob("real_results*.jsonl")) if "backup" not in f.name]
    return [r for r in (_rows(f) for f in files) if r]


def _per_prompt(runs: list[list[dict]], key: str = "speedup") -> dict[str, dict[str, float]]:
    """policy -> prompt -> value averaged over independent runs (the prompt is the unit of resampling)."""
    acc: dict[str, dict[str, list[float]]] = {}
    for rr in runs:
        for r in rr:
            acc.setdefault(r["policy"], {}).setdefault(r["prompt"], []).append(float(r[key]))
    return {p: {q: float(np.mean(v)) for q, v in d.items()} for p, d in acc.items()}


def real_table_md(runs: list[list[dict]]) -> str:
    from .stats import bootstrap_ci
    sp, tau, depth = _per_prompt(runs), _per_prompt(runs, "tau"), _per_prompt(runs, "mean_depth")
    rows_all = [r for rr in runs for r in rr]
    out = ["| Policy | Mean speedup [95% CI over prompts] | τ | Mean depth | Exact output match | Mean token-match rate |",
           "|---|---|---|---|---|---|"]
    for name in sorted(sp, key=lambda n: -np.mean(list(sp[n].values()))):
        m, lo, hi = bootstrap_ci(list(sp[name].values()))
        rs = [r for r in rows_all if r["policy"] == name]
        out.append(f"| {name} | {m:.2f}× [{lo:.2f}, {hi:.2f}] | {np.mean(list(tau[name].values())):.2f} | "
                   f"{np.mean(list(depth[name].values())):.2f} | {100 * np.mean([r['exact_match'] for r in rs]):.0f}% | "
                   f"{100 * np.mean([r['token_match_rate'] for r in rs]):.1f}% |")
    n_prompts = len(next(iter(sp.values())))
    return "\n".join(out) + f"\n\n_{n_prompts} prompts × {len(runs)} independent run(s); speedups are averaged over runs per prompt first._\n"


def real_paired_md(runs: list[list[dict]]) -> str:
    from .stats import paired_bootstrap_diff
    sp = _per_prompt(runs)
    learned = [n for n in sp if n.startswith("ltd-mini")]
    base = [n for n in sp if not n.startswith("ltd-mini")]
    if not learned or not base:
        return ""
    best = max(base, key=lambda n: np.mean(list(sp[n].values())))
    prompts = sorted(sp[best])
    out = [f"\nWall clock, learned vs the best baseline here (**{best}**), paired over prompts:\n",
           "| Policy | Mean Δ speedup | 95% CI | Wins | Significant |", "|---|---|---|---|---|"]
    for n in sorted(learned, key=lambda n: -np.mean(list(sp[n].values()))):
        d = paired_bootstrap_diff([sp[n][q] for q in prompts], [sp[best][q] for q in prompts])
        out.append(f"| {n} | {d['mean_diff']:+.3f} | [{d['ci_low']:+.3f}, {d['ci_high']:+.3f}] | "
                   f"{d['win_rate'] * 100:.0f}% | {'yes' if d['significant'] else 'no'} |")
    return "\n".join(out) + "\n"


def repeat_md(runs: list[list[dict]]) -> str:
    if len(runs) < 2:
        return ""
    pols = sorted({r["policy"] for r in runs[0]})
    head = "| Policy | " + " | ".join(f"run {i + 1}" for i in range(len(runs))) + " | spread (max − min) |\n"
    out = [head + "|---|" + "---|" * (len(runs) + 1)]
    for n in sorted(pols, key=lambda n: -np.mean([r["speedup"] for r in runs[0] if r["policy"] == n])):
        ms = [float(np.mean([r["speedup"] for r in rr if r["policy"] == n])) for rr in runs]
        out.append(f"| {n} | " + " | ".join(f"{m:.3f}×" for m in ms) + f" | {max(ms) - min(ms):.3f} |")
    return "\n".join(out) + "\n"


def exactness_md(res: Path, runs: list[list[dict]]) -> str:
    settings = [("fp16 on MPS (main runs)", [r for rr in runs for r in rr]),
                ("fp32 on MPS", _rows(res / "mps_fp32" / "real_results.jsonl")),
                ("fp32 on CPU (64 new tokens)", _rows(res / "cpu_fp32" / "real_results.jsonl"))]
    out = ["| Setting | Policy | Decodes | Exact output match | Mean token-match rate |", "|---|---|---|---|---|"]
    for label, rows in settings:
        if not rows:
            out.append(f"| {label} | — | — | NOT YET MEASURED | — |")
            continue
        for n in sorted({r["policy"] for r in rows}):
            rs = [r for r in rows if r["policy"] == n]
            out.append(f"| {label} | {n} | {len(rs)} | {100 * np.mean([r['exact_match'] for r in rs]):.0f}% | "
                       f"{100 * np.mean([r['token_match_rate'] for r in rs]):.1f}% |")
    txt = "\n".join(out) + "\n"
    mps = settings[0][1]
    div = [r["first_divergence"] for r in mps if r.get("first_divergence", -1) >= 0]
    n_rec = sum("first_divergence" in r for r in mps)
    if div:
        txt += (f"\nOf the {n_rec} fp16 decodes that recorded divergence info, {len(div)} diverged from the target's "
                f"greedy output; the first differing token was at generated position median {int(np.median(div))} "
                f"(min {min(div)}, max {max(div)}).\n")
    return txt


def robustness_md(res: Path) -> str:
    p = res / "robustness" / "robustness.json"
    if not p.exists():
        return ""
    rb = json.loads(p.read_text())
    out = [f"### PPO seeds ({rb['n_seeds']} seeds per reward, held-out test, simulator)\n",
           "| Reward | Per-seed speedup | Mean ± std | Mean τ | Seeds significantly better / worse than best tuned baseline |",
           "|---|---|---|---|---|"]
    main = rb["variants"].get("main", {}).get("rewards", {})
    for r, m in main.items():
        std = f"{m['std']:.3f}" if m["std"] is not None else "n/a"
        out.append(f"| {r} | " + ", ".join(f"{x['speedup']:.3f}" for x in m["runs"]) +
                   f" | {m['mean']:.3f} ± {std} | {m['mean_tau']:.2f} | {m['seeds_significantly_better']} / "
                   f"{m['seeds_significantly_worse']} of {len(m['runs'])} |")
    base = rb["baselines"].get("12") or next(iter(rb["baselines"].values()), {})
    if base:
        b = max(base, key=base.get)
        out.append(f"\nBest tuned baseline on the same test set: `{b}` at {base[b]:.3f}×.\n")
    abl = [(v, rb["variants"][v]) for v in ("no_history", "no_timing_noise", "dmax8") if v in rb["variants"]]
    if abl:
        out += ["\n### Ablations (throughput reward, same seeds)\n",
                "| Variant | Per-seed speedup | Mean ± std | Best tuned baseline at that dmax | Mean Δ vs that baseline (paired) |",
                "|---|---|---|---|---|"]
        rows = [("default", rb["variants"]["main"])] + abl if "main" in rb["variants"] else abl
        for v, d in rows:
            m = d["rewards"]["throughput"]
            bl = rb["baselines"][str(d["dmax"])]
            bb = max(bl, key=bl.get)
            std = f"{m['std']:.3f}" if m["std"] is not None else "n/a"
            out.append(f"| {v} | " + ", ".join(f"{x['speedup']:.3f}" for x in m["runs"]) + f" | {m['mean']:.3f} ± {std} | "
                       f"{bb} ({bl[bb]:.3f}) | {m['mean_diff_vs_best_baseline']:+.3f} |")
    return "\n".join(out) + "\n"


def _fig(figs: list[str], name: str) -> str:
    return f"![{name}](figures/{name}.png)\n" if f"figures/{name}.png" in figs else ""


def build_report(res: Path) -> Path:
    figs = make_all(res)
    note = ("_Generated by `ltdmini report` from the files in this folder. Do not edit by hand. "
            "Every number below is read from a file written by an earlier stage._\n")
    parts = [f"# Results — `{res.name}`\n", note]
    sim_p = res / "sim_results.json"
    runs = _real_runs(res)
    if sim_p.exists():
        sim = json.loads(sim_p.read_text())
        learned = sim.get("paired_vs_best_baseline", {})
        thr = sim["table"].get("ltd-mini-throughput", {}).get("overall")
        glance = []
        if thr and "ltd-mini-throughput" in learned:
            d, bb = learned["ltd-mini-throughput"], sim["best_baseline"]
            glance.append(f"- Simulated test speedup of the throughput-reward policy: **{thr['speedup']:.2f}×** "
                          f"[{thr['ci_low']:.2f}, {thr['ci_high']:.2f}]; best tuned baseline `{bb}`: "
                          f"{sim['table'][bb]['overall']['speedup']:.2f}×. Paired difference "
                          f"{d['mean_diff']:+.3f} [{d['ci_low']:+.3f}, {d['ci_high']:+.3f}] "
                          f"({'significant' if d['significant'] else 'not significant'}).")
        if runs:
            sp = _per_prompt(runs)
            if "ltd-mini-throughput" in sp:
                glance.append(f"- Wall-clock speedup of the same policy: **{np.mean(list(sp['ltd-mini-throughput'].values())):.2f}×** "
                              f"({len(sp['ltd-mini-throughput'])} prompts × {len(runs)} run(s)).")
        if glance:
            parts.append("## At a glance\n\n" + "\n".join(glance) + "\n\n" + _fig(figs, "headline_speedup"))
    env_p = res / "environment.json"
    if env_p.exists():
        env = json.loads(env_p.read_text())
        parts.append("## Environment\n\n" + "\n".join(f"- **{k}:** {v}" for k, v in env.items()) + "\n")
    tm_p = res / "timing.json"
    if tm_p.exists():
        tm = json.loads(tm_p.read_text())
        parts.append("## Timing model\n\n" + f"Device `{tm['device']}` — {tm['note']}.\n\n"
                     f"- draft step ≈ {tm['d0'] * 1e3:.2f} ms + {tm['d1'] * 1e6:.3f} µs·L\n"
                     f"- verify(k) ≈ {tm['v0'] * 1e3:.2f} ms + {tm['v1'] * 1e3:.3f} ms·k + {tm['v2'] * 1e6:.3f} µs·L\n"
                     f"- autoregressive step ≈ {tm['a0'] * 1e3:.2f} ms + {tm['a1'] * 1e6:.3f} µs·L\n\n" + _fig(figs, "timing_fit"))
    b_p = res / "baselines.json"
    if b_p.exists():
        b = json.loads(b_p.read_text())
        parts.append("## Tuned baselines (validation grid search)\n\n" +
                     "\n".join(f"- **{fam}:** `{v['policy']}` (val speedup {v['val_speedup']:.3f})" for fam, v in b.items()) + "\n")
    if sim_p.exists():
        parts.append("## Simulated evaluation on held-out traces\n\nSpeedup vs autoregressive "
                     "[95% bootstrap CI] · τ = mean tokens per cycle.\n\n" + sim_table_md(sim) + "\n" + paired_md(sim)
                     + "\n" + _fig(figs, "by_dataset") + "\n## Reward ablation (paper Table 2)\n\n" + _fig(figs, "reward_ablation"))
    if _fig(figs, "training_curves"):
        parts.append("## Training curves\n\n" + _fig(figs, "training_curves"))
    if _fig(figs, "policy_behaviour"):
        parts.append("## What the learned policy does\n\n" + _fig(figs, "policy_behaviour"))
    rob = robustness_md(res)
    if rob:
        parts.append("## Robustness: seeds and ablations\n\n" + rob + "\n" + _fig(figs, "seeds") + "\n" + _fig(figs, "ablations"))
    if runs:
        parts.append("## Real end-to-end evaluation (wall clock)\n\n" + real_table_md(runs) + real_paired_md(runs)
                     + "\n" + _fig(figs, "sim_vs_real"))
        if len(runs) > 1:
            parts.append("### Repeatability\n\nMean wall-clock speedup per independent run (same prompts, same policies, "
                         "run at different times):\n\n" + repeat_md(runs) + "\n" + _fig(figs, "repeatability"))
        parts.append("### Output exactness\n\n" + exactness_md(res, runs))
    sel = res.parent / "model_selection" / "pairs.md"
    if sel.exists():
        parts.append("## Model-pair selection\n\n" + sel.read_text())
    out = res / "REPORT.md"
    out.write_text("\n".join(parts))
    return out
