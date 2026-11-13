import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

"""Codelab 08 - one protocol, every method: a controlled comparison (reads claim vs evidence)."""

from src.benchmarks import protocol as P
from src.core.config import ExperimentConfig
from src.utils.table import summary_table


def main() -> None:
    cfg = ExperimentConfig.load("smoke")
    print(
        f"config '{cfg.name}': seeds {cfg.seeds}, {cfg.adapt_evals} adaptation evals/train task, {cfg.deploy_evals} deploy evals/held-out task"
    )
    print(f"train tasks {[t['name'] for t in cfg.train_tasks]}  held-out {[t['name'] for t in cfg.held_out_tasks]}\n")
    rows = P.run_experiment(cfg, P.MAIN_METHODS, out_dir=P.RESULTS_DIR / "smoke", quiet=True)
    print(summary_table(P.summarize(rows)))
    print("\npaired difference vs fixed tree search (same seed & task):")
    for m in P.RSI_METHODS:
        d = P.paired_vs(rows, m, "fixed_tree")
        print(f"  {m:<11}{d['mean_diff']:+.2f}  95% CI [{d['ci_lo']:+.2f}, {d['ci_hi']:+.2f}]")
    print(
        "\nFairness checks: equal deployment budget, identical seeds/tasks/initial program; RSI adaptation cost is reported separately,"
    )
    print("and *_matched baselines receive that adaptation budget as extra deployment evaluations.")


if __name__ == "__main__":
    main()
