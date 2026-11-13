"""Structural-anomaly detectors over an episode's edit trace (SO-RSI, arXiv:2610.05701).

The three anomaly types follow the paper: recurrence (same fix attempted repeatedly),
opposing edits (an edit that undoes an earlier one) and expectation mismatch (an outcome
that violates what the trace predicted). Detection reads only the recorded trace.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.history import DiscoveryTree


@dataclass(frozen=True)
class Anomaly:
    kind: str  # recurrence | opposing_edits | expectation_mismatch
    subject: str
    evidence: str
    node_ids: tuple[int, ...] = ()


def _delta(detail: str) -> float | None:
    """Parse 'a->b' const-perturbation details into b - a."""
    if "->" not in detail:
        return None
    a, b = detail.split("->", 1)
    try:
        return float(b) - float(a)
    except ValueError:
        return None


def accepted_nodes(tree: DiscoveryTree) -> list[int]:
    """Nodes that improved on their parent (the hill-climber's accepted edits)."""
    out = []
    for n in tree.nodes[1:]:
        p = tree.nodes[n.parent]  # type: ignore[index]
        if n.score is not None and p.score is not None and n.score > p.score + 1e-12:
            out.append(n.id)
    return out


def detect_recurrence(tree: DiscoveryTree, min_tries: int = 8) -> list[Anomaly]:
    """An edit kind tried >= ``min_tries`` times that never once improved the parent."""
    acc = set(accepted_nodes(tree))
    tries: dict[str, list[int]] = {}
    for n in tree.nodes[1:]:
        if n.edit:
            tries.setdefault(n.edit.kind, []).append(n.id)
    return [
        Anomaly("recurrence", kind, f"{len(ids)} '{kind}' edits, 0 improved", tuple(ids[:5]))
        for kind, ids in tries.items()
        if len(ids) >= min_tries and not (set(ids) & acc)
    ]


def detect_opposing(tree: DiscoveryTree) -> list[Anomaly]:
    """Two accepted edits at the same path whose effects reverse each other."""
    out: list[Anomaly] = []
    acc = [tree.nodes[i] for i in accepted_nodes(tree)]
    for i, a in enumerate(acc):
        for b in acc[i + 1 :]:
            if not (a.edit and b.edit) or a.edit.kind != b.edit.kind or a.edit.path != b.edit.path:
                continue
            da, db = _delta(a.edit.detail), _delta(b.edit.detail)
            reversed_const = da is not None and db is not None and da * db < 0
            reversed_op = (
                a.edit.kind == "swap_op"
                and "->" in a.edit.detail
                and "->" in b.edit.detail
                and a.edit.detail.split("->")[::-1] == b.edit.detail.split("->")
            )
            if reversed_const or reversed_op:
                out.append(Anomaly("opposing_edits", a.edit.kind, f"nodes {a.id} and {b.id} reverse each other", (a.id, b.id)))
    return out[:1]  # one finding per episode is enough to trigger inquiry


def detect_mismatch(train_gain: float, validation_gain: float, min_train_gain: float = 1.0) -> Anomaly | None:
    """Train improvement that fails to appear on fresh validation instances."""
    if train_gain > min_train_gain and validation_gain < 0.25 * train_gain:
        return Anomaly(
            "expectation_mismatch",
            "train_vs_validation",
            f"train gain {train_gain:+.2f} but validation gain {validation_gain:+.2f}",
        )
    return None
