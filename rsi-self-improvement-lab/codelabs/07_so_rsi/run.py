import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

"""Codelab 07 - SO-RSI: diagnose why failures recur before changing the improver."""

import numpy as np

from src.core.config import ExperimentConfig
from src.methods.so_rsi.so_rsi import run_so_rsi


def main() -> None:
    cfg = ExperimentConfig()
    run = run_so_rsi(cfg, seed=0, variant="so_rsi")
    print("episode  task      best     anomalies -> diagnosis -> intervention")
    for ep in run.log["episodes"]:
        applied = "; ".join(f"{a['anomaly']}/{a['subject']} -> {a['verdict']} -> {a['action']}" for a in ep["applied"]) or "-"
        print(f"{ep['episode']:>7}  {ep['task']:<8} {ep['best']:>7.2f}   {applied}")
    print("\ninquiry memory entries:", len(run.log["memory"]), "| validation required at deployment:", run.log["validate"])
    print("final edit weights:", {k: round(v, 2) for k, v in run.log["final_weights"].items()})
    print("\ndeployment, mean of 5 seeds (60 evaluations per held-out task):")
    for variant in ("naive_rsi", "so_rsi"):
        s = [np.mean([d.tree.best().score for d in run_so_rsi(cfg, seed, variant).deployments]) for seed in range(5)]
        print(f"  {variant:<10} best train score {np.mean(s):.2f}")


if __name__ == "__main__":
    main()
