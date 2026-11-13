"""Dream-RSI (educational minimal reproduction of arXiv:2609.14858).

Loop:  explore online -> record discovery tree -> add to replay-world pool ->
       "dream": replay candidate policies on every recorded world (no evaluator calls) ->
       keep the best-scoring policy -> redeploy -> repeat.

What recursively improves: the *exploration policy* (how search allocates its budget).
The proposer (our stand-in for the foundation model), the evaluator and the DSL never change.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from src.agents.proposer import ImproverConfig, MutationProposer
from src.agents.tree_search import (
    INITIAL_POLICY,
    SearchPolicy,
    run_tree_search,
    seed_program,
)
from src.core.config import ExperimentConfig
from src.core.evaluator import Budget, Evaluator
from src.core.history import DiscoveryTree
from src.core.results import DeployRun, MethodRun
from src.methods.dream_rsi.replay import policy_replay_score
from src.methods.dream_rsi.reviser import propose_revisions


@dataclass
class DreamGeneration:
    generation: int
    task: str
    online_best: float
    online_calls: int
    candidate_policies: list[dict[str, float]]
    replay_scores: list[float]
    chosen: int


def dream_step(
    policy: SearchPolicy,
    history: list[DiscoveryTree],
    cfg: ExperimentConfig,
    rng: np.random.Generator,
    use_replay: bool = True,
) -> tuple[SearchPolicy, list[SearchPolicy], list[float], int]:
    """One offline improvement phase: returns (new policy, candidates, replay scores, chosen index).

    Index 0 is always the incumbent, so with replay selection the new policy is never worse
    than the old one *on average replay score*.
    """
    candidates = [policy] + propose_revisions(policy, history, rng, cfg.dream_candidates - 1)
    scores = [policy_replay_score(c, history, cfg.dream_rhos, cfg.dream_lambda, int(rng.integers(1 << 30))) for c in candidates]
    if use_replay:
        chosen = int(np.argmax(scores))  # argmax returns the first max -> ties keep the incumbent
    else:  # ablation: accept a random revision without replay evidence
        chosen = int(rng.integers(1, len(candidates)))
    return candidates[chosen], candidates, scores, chosen


def run_dream_rsi(cfg: ExperimentConfig, seed: int, use_replay: bool = True, evolve: bool = True) -> MethodRun:
    rng = np.random.default_rng([seed, 101])
    proposer, seed_expr = MutationProposer(), seed_program()
    policy, history, gens = INITIAL_POLICY, [], []
    adapt_units = 0.0
    for g, task in enumerate(cfg.train_specs()):  # online exploration on training tasks
        ev = Evaluator(task, Budget(cfg.adapt_evals * cfg.n_train))
        tree = run_tree_search(ev, proposer, seed_expr, policy, rng, ImproverConfig(), rho=1.0)
        adapt_units += ev.budget.used
        history.append(tree)
        if not evolve:
            continue
        policy, cands, scores, chosen = dream_step(policy, history, cfg, rng, use_replay)
        gens.append(
            DreamGeneration(
                g,
                task.name,
                tree.best().score,
                len(tree.nodes) - 1,  # type: ignore[arg-type]
                [c.to_dict() for c in cands],
                scores,
                chosen,
            )
        )
    deployments = []
    for task in cfg.held_out_specs():  # deploy the improved policy
        t0 = time.time()
        ev = Evaluator(task, Budget(cfg.deploy_evals * cfg.n_train))
        tree = run_tree_search(ev, proposer, seed_expr, policy, rng, ImproverConfig(), rho=cfg.dream_deploy_rho)
        deployments.append(DeployRun(task.name, tree, ev.budget.used, time.time() - t0))
    method = "dream_rsi" if use_replay and evolve else ("dream_no_replay" if evolve else "dream_no_evolution")
    return MethodRun(
        method,
        seed,
        adapt_units,
        deployments,
        {"final_policy": policy.to_dict(), "generations": [g.__dict__ for g in gens]},
    )
