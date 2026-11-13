"""SO-RSI and the first-order "naive RSI" it is compared against (arXiv:2610.05701, minimal reproduction).

Both loops run episodes of hill-climbing under an :class:`ImproverConfig` and then revise the
improver from the episode trace (this revision is the recursive step).

* Naive RSI (first order): reacts to symptoms - shifts edit weights toward whatever last succeeded.
* SO-RSI (second order): detects structural anomalies in the trace, runs cheap *diagnostic probes*
  to find out WHY, writes the causal finding to inquiry memory and applies a targeted structural
  intervention (demote a dead edit kind, shrink steps, require validation).

What improves: the improver's edit procedure (its mutation distribution, step size, acceptance rule).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from src.agents.proposer import (
    DEFAULT_WEIGHTS,
    EDIT_KINDS,
    ImproverConfig,
    MutationProposer,
)
from src.agents.tree_search import _score, seed_program
from src.core.candidate import Const, Expr, Op
from src.core.config import ExperimentConfig
from src.core.evaluator import Budget, Evaluator
from src.core.history import DiscoveryTree
from src.core.results import DeployRun, MethodRun
from src.methods.so_rsi.anomalies import (
    Anomaly,
    accepted_nodes,
    detect_mismatch,
    detect_opposing,
    detect_recurrence,
)
from src.methods.so_rsi.memory import InquiryMemory, InquiryRecord


@dataclass
class ImproverState:
    config: ImproverConfig = field(default_factory=ImproverConfig)
    validate: bool = False  # require validation-split agreement before accepting an edit


def climb(ev: Evaluator, state: ImproverState, rng: np.random.Generator, max_evals: int | None, n_val: int) -> DiscoveryTree:
    """(1+1) hill-climb; with ``state.validate`` an edit must also not hurt on fresh instances."""
    proposer = MutationProposer()
    tree = DiscoveryTree(ev.task.name, seed_program())
    _score(tree.root, ev)
    inc, evals = tree.root, 1
    inc_val: float | None = None
    while ev.can_afford_full() and (max_evals is None or evals < max_evals):
        expr, edit = proposer.propose(inc.expr, rng, state.config)
        node = tree.add_child(inc.id, expr, edit, evals)
        _score(node, ev)
        evals += 1
        if node.score <= inc.score:  # type: ignore[operator]
            continue
        if state.validate:
            if not ev.budget.can_afford(2 * n_val):
                break
            if inc_val is None:
                inc_val = ev.evaluate_split(inc.expr, "probe", n_val).score
            val = ev.evaluate_split(node.expr, "probe", n_val).score
            if val < inc_val:
                continue
            inc_val = val
        inc = node
    return tree


# ---- diagnostic probes ---------------------------------------------------------------------


def _scaled_consts(expr: Expr, factor: float) -> Expr:
    if isinstance(expr, Const):
        return Const(expr.value * factor)
    if isinstance(expr, Op):
        return Op(expr.op, _scaled_consts(expr.left, factor), _scaled_consts(expr.right, factor))
    return expr


def probe_kind(
    ev: Evaluator, kind: str, parent: Expr, rng: np.random.Generator, cfg: ImproverConfig, n: int
) -> tuple[str, float]:
    """Diagnose WHY edits of ``kind`` never help. Returns (verdict, cost)."""
    before = ev.budget.used
    base = ev.evaluate_split(parent, "probe", n).score
    if kind == "perturb_const":
        spread = [abs(ev.evaluate_split(_scaled_consts(parent, f), "probe", n).score - base) for f in (0.8, 1.25)]
        verdict = "insensitive_constants" if max(spread) < 0.3 else "step_too_large"
    else:
        proposer, probe_cfg = MutationProposer(), cfg.copy()
        probe_cfg.edit_weights = {k: (1.0 if k == kind else 0.0) for k in EDIT_KINDS}
        deltas = []
        for _ in range(3):
            child, _ = proposer.propose(parent, rng, probe_cfg)
            deltas.append(ev.evaluate_split(child, "probe", n).score - base)
        verdict = "neutral_edits" if max(abs(d) for d in deltas) < 0.3 else "destructive_edits"
    return verdict, ev.budget.used - before


def probe_noise(ev: Evaluator, tree: DiscoveryTree, node_ids: tuple[int, int], n: int) -> tuple[str, float]:
    """Do the 'opposing' edits make a real difference on fresh instances or only on the train set?"""
    before = ev.budget.used
    a = tree.nodes[node_ids[0]]
    parent = tree.nodes[a.parent]  # type: ignore[index]
    gain = ev.evaluate_split(a.expr, "probe", n).score - ev.evaluate_split(parent.expr, "probe", n).score
    return ("instance_noise" if gain <= 0.0 else "real_effect"), ev.budget.used - before


# ---- improver revision -----------------------------------------------------------------------


def revise_naive(state: ImproverState, tree: DiscoveryTree) -> None:
    """First-order revision: chase the most recent success rates (reactive, no diagnosis)."""
    acc = set(accepted_nodes(tree))
    for kind in EDIT_KINDS:
        ids = [n.id for n in tree.nodes[1:] if n.edit and n.edit.kind == kind]
        if len(ids) >= 3:
            rate = len(set(ids) & acc) / len(ids)
            state.config.edit_weights[kind] = 0.5 * state.config.edit_weights[kind] + 0.5 * (0.2 + 8.0 * rate)
    gain = tree.best().score - tree.root.score  # type: ignore[operator]
    state.config.step_sigma = float(np.clip(state.config.step_sigma * (1.3 if gain < 1.0 else 0.9), 0.05, 1.5))


def apply_intervention(state: ImproverState, anomaly: Anomaly, verdict: str) -> str:
    cfg = state.config
    if verdict in ("insensitive_constants", "neutral_edits"):
        cfg.edit_weights[anomaly.subject] *= 0.2
        for kind in ("add_term", "replace_subtree"):
            cfg.edit_weights[kind] *= 1.5
        return f"demote '{anomaly.subject}' x0.2, promote add_term/replace_subtree x1.5"
    if verdict == "step_too_large":
        cfg.step_sigma = max(0.05, cfg.step_sigma * 0.5)
        return "halve step_sigma"
    if verdict == "destructive_edits":
        cfg.edit_weights[anomaly.subject] *= 0.3
        return f"demote '{anomaly.subject}' x0.3"
    if verdict == "instance_noise" or anomaly.kind == "expectation_mismatch":
        state.validate = True
        return "require validation-split agreement before accepting edits"
    return "no change"


def run_so_rsi(cfg: ExperimentConfig, seed: int, variant: str = "so_rsi") -> MethodRun:
    """variant: 'so_rsi' | 'naive_rsi' | 'so_no_probes' | 'so_no_memory'."""
    rng = np.random.default_rng([seed, 303])
    state, memory = ImproverState(), InquiryMemory()
    adapt_units, episodes, episode = 0.0, [], 0
    use_so = variant != "naive_rsi"
    for task in cfg.train_specs():
        budget = Budget(cfg.adapt_evals * cfg.n_train)
        while budget.can_afford(cfg.so_episode_evals * cfg.n_train):
            ev = Evaluator(task, budget)
            if variant == "so_no_memory":
                state = ImproverState()  # forget every earlier revision
            tree = climb(ev, state, rng, cfg.so_episode_evals, cfg.so_validation_instances)
            found: list[Anomaly] = []
            if use_so and budget.can_afford(3 * cfg.so_probe_instances * 4 + 2 * cfg.so_validation_instances):
                found += detect_recurrence(tree) + detect_opposing(tree)
                if (best := tree.best()).id != 0:
                    val_gain = (
                        ev.evaluate_split(best.expr, "probe", cfg.so_validation_instances).score
                        - ev.evaluate_split(tree.root.expr, "probe", cfg.so_validation_instances).score
                    )
                    if mm := detect_mismatch(best.score - tree.root.score, val_gain):  # type: ignore[operator]
                        found.append(mm)
            applied = []
            for an in found:
                prior = memory.lookup(an.kind, an.subject)
                if prior is not None and variant != "so_no_memory":
                    verdict, cost = prior.verdict, 0.0  # reuse earlier causal evidence: no probe needed
                elif variant == "so_no_probes":
                    verdict, cost = "unprobed", 0.0
                elif an.kind == "recurrence":
                    verdict, cost = probe_kind(ev, an.subject, tree.best().expr, rng, state.config, cfg.so_probe_instances)
                elif an.kind == "opposing_edits":
                    verdict, cost = probe_noise(ev, tree, (an.node_ids[0], an.node_ids[1]), 2 * cfg.so_probe_instances)
                else:
                    verdict, cost = "overfit_to_train", 0.0
                if variant == "so_no_probes":  # default reflex without a diagnosis: demote / validate
                    verdict = "neutral_edits" if an.kind == "recurrence" else "instance_noise"
                action = apply_intervention(state, an, verdict)
                memory.add(InquiryRecord(episode, an.kind, an.subject, an.evidence, verdict, action, cost))
                applied.append({"anomaly": an.kind, "subject": an.subject, "verdict": verdict, "action": action})
            if not use_so:
                revise_naive(state, tree)
            episodes.append(
                {
                    "episode": episode,
                    "task": task.name,
                    "best": tree.best().score,
                    "root": tree.root.score,
                    "anomalies": [a.kind for a in found],
                    "applied": applied,
                    "weights": dict(state.config.edit_weights),
                    "step_sigma": state.config.step_sigma,
                }
            )
            episode += 1
        adapt_units += budget.used
    deployments = []
    for task in cfg.held_out_specs():
        t0 = time.time()
        ev = Evaluator(task, Budget(cfg.deploy_evals * cfg.n_train))
        tree = climb(ev, state, rng, None, cfg.so_validation_instances)
        deployments.append(DeployRun(task.name, tree, ev.budget.used, time.time() - t0))
    return MethodRun(
        variant if variant != "so_rsi" else "so_rsi",
        seed,
        adapt_units,
        deployments,
        {
            "episodes": episodes,
            "memory": memory.to_list(),
            "validate": state.validate,
            "final_weights": dict(state.config.edit_weights),
            "final_step_sigma": state.config.step_sigma,
        },
    )


__all__ = ["DEFAULT_WEIGHTS", "Callable", "ImproverState", "climb", "run_so_rsi"]
