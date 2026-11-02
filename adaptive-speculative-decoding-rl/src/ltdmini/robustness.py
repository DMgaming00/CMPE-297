"""Robustness experiments: PPO seeds, ablations, and a look at what the learned policy actually does.

    ltdmini robust    --config C [--seeds 3]   seeds for every reward + ablations (throughput reward)
    ltdmini behaviour --config C               depth vs draft top-1 probability, learned vs baselines

Everything is trained in the simulator on the TRAIN traces, checkpoints are selected on VAL, and all numbers reported
here are on the held-out TEST traces. Runs are resumable: a finished policy file is never retrained.

Variants (all trained with the throughput reward unless noted):
    main             the default setup (all three rewards, for the reward-ablation spread)
    no_history       the two history features (recent_accept, last_accept_frac) are zeroed
    no_timing_noise  PPO trains with deterministic simulated step times (no multiplicative noise)
    dmax8            maximum draft depth 8 instead of 12 (baselines are re-tuned at dmax 8 too)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .config import Config
from .evaluate import evaluate_sim
from .policies import IDX, MLPPolicy
from .sim import SimCore
from .timing import TimingModel
from .tune import tune_baselines

VARIANTS = {
    "main": {"rewards": ("throughput", "acceptance", "time")},
    "no_history": {"rewards": ("throughput",), "mask": ("recent_accept", "last_accept_frac")},
    "no_timing_noise": {"rewards": ("throughput",), "noise": 0.0},
    "dmax8": {"rewards": ("throughput",), "dmax": 8},
}


def _load_split(cfg: Config, split: str):
    from .traces import load_traces
    return load_traces(cfg.out / f"traces_{split}.npz")


def run_robust(cfg: Config, n_seeds: int = 3, variants: tuple[str, ...] = tuple(VARIANTS)) -> dict:
    from .train import train_ppo
    train, vocab = _load_split(cfg, "train")
    val, _ = _load_split(cfg, "val")
    test, _ = _load_split(cfg, "test")
    tm = TimingModel.load(cfg.out / "timing.json")
    t = cfg.train
    root = cfg.out / "robustness"
    res_path = root / "robustness.json"
    out: dict = {"n_seeds": n_seeds, "variants": {}, "baselines": {}}
    baselines_by_dmax: dict[int, dict] = {}

    for vname in variants:
        v = VARIANTS[vname]
        dmax = v.get("dmax", cfg.decode.dmax)
        if dmax not in baselines_by_dmax:
            baselines_by_dmax[dmax], _ = tune_baselines(val, tm, vocab, dmax)
        base = {p.name: p for p in baselines_by_dmax[dmax].values()}
        mask = tuple(IDX[n] for n in v.get("mask", ()))
        noise = v.get("noise", t.timing_noise)
        out["variants"][vname] = {"dmax": dmax, "mask": list(v.get("mask", ())), "train_noise": noise, "rewards": {}}
        for reward in v["rewards"]:
            runs = []
            for seed in range(n_seeds):
                d = root / vname / f"seed{seed}"
                pol_path = d / f"policy_{reward}.json"
                if not pol_path.exists():
                    print(f"[robust] training variant={vname} reward={reward} seed={seed}", flush=True)
                    train_ppo(train, val, tm, vocab, dmax, reward, t.total_timesteps, t.n_steps, t.batch_size,
                              t.learning_rate, t.gamma, t.net_arch, t.eval_every, noise, seed, d, mask=mask)
                pol = MLPPolicy.load(pol_path)
                pols = {**base, pol.name: pol}
                ev = evaluate_sim(pols, test, tm, vocab, dmax, reference=None, noise=t.timing_noise)
                o = ev["table"][pol.name]["overall"]
                bb = ev["best_baseline"]
                runs.append({
                    "seed": seed, "speedup": o["speedup"], "ci_low": o["ci_low"], "ci_high": o["ci_high"],
                    "tau": o["tau"], "mean_depth": o["mean_depth"],
                    "by_group": {g: x["speedup"] for g, x in ev["table"][pol.name].items() if g != "overall"},
                    "best_baseline": bb, "best_baseline_speedup": ev["table"][bb]["overall"]["speedup"],
                    "vs_best_baseline": ev["paired_vs_best_baseline"][pol.name],
                })
                print(f"[robust] {vname}/{reward}/seed{seed}: {o['speedup']:.3f}x  tau {o['tau']:.2f}  "
                      f"depth {o['mean_depth']:.2f}  vs best baseline {bb}: "
                      f"{ev['paired_vs_best_baseline'][pol.name]['mean_diff']:+.3f}", flush=True)
            sp = np.array([r["speedup"] for r in runs])
            out["variants"][vname]["rewards"][reward] = {
                "runs": runs, "mean": float(sp.mean()), "std": float(sp.std(ddof=1)) if len(sp) > 1 else None,
                "min": float(sp.min()), "max": float(sp.max()),
                "mean_tau": float(np.mean([r["tau"] for r in runs])),
                "mean_diff_vs_best_baseline": float(np.mean([r["vs_best_baseline"]["mean_diff"] for r in runs])),
                "seeds_significantly_better": int(sum(r["vs_best_baseline"]["ci_low"] > 0 for r in runs)),
                "seeds_significantly_worse": int(sum(r["vs_best_baseline"]["ci_high"] < 0 for r in runs)),
            }
        out["baselines"][str(dmax)] = {
            p.name: ev["table"][p.name]["overall"]["speedup"] for p in baselines_by_dmax[dmax].values()}
        root.mkdir(parents=True, exist_ok=True)
        res_path.write_text(json.dumps(out, indent=2))
    print(f"-> {res_path}")
    return out


def _decisions(policy, traces, tm: TimingModel, vocab: int, dmax: int):
    """Replay `policy` on traces (no timing noise) and log every continue/stop decision and every cycle."""
    core = SimCore(tm, vocab, dmax, "throughput", 0.0)
    dec, cyc = [], []
    for tr in traces:
        policy.reset()
        obs, done = core.reset(tr), False
        first_top1 = float(obs[IDX["top1_prob"]])
        while not done:
            cont = policy.should_continue(obs)
            dec.append((float(obs[IDX["top1_prob"]]), round(float(obs[IDX["depth_frac"]]) * dmax), cont))
            n_before = len(core.cycles)
            obs, _, done, _ = core.step(cont)
            if len(core.cycles) > n_before:
                cyc.append((first_top1, core.cycles[-1].depth))
                if obs is not None:
                    first_top1 = float(obs[IDX["top1_prob"]])
    return np.array(dec, dtype=float), np.array(cyc, dtype=float)


def run_behaviour(cfg: Config, policies: dict) -> Path:
    test, vocab = _load_split(cfg, "test")
    tm = TimingModel.load(cfg.out / "timing.json")
    dmax = cfg.decode.dmax
    edges = np.linspace(0.0, 1.0, 11)
    out: dict = {"bin_edges": edges.tolist(), "dmax": dmax, "policies": {}}
    for name, pol in policies.items():
        dec, cyc = _decisions(pol, test, tm, vocab, dmax)
        b_dec = np.clip(np.digitize(dec[:, 0], edges) - 1, 0, 9)
        b_cyc = np.clip(np.digitize(cyc[:, 0], edges) - 1, 0, 9)
        out["policies"][name] = {
            "continue_rate_by_top1": [float(dec[b_dec == i, 2].mean()) if (b_dec == i).sum() >= 20 else None
                                      for i in range(10)],
            "n_decisions_by_top1": [int((b_dec == i).sum()) for i in range(10)],
            "cycle_depth_by_first_top1": [float(cyc[b_cyc == i, 1].mean()) if (b_cyc == i).sum() >= 20 else None
                                          for i in range(10)],
            "n_cycles_by_first_top1": [int((b_cyc == i).sum()) for i in range(10)],
            "depth_histogram": [int((cyc[:, 1] == d).sum()) for d in range(1, dmax + 1)],
            "mean_depth": float(cyc[:, 1].mean()), "n_cycles": len(cyc),
        }
    path = cfg.out / "behaviour.json"
    path.write_text(json.dumps(out, indent=2))
    return path
