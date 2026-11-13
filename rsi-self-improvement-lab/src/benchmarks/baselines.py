"""Non-RSI baselines on the shared protocol (no adaptation phase unless budget-matched)."""

from __future__ import annotations

import time

import numpy as np

from src.agents.proposer import ImproverConfig, MutationProposer
from src.agents.tree_search import (
    AIDE_POLICY,
    INITIAL_POLICY,
    hill_climb,
    random_search,
    run_tree_search,
    seed_program,
)
from src.core.config import ExperimentConfig
from src.core.evaluator import Budget, Evaluator
from src.core.history import DiscoveryTree
from src.core.results import DeployRun, MethodRun


def _run(cfg: ExperimentConfig, seed: int, name: str, extra_evals: float, search) -> MethodRun:
    """Run ``search(evaluator, rng) -> tree`` on every held-out task with the given budget."""
    rng = np.random.default_rng([seed, 404])
    deployments = []
    for task in cfg.held_out_specs():
        t0 = time.time()
        ev = Evaluator(task, Budget((cfg.deploy_evals + extra_evals) * cfg.n_train))
        tree: DiscoveryTree = search(ev, rng)
        deployments.append(DeployRun(task.name, tree, ev.budget.used, time.time() - t0))
    return MethodRun(name, seed, 0.0, deployments, {"extra_evals": extra_evals})


def matched_extra(cfg: ExperimentConfig) -> float:
    """Evaluations a baseline gets per held-out task to match the RSI methods' *whole* adaptation allowance."""
    return cfg.adapt_evals * len(cfg.train_tasks) / len(cfg.held_out_tasks)


def run_baseline(name: str, cfg: ExperimentConfig, seed: int) -> MethodRun:
    prop, seed_expr, imp = MutationProposer(), seed_program(), ImproverConfig()
    extra = matched_extra(cfg) if name.endswith("_matched") else 0.0
    base = name.removesuffix("_matched")
    if base == "initial":
        return _run_initial(cfg, seed)
    searches = {
        "random_search": lambda ev, rng: random_search(ev, seed_expr, rng),
        "hill_climb": lambda ev, rng: hill_climb(ev, prop, seed_expr, rng, imp),
        "aide_style": lambda ev, rng: run_tree_search(ev, prop, seed_expr, AIDE_POLICY, rng, imp),
        "fixed_tree": lambda ev, rng: run_tree_search(ev, prop, seed_expr, INITIAL_POLICY, rng, imp),
    }
    if base not in searches:
        raise KeyError(f"unknown baseline {name!r}")
    return _run(cfg, seed, name, extra, searches[base])


def _run_initial(cfg: ExperimentConfig, seed: int) -> MethodRun:
    """The initial solution, evaluated once (the 'do nothing' baseline)."""
    deployments = []
    for task in cfg.held_out_specs():
        ev = Evaluator(task, Budget(cfg.n_train))
        tree = DiscoveryTree(task.name, seed_program())
        res = ev.evaluate(tree.root.expr)
        tree.root.score, tree.root.solved, tree.root.n_instances, tree.root.cost = res.score, res.solved, res.n, ev.budget.used
        deployments.append(DeployRun(task.name, tree, ev.budget.used))
    return MethodRun("initial", seed, 0.0, deployments)
