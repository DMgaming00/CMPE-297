import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

"""Codelab 06 - Budget RSI: score edits with a frozen linear readout before spending evaluations."""

import numpy as np

from src.core.config import ExperimentConfig
from src.methods.budget_rsi.budget_rsi import collect_labelled_edits, run_budget_rsi
from src.methods.budget_rsi.readout import FEATURE_NAMES, fit_readout, spearman


def main() -> None:
    cfg = ExperimentConfig()
    lab = collect_labelled_edits(cfg, np.random.default_rng(0))
    print(
        f"labelled {len(lab.y)} edits on a {cfg.budget_fit_instances}-instance fit split: cost {lab.units:.0f} units "
        f"(= {lab.units / cfg.n_train:.0f} full evaluations); {np.mean(lab.y > 0):.0%} of edits improved their parent"
    )
    split = int(0.8 * len(lab.y))
    ro = fit_readout(lab.X[:split], lab.y[:split])
    rho = spearman(lab.X[split:] @ ro.weights, lab.y[split:])
    print(f"readout fitted on 80%, Spearman rank-correlation with held-out labels: {rho:+.2f}")
    final = fit_readout(lab.X, lab.y)
    print("\nfrozen readout weights (predicts expected improvement of an edit):")
    for name, w in zip(FEATURE_NAMES, final.weights):
        print(f"  {name:<14}{w:+.3f}")
    print("\ndeployment (same 60-evaluation budget on each held-out task), mean of 5 seeds:")
    for variant in ("full", "parent_only", "no_screen"):
        s = [np.mean([d.tree.best().score for d in run_budget_rsi(cfg, seed, variant).deployments]) for seed in range(5)]
        print(f"  {variant:<12} best train score {np.mean(s):.2f}")


if __name__ == "__main__":
    main()
