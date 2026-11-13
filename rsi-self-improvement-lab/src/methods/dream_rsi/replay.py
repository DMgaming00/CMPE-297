"""Replay worlds: re-run a *policy* against a recorded discovery tree, with zero new evaluations.

A recorded tree fixes the outcome of every attempt that was actually made. A candidate
policy then decides, round by round, which *revealed* node to expand next; expanding
reveals the next recorded child of that node. Nothing is generated or evaluated, so
many policies can be compared on real discovery history for free.

Limitation (inherent to the idea): a policy can only reach outcomes that were recorded.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.agents.tree_search import SearchPolicy, select_batch
from src.core.candidate import Candidate
from src.core.history import DiscoveryTree
from src.core.metrics import frontier_hypervolume


@dataclass
class ReplayResult:
    calls: int  # recorded children revealed (== evaluator calls the policy would have used)
    rounds: int
    best_score: float


def replay(tree: DiscoveryTree, policy: SearchPolicy, rho: float, rng: np.random.Generator) -> ReplayResult:
    """Replay ``policy`` (at budget preference ``rho``) on ``tree``."""
    view = {n.id: Candidate(id=n.id, parent=n.parent, expr=n.expr, score=n.score) for n in tree.nodes}
    next_child = {n.id: 0 for n in tree.nodes}  # how many recorded children are revealed
    revealed = [0]
    best = tree.root.score
    assert best is not None
    stale, rounds, calls = 0, 0, 0
    patience = policy.effective_patience(rho)
    while True:
        eligible = [
            view[i]
            for i in revealed
            if next_child[i] < len(tree.nodes[i].children) and len(view[i].children) < policy.max_children
        ]
        if not eligible:
            break
        rounds += 1
        improved = False
        for pid in select_batch(eligible, 0, policy, rng):
            k = next_child[pid]
            if k >= len(tree.nodes[pid].children):
                continue  # already exhausted by an earlier pick in this batch
            cid = tree.nodes[pid].children[k]
            next_child[pid] += 1
            view[pid].children.append(cid)
            revealed.append(cid)
            calls += 1
            score = tree.nodes[cid].score
            assert score is not None
            if score > best + 1e-12:
                best, improved = score, True
        stale = 0 if improved else stale + 1
        if stale >= patience:
            break
    return ReplayResult(calls, rounds, best)


def policy_replay_score(
    policy: SearchPolicy,
    trees: list[DiscoveryTree],
    rhos: list[float],
    lam: float,
    seed: int,
    repeats: int = 4,
) -> float:
    """Mean over replay worlds of (frontier hypervolume - lam * rounds-per-call).

    For each world, the policy is replayed at every budget preference ``rho``; each run
    gives a point (calls / total recorded calls, normalised quality gain). The hypervolume
    of those points rewards reaching high quality with few calls. The ``lam`` term is a
    parallelism penalty: sequential rounds per call (1.0 = fully sequential).
    """
    values: list[float] = []
    for t_idx, tree in enumerate(trees):
        root = tree.root.score
        top = max(n.score for n in tree.evaluated() if n.score is not None)
        total_calls = len(tree.nodes) - 1
        if root is None or top - root < 1e-9 or total_calls == 0:
            continue  # nothing was discovered in this world: no signal
        for rep in range(repeats):
            rng = np.random.default_rng([seed, t_idx, rep])
            points, rpc = [], []
            for rho in rhos:
                res = replay(tree, policy, rho, rng)
                points.append((res.calls / total_calls, (res.best_score - root) / (top - root)))
                rpc.append(res.rounds / max(res.calls, 1))
            values.append(frontier_hypervolume(points) - lam * float(np.mean(rpc)))
    return float(np.mean(values)) if values else 0.0
