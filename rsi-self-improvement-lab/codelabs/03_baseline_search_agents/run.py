import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

"""Codelab 03 - fixed (non-RSI) search agents and their trajectories."""

import numpy as np

from src.agents.proposer import ImproverConfig, MutationProposer
from src.agents.tree_search import AIDE_POLICY, INITIAL_POLICY, hill_climb, run_tree_search, seed_program
from src.core.config import ExperimentConfig
from src.core.evaluator import Budget, Evaluator, score_expr


def main() -> None:
    task = ExperimentConfig().train_specs()[0]
    agents = {
        "hill-climb (1+1)": lambda ev, r: hill_climb(ev, MutationProposer(), seed_program(), r, ImproverConfig()),
        "tree search, naive policy": lambda ev, r: run_tree_search(ev, MutationProposer(), seed_program(), INITIAL_POLICY, r),
        "AIDE-style (greedy best-first)": lambda ev, r: run_tree_search(ev, MutationProposer(), seed_program(), AIDE_POLICY, r),
    }
    print(f"{'agent':<32}{'best train':>11}{'test':>8}{'nodes':>7}{'improving edits':>17}")
    for name, fn in agents.items():
        tr, te = [], []
        nodes = imp = 0
        for seed in range(5):
            ev = Evaluator(task, Budget(60 * 12))
            tree = fn(ev, np.random.default_rng(seed))
            best = tree.best()
            tr.append(best.score)
            te.append(score_expr(task, best.expr, "test").score)
            nodes += len(tree.nodes)
            imp += sum(1 for n in tree.nodes[1:] if n.score > tree.nodes[n.parent].score)
        print(f"{name:<32}{np.mean(tr):>11.2f}{np.mean(te):>8.2f}{nodes // 5:>7}{imp // 5:>17}")
    print(
        "\n(mean of 5 seeds, 60 evaluations each; the seed program scores",
        f"{score_expr(task, seed_program(), 'train').score:.2f} on train)",
    )
    print("Every attempt is stored in a DiscoveryTree - that trajectory is the raw material for codelabs 04-07.")


if __name__ == "__main__":
    main()
