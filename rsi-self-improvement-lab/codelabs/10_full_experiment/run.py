import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

"""Codelab 10 - the full experiment: bounded generations, figures, and an honest claim.

Usage:  python codelabs/10_full_experiment/run.py          # analyse saved results
        python codelabs/10_full_experiment/run.py --rerun  # re-run the whole default experiment
"""

import sys

from src.benchmarks import protocol as P
from src.core.config import ExperimentConfig
from src.visualization.plots import make_all_figures


def main() -> None:
    if "--rerun" in sys.argv:
        P.run_experiment(ExperimentConfig.load("default"), P.MAIN_METHODS + P.ABLATIONS)
    rows = P.load_rows("default")
    cfg = ExperimentConfig.load("default")
    print(
        f"Bounded recursion: {len(cfg.train_tasks)} adaptation generations (one per training task), "
        f"hard cap {cfg.adapt_evals} evals each; no method may run more."
    )
    for m in ["dream_rsi", "budget_rsi", "so_rsi"]:
        d = P.paired_vs(rows, m, "fixed_tree")
        sm = {s["method"]: s for s in P.summarize(rows)}[m]
        verdict = "supported" if d["ci_lo"] > 0 else "NOT supported (CI includes 0)"
        print(
            f"\n{m}: final {sm['final']:.2f} vs fixed tree: {d['mean_diff']:+.2f} [{d['ci_lo']:+.2f},{d['ci_hi']:+.2f}] over {d['n']} paired runs "
            f"-> 'better than fixed search at equal deployment budget' {verdict}"
        )
    print("\nfigures:", *make_all_figures("default"), sep="\n  ")


if __name__ == "__main__":
    main()
