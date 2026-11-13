"""Edit proposers: the component that *writes* candidate programs.

``MutationProposer`` is a programmatic, seeded stand-in for an LLM code editor.
It is NOT a language model; it lets every experiment run offline and
deterministically. ``LLMProposer`` (in :mod:`src.agents.llm`) implements the same
interface using a real model when credentials are available.

``ImproverConfig`` is the improver's tunable surface. It is the *only* thing
SO-RSI/naive RSI are allowed to revise, which keeps self-modification bounded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from src.core import candidate as cand
from src.core.candidate import VARIABLES, Const, EditRecord, Expr, Op, Var

EDIT_KINDS: tuple[str, ...] = ("perturb_const", "swap_op", "replace_subtree", "add_term", "prune", "rewrite")
DEFAULT_WEIGHTS: dict[str, float] = {
    "perturb_const": 3.0,
    "swap_op": 2.0,
    "replace_subtree": 2.0,
    "add_term": 2.0,
    "prune": 1.0,
    "rewrite": 1.0,
}
MAX_SIZE = 25


@dataclass
class ImproverConfig:
    """Tunable surface of the improver (what the RSI loop is allowed to revise)."""

    edit_weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    step_sigma: float = 0.4
    feature_bias: dict[str, float] = field(default_factory=dict)
    frozen_paths: set[tuple[int, ...]] = field(default_factory=set)

    def copy(self) -> ImproverConfig:
        return ImproverConfig(dict(self.edit_weights), self.step_sigma, dict(self.feature_bias), set(self.frozen_paths))


class Proposer(Protocol):
    def propose(self, parent: Expr, rng: np.random.Generator, cfg: ImproverConfig) -> tuple[Expr, EditRecord]: ...


def random_expr(rng: np.random.Generator, max_depth: int = 3) -> Expr:
    """Random expression; leaves become likelier as depth runs out."""
    if max_depth <= 1 or rng.random() < 0.3:
        if rng.random() < 0.4:
            return Const(round(float(rng.normal(0, 1)), 2))
        return Var(str(rng.choice(VARIABLES)))
    op = str(rng.choice(cand.OPERATORS))
    return Op(op, random_expr(rng, max_depth - 1), random_expr(rng, max_depth - 1))


def _pick_feature(rng: np.random.Generator, bias: dict[str, float]) -> str:
    w = np.array([1.0 + bias.get(v, 0.0) for v in VARIABLES])
    return str(rng.choice(VARIABLES, p=w / w.sum()))


class MutationProposer:
    """Seeded structural/numeric mutations of an expression tree."""

    def propose(self, parent: Expr, rng: np.random.Generator, cfg: ImproverConfig) -> tuple[Expr, EditRecord]:
        weights = np.array([max(cfg.edit_weights.get(k, 0.0), 0.0) for k in EDIT_KINDS])
        if weights.sum() <= 0:
            weights = np.ones(len(EDIT_KINDS))
        for _ in range(20):  # retry until the edit actually changes the program
            kind = str(rng.choice(EDIT_KINDS, p=weights / weights.sum()))
            child, path, detail = self._apply(kind, parent, rng, cfg)
            if child != parent and cand.size(child) <= MAX_SIZE and path not in cfg.frozen_paths:
                return child, EditRecord(kind, path, cand.diff_features(parent, child), detail)
        child = Op("add", parent, Const(round(float(rng.normal(0, 0.1)), 3)))  # fallback: tiny additive term
        return child, EditRecord("add_term", (), cand.diff_features(parent, child), "fallback")

    def _apply(self, kind: str, parent: Expr, rng: np.random.Generator, cfg: ImproverConfig) -> tuple[Expr, cand.Path, str]:
        all_paths = cand.paths(parent)
        if kind == "perturb_const":
            consts = [p for p in all_paths if isinstance(cand.get_node(parent, p), Const)]
            if not consts:
                return parent, (), ""
            path = consts[int(rng.integers(len(consts)))]
            old = cand.get_node(parent, path)
            assert isinstance(old, Const)
            new = Const(round(old.value + float(rng.normal(0, cfg.step_sigma)), 3))
            return cand.replace_node(parent, path, new), path, f"{old.value:.3g}->{new.value:.3g}"
        if kind == "swap_op":
            ops = [p for p in all_paths if isinstance(cand.get_node(parent, p), Op)]
            if not ops:
                return parent, (), ""
            path = ops[int(rng.integers(len(ops)))]
            node = cand.get_node(parent, path)
            assert isinstance(node, Op)
            others = [o for o in cand.OPERATORS if o != node.op]
            new_op = str(rng.choice(others))
            return cand.replace_node(parent, path, Op(new_op, node.left, node.right)), path, f"{node.op}->{new_op}"
        if kind == "replace_subtree":
            path = all_paths[int(rng.integers(len(all_paths)))]
            return cand.replace_node(parent, path, random_expr(rng, 2)), path, "random subtree"
        if kind == "add_term":
            feat = _pick_feature(rng, cfg.feature_bias)
            coef = Const(round(float(rng.normal(0, 1.0)), 2))
            if rng.random() < 0.5:  # "match a target value" term: coef * |feature - target|
                target = Const(round(float(rng.uniform(0.0, 0.7)), 2))
                term: Expr = Op("mul", coef, Op("adiff", Var(feat), target))
            else:
                term = Op("mul", coef, Var(feat))
            op = str(rng.choice(["add", "sub"]))
            return Op(op, parent, term), (), f"{op} {cand.to_str(term)}"
        if kind == "prune":
            ops = [p for p in all_paths if isinstance(cand.get_node(parent, p), Op)]
            if not ops:
                return parent, (), ""
            path = ops[int(rng.integers(len(ops)))]
            node = cand.get_node(parent, path)
            assert isinstance(node, Op)
            keep = node.left if rng.random() < 0.5 else node.right
            return cand.replace_node(parent, path, keep), path, "collapse to child"
        return random_expr(rng, 3), (), "full rewrite"  # "rewrite"
