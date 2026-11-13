import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

"""Codelab 02 - the candidate DSL, the proposer, and random search."""

import numpy as np

from src.agents.proposer import ImproverConfig, MutationProposer, random_expr
from src.agents.tree_search import random_search, seed_program
from src.core import candidate as cand
from src.core.config import ExperimentConfig
from src.core.evaluator import Budget, Evaluator


def main() -> None:
    task = ExperimentConfig().train_specs()[0]
    rng = np.random.default_rng(0)
    seed = seed_program()
    print("seed program (Nearest-Neighbour):", cand.to_str(seed))

    print("\nfive edits proposed from the seed (offline MutationProposer, seed 0):")
    prop, cfg = MutationProposer(), ImproverConfig()
    for _ in range(5):
        child, edit = prop.propose(seed, rng, cfg)
        feats = {k: v for k, v in edit.features.items() if v}
        print(f"  {edit.kind:<16} {cand.to_str(child):<48} diff features {feats}")

    print("\nthe DSL is closed: an out-of-grammar program is rejected, not executed")
    try:
        cand.parse("__import__('os').system('echo hi')")
    except ValueError as exc:
        print("  rejected:", exc)

    ev = Evaluator(task, Budget(60 * 12))
    tree = random_search(ev, seed, np.random.default_rng(0))
    print(f"\nrandom search, 60 evaluations: best train score {tree.best().score:.2f} (seed program {tree.root.score:.2f})")
    print("a random program of depth 3 looks like:", cand.to_str(random_expr(np.random.default_rng(3))))


if __name__ == "__main__":
    main()
