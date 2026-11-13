"""Candidate solutions: priority-function expressions for greedy TSP construction.

A *candidate* is a small expression tree (a tiny program) that scores every unvisited
city; the highest-scoring city is visited next.
The DSL is deliberately closed (whitelisted operators and variables only) so that
"self-modification" is bounded: agents can only edit expression trees.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np

VARIABLES: tuple[str, ...] = ("d_cur", "d_start", "d_cent", "d_iso", "t")
OPERATORS: tuple[str, ...] = ("add", "sub", "mul", "pdiv", "max", "min", "adiff")
EDIT_FEATURE_NAMES: tuple[str, ...] = (
    "added_nodes",
    "removed_nodes",
    "delta_depth",
    "const_shift",
    "op_changes",
    "var_changes",
    "is_structural",
    "new_vars",
)

Path = tuple[int, ...]


@dataclass(frozen=True)
class Const:
    value: float


@dataclass(frozen=True)
class Var:
    name: str


@dataclass(frozen=True)
class Op:
    op: str
    left: Expr
    right: Expr


Expr = Const | Var | Op


def evaluate(expr: Expr, env: dict[str, np.ndarray]) -> np.ndarray | float:
    """Vectorised evaluation of ``expr`` over per-bin feature arrays."""
    if isinstance(expr, Const):
        return expr.value
    if isinstance(expr, Var):
        return env[expr.name]
    a = evaluate(expr.left, env)
    b = evaluate(expr.right, env)
    if expr.op == "add":
        return a + b
    if expr.op == "sub":
        return a - b
    if expr.op == "mul":
        return a * b
    if expr.op == "pdiv":  # protected division
        return a / (np.abs(b) + 0.05)
    if expr.op == "max":
        return np.maximum(a, b)
    if expr.op == "adiff":  # absolute difference |a - b|: "how close is a to target b"
        return np.abs(a - b)
    return np.minimum(a, b)


def to_str(expr: Expr) -> str:
    if isinstance(expr, Const):
        return f"{expr.value:.3g}"
    if isinstance(expr, Var):
        return expr.name
    return f"{expr.op}({to_str(expr.left)}, {to_str(expr.right)})"


def size(expr: Expr) -> int:
    if isinstance(expr, Op):
        return 1 + size(expr.left) + size(expr.right)
    return 1


def depth(expr: Expr) -> int:
    if isinstance(expr, Op):
        return 1 + max(depth(expr.left), depth(expr.right))
    return 1


def paths(expr: Expr, prefix: Path = ()) -> list[Path]:
    """All node paths (0 = left child, 1 = right child), root first."""
    out: list[Path] = [prefix]
    if isinstance(expr, Op):
        out += paths(expr.left, prefix + (0,))
        out += paths(expr.right, prefix + (1,))
    return out


def get_node(expr: Expr, path: Path) -> Expr:
    for step in path:
        assert isinstance(expr, Op)
        expr = expr.left if step == 0 else expr.right
    return expr


def replace_node(expr: Expr, path: Path, new: Expr) -> Expr:
    if not path:
        return new
    assert isinstance(expr, Op)
    if path[0] == 0:
        return Op(expr.op, replace_node(expr.left, path[1:], new), expr.right)
    return Op(expr.op, expr.left, replace_node(expr.right, path[1:], new))


def to_dict(expr: Expr) -> dict[str, Any]:
    if isinstance(expr, Const):
        return {"c": expr.value}
    if isinstance(expr, Var):
        return {"v": expr.name}
    return {"op": expr.op, "l": to_dict(expr.left), "r": to_dict(expr.right)}


def from_dict(data: dict[str, Any]) -> Expr:
    if "c" in data:
        return Const(float(data["c"]))
    if "v" in data:
        if data["v"] not in VARIABLES:
            raise ValueError(f"unknown variable {data['v']!r}")
        return Var(data["v"])
    if data["op"] not in OPERATORS:
        raise ValueError(f"unknown operator {data['op']!r}")
    return Op(data["op"], from_dict(data["l"]), from_dict(data["r"]))


def parse(text: str) -> Expr:
    """Parse the textual form produced by :func:`to_str` (used for LLM proposals)."""
    tokens = text.replace("(", " ( ").replace(")", " ) ").replace(",", " , ").split()
    pos = 0

    def node() -> Expr:
        nonlocal pos
        if pos >= len(tokens):
            raise ValueError("unexpected end of expression")
        tok = tokens[pos]
        pos += 1
        if tok in OPERATORS:
            if pos >= len(tokens) or tokens[pos] != "(":
                raise ValueError(f"expected '(' after {tok}")
            pos += 1
            left = node()
            if pos >= len(tokens) or tokens[pos] != ",":
                raise ValueError("expected ','")
            pos += 1
            right = node()
            if pos >= len(tokens) or tokens[pos] != ")":
                raise ValueError("expected ')'")
            pos += 1
            return Op(tok, left, right)
        if tok in VARIABLES:
            return Var(tok)
        try:
            return Const(float(tok))
        except ValueError as exc:
            raise ValueError(f"unknown token {tok!r}") from exc

    result = node()
    if pos != len(tokens):
        raise ValueError("trailing tokens after expression")
    return result


def _tokens(expr: Expr) -> list[str]:
    if isinstance(expr, Const):
        return ["const"]
    if isinstance(expr, Var):
        return [f"var:{expr.name}"]
    return [f"op:{expr.op}"] + _tokens(expr.left) + _tokens(expr.right)


def _consts(expr: Expr) -> list[float]:
    if isinstance(expr, Const):
        return [expr.value]
    if isinstance(expr, Var):
        return []
    return _consts(expr.left) + _consts(expr.right)


def diff_features(old: Expr, new: Expr) -> dict[str, float]:
    """Eight cheap diff features describing an edit (old -> new).

    These play the role of the "diff features" in Budget RSI: they are computed
    from the edit alone, *before* any evaluation.
    """
    a, b = Counter(_tokens(old)), Counter(_tokens(new))
    added = sum((b - a).values())
    removed = sum((a - b).values())
    op_a = Counter(t for t in a.elements() if t.startswith("op:"))
    op_b = Counter(t for t in b.elements() if t.startswith("op:"))
    var_a = Counter(t for t in a.elements() if t.startswith("var:"))
    var_b = Counter(t for t in b.elements() if t.startswith("var:"))
    ca, cb = sorted(_consts(old)), sorted(_consts(new))
    n = min(len(ca), len(cb))
    shift = float(sum(abs(x - y) for x, y in zip(ca[:n], cb[:n])))
    return {
        "added_nodes": float(added),
        "removed_nodes": float(removed),
        "delta_depth": float(depth(new) - depth(old)),
        "const_shift": shift,
        "op_changes": float(sum(((op_a - op_b) + (op_b - op_a)).values())) / 2.0,
        "var_changes": float(sum(((var_a - var_b) + (var_b - var_a)).values())) / 2.0,
        "is_structural": 1.0 if added + removed >= 3 else 0.0,
        "new_vars": float(sum((var_b - var_a).values())),
    }


@dataclass
class EditRecord:
    """What an agent did to the parent to obtain a child."""

    kind: str
    path: Path
    features: dict[str, float]
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "path": list(self.path), "features": self.features, "detail": self.detail}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EditRecord:
        return cls(d["kind"], tuple(d["path"]), dict(d["features"]), d.get("detail", ""))


@dataclass
class Candidate:
    """A node of the discovery tree."""

    id: int
    parent: int | None
    expr: Expr
    edit: EditRecord | None = None
    score: float | None = None  # train score (higher is better)
    solved: int | None = None  # train instances where bins <= Best-Fit bins
    n_instances: int | None = None
    cost: float = 0.0  # cumulative budget units spent when this node was evaluated
    round: int = 0
    children: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "parent": self.parent,
            "expr": to_dict(self.expr),
            "edit": self.edit.to_dict() if self.edit else None,
            "score": self.score,
            "solved": self.solved,
            "n_instances": self.n_instances,
            "cost": self.cost,
            "round": self.round,
            "children": self.children,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Candidate:
        return cls(
            id=d["id"],
            parent=d["parent"],
            expr=from_dict(d["expr"]),
            edit=EditRecord.from_dict(d["edit"]) if d["edit"] else None,
            score=d["score"],
            solved=d["solved"],
            n_instances=d["n_instances"],
            cost=d["cost"],
            round=d["round"],
            children=list(d["children"]),
        )
