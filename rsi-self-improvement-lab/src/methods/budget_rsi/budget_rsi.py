"""Budget RSI (educational minimal reproduction of arXiv:2610.29121).

Core idea: a self-improving search must choose which proposed edit to *expand* before it
has been evaluated. A cheap linear readout over diff features, fitted once on a small
labelled-edit set and frozen, ranks proposals; only the top one is fully evaluated.
Parent selection uses Thompson sampling over "solved-instance" counts, as in the
Huxley-Godel-Machine-style selection the paper builds on.

What improves: the *edit-selection scorer* (and therefore how a fixed budget is spent).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from src.agents.proposer import ImproverConfig, MutationProposer
from src.agents.tree_search import seed_program
from src.core.candidate import Candidate
from src.core.config import ExperimentConfig
from src.core.evaluator import Budget, Evaluator, score_expr
from src.core.history import DiscoveryTree
from src.core.results import DeployRun, MethodRun
from src.methods.budget_rsi.readout import (
    LinearReadout,
    edit_vector,
    fit_readout,
    spearman,
)

LABEL_CLIP = 5.0  # score points. Label = max(gain, 0): a search keeps the best child, so what matters is
# expected improvement, not expected change (mean-change labels favour harmless no-op edits).


@dataclass
class LabelledEdits:
    X: np.ndarray
    y: np.ndarray
    units: float


def collect_labelled_edits(cfg: ExperimentConfig, rng: np.random.Generator) -> LabelledEdits:
    """Label random edits by the change in score on a small *fit split* (cheap, charged)."""
    proposer, improver, seed_expr = MutationProposer(), ImproverConfig(), seed_program()
    rows, labels, units = [], [], 0.0
    tasks = cfg.train_specs()
    n_fit = cfg.budget_fit_instances
    archives: dict[str, list[tuple[object, float]]] = {}
    for i in range(cfg.budget_label_edits):
        task = tasks[i % len(tasks)]
        arch = archives.setdefault(task.name, [(seed_expr, score_expr(task, seed_expr, "fit", n_fit).score)])
        if i < len(tasks):
            units += n_fit  # the seed's own fit-split evaluation
        parent_expr, parent_fit = arch[int(rng.integers(len(arch)))]
        child_expr, edit = proposer.propose(parent_expr, rng, improver)  # type: ignore[arg-type]
        child_fit = score_expr(task, child_expr, "fit", n_fit).score
        units += n_fit
        rows.append(edit_vector(edit, parent_fit))
        labels.append(float(np.clip(child_fit - parent_fit, 0.0, LABEL_CLIP)))  # expected *improvement*; clipped vs wild rewrites
        if child_fit > parent_fit or (child_fit > arch[0][1] - 3.0 and rng.random() < 0.3):
            arch.append((child_expr, child_fit))  # grow the archive so parents vary in quality
    return LabelledEdits(np.array(rows), np.array(labels), units)


def thompson_parent(nodes: list[Candidate], rng: np.random.Generator) -> Candidate:
    """Thompson sampling over Beta(1+solved, 1+failed) posteriors of evaluated nodes."""
    draws = [rng.beta(1 + (n.solved or 0), 1 + (n.n_instances or 0) - (n.solved or 0)) for n in nodes]
    return nodes[int(np.argmax(draws))]


def run_budget_search(
    ev: Evaluator, readout: LinearReadout | None, rng: np.random.Generator, k: int
) -> tuple[DiscoveryTree, list[tuple[float, float]]]:
    """Deployment search. Returns the tree and (predicted gain, actual gain) pairs for diagnostics."""
    proposer, improver = MutationProposer(), ImproverConfig()
    tree = DiscoveryTree(ev.task.name, seed_program())
    _evaluate(tree.root, ev)
    pairs: list[tuple[float, float]] = []
    round_ = 0
    while ev.can_afford_full():
        parent = thompson_parent(tree.evaluated(), rng)
        proposals = [proposer.propose(parent.expr, rng, improver) for _ in range(k if readout else 1)]
        if readout is not None:
            preds = [readout.predict(edit, parent.score) for _, edit in proposals]  # type: ignore[arg-type]
            best_i = int(np.argmax(preds))
        else:
            preds, best_i = [0.0], 0
        expr, edit = proposals[best_i]
        round_ += 1
        node = tree.add_child(parent.id, expr, edit, round_)
        _evaluate(node, ev)
        pairs.append((preds[best_i], node.score - parent.score))  # type: ignore[operator]
    return tree, pairs


def _evaluate(node: Candidate, ev: Evaluator) -> None:
    res = ev.evaluate(node.expr)
    node.score, node.solved, node.n_instances, node.cost = res.score, res.solved, res.n, ev.budget.used


def run_budget_rsi(cfg: ExperimentConfig, seed: int, variant: str = "full") -> MethodRun:
    """variant: 'full' | 'parent_only' (paper's ablation) | 'no_screen' (K=1, readout unused)."""
    rng = np.random.default_rng([seed, 202])
    labelled = collect_labelled_edits(cfg, rng)
    split = int(0.8 * len(labelled.y))
    use_diff = variant != "parent_only"
    X = labelled.X if use_diff else labelled.X * np.array([1, 1] + [0] * (labelled.X.shape[1] - 2))
    held = fit_readout(X[:split], labelled.y[:split], use_diff=use_diff)
    rho = spearman(np.array([float(held.weights @ x) for x in X[split:]]), labelled.y[split:])
    readout = fit_readout(X, labelled.y, use_diff=use_diff)  # frozen from here on
    readout_for_search = None if variant == "no_screen" else readout
    deployments, pairs_all = [], []
    for task in cfg.held_out_specs():
        t0 = time.time()
        ev = Evaluator(task, Budget(cfg.deploy_evals * cfg.n_train))
        tree, pairs = run_budget_search(ev, readout_for_search, rng, cfg.budget_proposals)
        pairs_all += pairs
        deployments.append(DeployRun(task.name, tree, ev.budget.used, time.time() - t0))
    name = {"full": "budget_rsi", "parent_only": "budget_parent_only", "no_screen": "budget_no_screen"}[variant]
    return MethodRun(
        name,
        seed,
        labelled.units,
        deployments,
        {
            "readout": readout.to_dict(),
            "n_labelled_edits": len(labelled.y),
            "heldout_label_spearman": rho,
            "pred_vs_actual": pairs_all,
        },
    )
