"""Discovery history: the tree of every attempt an agent made.

The same structure is the *memory* of the baselines, the raw material Dream-RSI
turns into replay worlds, and the labelled-edit source for Budget RSI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.core.candidate import Candidate, EditRecord, Expr


class DiscoveryTree:
    def __init__(self, task: str, root_expr: Expr) -> None:
        self.task = task
        self.nodes: list[Candidate] = [Candidate(id=0, parent=None, expr=root_expr)]

    @property
    def root(self) -> Candidate:
        return self.nodes[0]

    def add_child(self, parent_id: int, expr: Expr, edit: EditRecord | None, round_: int) -> Candidate:
        node = Candidate(id=len(self.nodes), parent=parent_id, expr=expr, edit=edit, round=round_)
        self.nodes.append(node)
        self.nodes[parent_id].children.append(node.id)
        return node

    def evaluated(self) -> list[Candidate]:
        return [n for n in self.nodes if n.score is not None]

    def best(self) -> Candidate:
        """Highest train score; earliest node wins ties."""
        return max(self.evaluated(), key=lambda n: (n.score, -n.id))  # type: ignore[arg-type, return-value]

    def best_curve(self) -> list[tuple[float, float]]:
        """(cumulative cost, best-so-far score) after every evaluation."""
        curve: list[tuple[float, float]] = []
        best = float("-inf")
        for node in sorted(self.evaluated(), key=lambda n: n.id):
            best = max(best, node.score)  # type: ignore[type-var]
            curve.append((node.cost, best))
        return curve

    def lineage(self, node_id: int) -> list[int]:
        out = [node_id]
        while self.nodes[out[-1]].parent is not None:
            out.append(self.nodes[out[-1]].parent)  # type: ignore[arg-type]
        return out[::-1]

    def to_dict(self) -> dict[str, Any]:
        return {"task": self.task, "nodes": [n.to_dict() for n in self.nodes]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DiscoveryTree:
        tree = cls.__new__(cls)
        tree.task = data["task"]
        tree.nodes = [Candidate.from_dict(d) for d in data["nodes"]]
        return tree

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict()))

    @classmethod
    def load(cls, path: str | Path) -> DiscoveryTree:
        return cls.from_dict(json.loads(Path(path).read_text()))
