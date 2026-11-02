"""Command-line interface.

    ltdmini profile   --config configs/mac.yaml      measure step times -> timing.json
    ltdmini traces    --config configs/mac.yaml      build train/val/test traces
    ltdmini tune      --config configs/mac.yaml      grid-search baselines on validation traces
    ltdmini train     --config configs/mac.yaml [--reward throughput|acceptance|time|all]
    ltdmini eval-sim  --config configs/mac.yaml      simulated eval on test traces (+ CIs)
    ltdmini eval-real --config configs/mac.yaml      wall-clock eval with the real models
    ltdmini report    --config configs/mac.yaml      regenerate REPORT.md + figures
    ltdmini robust    --config configs/mac.yaml [--seeds 3]   PPO seeds + ablations (resumable)
    ltdmini behaviour --config configs/mac.yaml      what the learned policy does vs draft confidence
    ltdmini all       --config configs/mac.yaml      the seven core stages above, in order
    ltdmini synthetic-demo                           NumPy-only pipeline on synthetic traces
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import Config, load_config
from .env_info import environment
from .evaluate import evaluate_sim, save_json
from .policies import MLPPolicy, baseline_grid
from .report import build_report
from .timing import TimingModel
from .traces import load_traces, save_traces, synthetic_traces
from .tune import tune_baselines

REWARDS = ("throughput", "acceptance", "time")


def _pair(cfg: Config):
    from .models import load_pair
    m = cfg.models
    return load_pair(m.target, m.draft, m.device, m.dtype, m.revision_target, m.revision_draft)


def _offline(cfg: Config) -> bool:
    return cfg.models.target == "random-tiny"


def cmd_profile(cfg: Config) -> None:
    from .profile import profile_pair
    pair = _pair(cfg)
    print(f"Profiling {cfg.models.target} / {cfg.models.draft} on {pair.device} ({pair.dtype})")
    tm, raw = profile_pair(pair, cfg.decode.dmax)
    tm.save(cfg.out / "timing.json")
    (cfg.out / "timing_raw.json").write_text(json.dumps(raw))
    save_json(environment() | {"target": cfg.models.target, "draft": cfg.models.draft,
                                "device": str(pair.device), "dtype": str(pair.dtype)}, cfg.out / "environment.json")
    print(f"-> {cfg.out / 'timing.json'}")


def cmd_traces(cfg: Config) -> None:
    from .build_traces import build_traces
    from .data import load_prompts
    pair = _pair(cfg)
    d = cfg.data
    off = _offline(cfg)
    splits = {
        "train": [p for s in d.train for p in load_prompts(s, d.n_train, d.seed, 0, off)],
        "val": [p for s in d.val for p in load_prompts(s, d.n_val, d.seed, d.n_train, off)],
        "test": [p for s in d.test for p in load_prompts(s, d.n_test_per_set, d.seed + 1, 0, off)],
    }
    for split, prompts in splits.items():
        print(f"Building {split} traces from {len(prompts)} prompts")
        tr = build_traces(pair, prompts, cfg.decode.max_new_tokens, cfg.decode.dmax, d.max_prompt_tokens)
        save_traces(tr, cfg.out / f"traces_{split}.npz", pair.vocab_size,
                    meta={"target": cfg.models.target, "draft": cfg.models.draft, "split": split})


def _load(cfg: Config, split: str):
    return load_traces(cfg.out / f"traces_{split}.npz")


def cmd_tune(cfg: Config) -> dict:
    val, vocab = _load(cfg, "val")
    tm = TimingModel.load(cfg.out / "timing.json")
    best, rows = tune_baselines(val, tm, vocab, cfg.decode.dmax)
    from .sim import simulate, summarize
    out = {fam: {"policy": p.name, "val_speedup": summarize(simulate(p, val, tm, vocab, cfg.decode.dmax))["speedup"]}
           for fam, p in best.items()}
    save_json(out, cfg.out / "baselines.json")
    import csv
    with (cfg.out / "baseline_grid.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    for fam, v in out.items():
        print(f"  best {fam:<11} {v['policy']:<20} val speedup {v['val_speedup']:.3f}")
    return out


def cmd_train(cfg: Config, reward: str) -> None:
    from .train import train_ppo
    train, vocab = _load(cfg, "train")
    val, _ = _load(cfg, "val")
    tm = TimingModel.load(cfg.out / "timing.json")
    t = cfg.train
    for r in (REWARDS if reward == "all" else (reward,)):
        print(f"Training depth policy with PPO, reward = {r}")
        train_ppo(train, val, tm, vocab, cfg.decode.dmax, r, t.total_timesteps, t.n_steps, t.batch_size,
                  t.learning_rate, t.gamma, t.net_arch, t.eval_every, t.timing_noise, t.seed, cfg.out)


def _policies(cfg: Config, src: Path | None = None) -> tuple[dict, str | None]:
    src = src or cfg.out
    pols = {}
    b_p = src / "baselines.json"
    if b_p.exists():
        names = {v["policy"] for v in json.loads(b_p.read_text()).values()}
        pols.update({p.name: p for p in baseline_grid(cfg.decode.dmax) if p.name in names})
    for p in sorted(src.glob("policy_*.json")):
        mp = MLPPolicy.load(p)
        pols[mp.name] = mp
    fixed = [n for n in pols if n.startswith("fixed")]
    return pols, (fixed[0] if fixed else None)


def cmd_eval_sim(cfg: Config) -> None:
    test, vocab = _load(cfg, "test")
    tm = TimingModel.load(cfg.out / "timing.json")
    pols, ref = _policies(cfg)
    res = evaluate_sim(pols, test, tm, vocab, cfg.decode.dmax, reference=ref, noise=cfg.train.timing_noise)
    save_json(res, cfg.out / "sim_results.json")
    for name, by_g in sorted(res["table"].items(), key=lambda kv: -kv[1]["overall"]["speedup"]):
        o = by_g["overall"]
        print(f"  {name:<24} {o['speedup']:.3f}x [{o['ci_low']:.3f}, {o['ci_high']:.3f}]  tau {o['tau']:.2f}")


def cmd_eval_real(cfg: Config, n_prompts: int | None, tag: str = "", policies_from: str | None = None) -> None:
    from .data import load_prompts
    from .real_eval import evaluate_real
    pair = _pair(cfg)
    pols, _ = _policies(cfg, Path(policies_from) if policies_from else None)
    d = cfg.data
    n = n_prompts or max(4, d.n_test_per_set // 4)
    prompts = [p for s in d.test for p in load_prompts(s, n, d.seed + 1, 0, _offline(cfg))]
    print(f"Real evaluation: {len(prompts)} prompts x {len(pols)} policies on {pair.device}")
    evaluate_real(pair, prompts, pols, cfg.decode.max_new_tokens, cfg.decode.dmax, d.max_prompt_tokens,
                  cfg.out / f"real_results{tag}.jsonl", seed=d.seed)


def cmd_robust(cfg: Config, n_seeds: int) -> None:
    from .robustness import run_robust
    run_robust(cfg, n_seeds)


def cmd_behaviour(cfg: Config) -> None:
    from .robustness import run_behaviour
    pols, _ = _policies(cfg)
    print(f"-> {run_behaviour(cfg, pols)}")


def cmd_synthetic_demo(out_dir: str, train_steps: int) -> None:
    """End-to-end pipeline with synthetic traces and an illustrative timing model.
    Exercises tune / (train) / eval-sim / report without any model download.
    The numbers are NOT results - they only show the machinery works."""
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    dmax, vocab = 12, 32_000
    tm = TimingModel.synthetic(); tm.save(out / "timing.json")
    for split, n, seed in (("train", 60, 0), ("val", 16, 1), ("test", 24, 2)):
        save_traces(synthetic_traces(n, 96, dmax, seed, vocab), out / f"traces_{split}.npz", vocab)
    cfg = Config(name="synthetic-demo", out_dir=str(out))
    cfg.train.total_timesteps = train_steps
    cfg.train.eval_every = max(train_steps // 5, 2048)
    save_json(environment() | {"note": "SYNTHETIC DEMO - not a result"}, out / "environment.json")
    cmd_tune(cfg)
    if train_steps > 0:
        try:
            cmd_train(cfg, "throughput")
        except ImportError as e:
            print(f"  (skipping PPO training: {e}; install the [train] extra)")
    cmd_eval_sim(cfg)
    print(f"-> {build_report(out)}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="ltdmini", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("profile", "traces", "tune", "train", "eval-sim", "eval-real", "report", "all", "robust", "behaviour"):
        p = sub.add_parser(name)
        p.add_argument("--config", required=True)
        if name in ("train", "all"):
            p.add_argument("--reward", default="all", choices=REWARDS + ("all",))
        if name in ("eval-real", "all"):
            p.add_argument("--n-prompts", type=int, default=None, help="prompts per test set for wall-clock eval")
        if name == "eval-real":
            p.add_argument("--tag", default="", help="suffix for the output file, e.g. _run2 -> real_results_run2.jsonl")
            p.add_argument("--policies-from", default=None, help="load policies/baselines from another results folder")
        if name == "robust":
            p.add_argument("--seeds", type=int, default=3)
    s = sub.add_parser("synthetic-demo")
    s.add_argument("--out", default="results/synthetic-demo")
    s.add_argument("--train-steps", type=int, default=20_000)
    a = ap.parse_args(argv)

    if a.cmd == "synthetic-demo":
        return cmd_synthetic_demo(a.out, a.train_steps)
    cfg = load_config(a.config)
    (cfg.out / "config_used.json").write_text(json.dumps(cfg.to_dict(), indent=2))
    steps = {
        "profile": lambda: cmd_profile(cfg),
        "traces": lambda: cmd_traces(cfg),
        "tune": lambda: cmd_tune(cfg),
        "train": lambda: cmd_train(cfg, a.reward),
        "eval-sim": lambda: cmd_eval_sim(cfg),
        "eval-real": lambda: cmd_eval_real(cfg, a.n_prompts, getattr(a, "tag", ""), getattr(a, "policies_from", None)),
        "robust": lambda: cmd_robust(cfg, getattr(a, "seeds", 3)),
        "behaviour": lambda: cmd_behaviour(cfg),
        "report": lambda: print(f"-> {build_report(cfg.out)}"),
    }
    if a.cmd == "all":
        for k in ("profile", "traces", "tune", "train", "eval-sim", "eval-real", "report"):
            print(f"\n=== {k} ===")
            steps[k]()
    else:
        steps[a.cmd]()


if __name__ == "__main__":
    sys.exit(main())
