import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

"""Codelab 04 - memory: persist the discovery tree and replay it for free."""

import tempfile
from pathlib import Path

import numpy as np

from src.agents.proposer import ImproverConfig, MutationProposer
from src.agents.tree_search import INITIAL_POLICY, SearchPolicy, run_tree_search, seed_program
from src.core.config import ExperimentConfig
from src.core.evaluator import Budget, Evaluator
from src.core.history import DiscoveryTree
from src.methods.dream_rsi.replay import replay


def main() -> None:
    task = ExperimentConfig().train_specs()[1]
    ev = Evaluator(task, Budget(60 * 12))
    tree = run_tree_search(ev, MutationProposer(), seed_program(), INITIAL_POLICY, np.random.default_rng(0), ImproverConfig())
    print(
        f"online run on '{task.name}': {len(tree.nodes) - 1} evaluator calls, best {tree.best().score:.2f}, {ev.budget.used:.0f} units"
    )

    path = Path(tempfile.mkdtemp()) / "tree.json"
    tree.save(path)
    loaded = DiscoveryTree.load(path)
    print(f"saved + reloaded: {len(loaded.nodes)} nodes, best lineage {loaded.lineage(loaded.best().id)}")

    print("\nreplay = re-run a *different* policy against the recorded outcomes, with ZERO new evaluations")
    for name, pol in {
        "naive (temp 2.0)": INITIAL_POLICY,
        "greedy (temp 0)": SearchPolicy(temperature=0.0),
        "greedy + stops after 3 stale rounds": SearchPolicy(temperature=0.0, patience=3.0),
    }.items():
        res = replay(loaded, pol, rho=1.0, rng=np.random.default_rng(0))
        print(f"  {name:<38} reveals {res.calls:>3} recorded calls -> best {res.best_score:.2f}")
    print("\nLimit: a replayed policy can only reach outcomes that were recorded (it never sees unexplored children).")


if __name__ == "__main__":
    main()
