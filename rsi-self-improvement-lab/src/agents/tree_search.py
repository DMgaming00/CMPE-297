"""Parameterised tree search: the *search policy* that Dream-RSI improves.

One engine, three uses: (1) the fixed-policy baselines (AIDE-style and the
default tree search), (2) Dream-RSI's online rollouts and deployment, and
(3) the replay simulator, which re-uses :func:`select_batch` verbatim so that a
policy behaves identically online and in replay.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace

import numpy as np

from src.agents.proposer import ImproverConfig, Proposer, random_expr
from src.core.candidate import Candidate, Expr
from src.core.evaluator import Evaluator
from src.core.history import DiscoveryTree
from src.core.problem import NEAREST_NEIGHBOR


@dataclass(frozen=True)
class SearchPolicy:
    """Exploration policy: which nodes to expand, how many in parallel, when to stop.

    temperature   softmax temperature over parent ranks (0 = greedy on score)
    explore_c     bonus for nodes with few children (UCB-like)
    restart_prob  probability of expanding the root instead (new branch)
    batch         nodes expanded per round ("parallel workers")
    max_children  cap on children per node
    patience      rounds without improvement tolerated at preference rho=0.5
    """

    temperature: float = 1.0
    explore_c: float = 0.0
    restart_prob: float = 0.0
    batch: int = 1
    max_children: int = 50
    patience: float = 1000.0

    def effective_patience(self, rho: float) -> int:
        """rho in [0,1] trades cost for quality: 0 = stop early, 1 = be thorough."""
        return max(1, round(self.patience * (0.25 + 1.5 * rho)))

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    def clamp(self) -> SearchPolicy:
        return replace(
            self,
            temperature=min(max(self.temperature, 0.0), 5.0),
            explore_c=min(max(self.explore_c, 0.0), 2.0),
            restart_prob=min(max(self.restart_prob, 0.0), 0.5),
            batch=int(min(max(self.batch, 1), 8)),
            max_children=int(min(max(self.max_children, 1), 200)),
            patience=min(max(self.patience, 1.0), 1000.0),
        )


# A deliberately naive default: nearly-uniform parent choice, no stopping.
INITIAL_POLICY = SearchPolicy(temperature=2.0, explore_c=0.0, restart_prob=0.1, batch=1, patience=1000.0)
# AIDE-style: greedy "improve the current best", with occasional fresh drafts.
AIDE_POLICY = SearchPolicy(temperature=0.0, explore_c=0.0, restart_prob=0.05, batch=1, patience=1000.0)


def select_batch(eligible: Sequence[Candidate], root_id: int, policy: SearchPolicy, rng: np.random.Generator) -> list[int]:
    """Pick up to ``policy.batch`` node ids to expand this round (with replacement)."""
    if not eligible:
        return []
    ids = [n.id for n in eligible]
    scores = np.array([n.score if n.score is not None else -1e9 for n in eligible], dtype=float)
    ranks = scores.argsort().argsort() / max(len(eligible) - 1, 1)  # 0 worst .. 1 best
    bonus = np.array([policy.explore_c / math.sqrt(1 + len(n.children)) for n in eligible])
    util = ranks + bonus
    if policy.temperature <= 1e-9:
        probs = np.zeros(len(eligible))
        probs[int(np.argmax(util))] = 1.0
    else:
        z = (util - util.max()) / (0.15 * policy.temperature)
        probs = np.exp(z)
        probs /= probs.sum()
    chosen: list[int] = []
    for _ in range(policy.batch):
        if root_id in ids and rng.random() < policy.restart_prob:
            chosen.append(root_id)
        else:
            chosen.append(int(rng.choice(ids, p=probs)))
    return chosen


def run_tree_search(
    evaluator: Evaluator,
    proposer: Proposer,
    seed_expr: Expr,
    policy: SearchPolicy,
    rng: np.random.Generator,
    improver: ImproverConfig | None = None,
    rho: float = 1.0,
    max_evals: int | None = None,
) -> DiscoveryTree:
    """Expand a discovery tree until the budget, ``max_evals`` or the stopping rule ends it."""
    improver = improver or ImproverConfig()
    tree = DiscoveryTree(evaluator.task.name, seed_expr)
    _score(tree.root, evaluator)
    best, stale, round_, evals = tree.root.score, 0, 0, 1
    patience = policy.effective_patience(rho)
    while evaluator.can_afford_full() and (max_evals is None or evals < max_evals):
        eligible = [n for n in tree.evaluated() if len(n.children) < policy.max_children]
        parents = select_batch(eligible, 0, policy, rng)
        round_ += 1
        improved = False
        for pid in parents:
            if not evaluator.can_afford_full() or (max_evals is not None and evals >= max_evals):
                break
            child_expr, edit = proposer.propose(tree.nodes[pid].expr, rng, improver)
            node = tree.add_child(pid, child_expr, edit, round_)
            _score(node, evaluator)
            evals += 1
            if node.score > best + 1e-12:  # type: ignore[operator]
                best, improved = node.score, True
        stale = 0 if improved else stale + 1
        if stale >= patience:
            break
    return tree


def _score(node: Candidate, evaluator: Evaluator) -> None:
    result = evaluator.evaluate(node.expr)
    node.score, node.solved, node.n_instances = result.score, result.solved, result.n
    node.cost = evaluator.budget.used


def random_search(evaluator: Evaluator, seed_expr: Expr, rng: np.random.Generator, depth: int = 3) -> DiscoveryTree:
    """Baseline: independent random programs (no use of history)."""
    tree = DiscoveryTree(evaluator.task.name, seed_expr)
    _score(tree.root, evaluator)
    while evaluator.can_afford_full():
        node = tree.add_child(0, random_expr(rng, depth), None, 0)
        _score(node, evaluator)
    return tree


def hill_climb(
    evaluator: Evaluator,
    proposer: Proposer,
    seed_expr: Expr,
    rng: np.random.Generator,
    improver: ImproverConfig,
    max_evals: int | None = None,
    margin: float = 0.0,
) -> DiscoveryTree:
    """Baseline / SO-RSI inner loop: (1+1) hill-climbing on the incumbent."""
    tree = DiscoveryTree(evaluator.task.name, seed_expr)
    _score(tree.root, evaluator)
    incumbent, evals = tree.root, 1
    while evaluator.can_afford_full() and (max_evals is None or evals < max_evals):
        child_expr, edit = proposer.propose(incumbent.expr, rng, improver)
        node = tree.add_child(incumbent.id, child_expr, edit, evals)
        _score(node, evaluator)
        evals += 1
        if node.score > incumbent.score + margin:  # type: ignore[operator]
            incumbent = node
    return tree


def seed_program() -> Expr:
    """The common initial solution: Nearest-Neighbour expressed in the DSL."""
    return NEAREST_NEIGHBOR


__all__ = [
    "AIDE_POLICY",
    "INITIAL_POLICY",
    "SearchPolicy",
    "hill_climb",
    "random_search",
    "run_tree_search",
    "seed_program",
    "select_batch",
]
