"""The policy-development step: propose revised search policies from discovery history.

In the paper this step is an LLM agent that reads replay trajectories and rewrites
policy *code*. Here it is a transparent rule-based stand-in that reads the same kind
of evidence (where improvements came from, how long stalls last) and edits the
policy's parameters. It is *not* an LLM; see docs/limitations.md.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from src.agents.tree_search import SearchPolicy
from src.core.history import DiscoveryTree


def history_stats(trees: list[DiscoveryTree]) -> dict[str, float]:
    """Summarise where improvements came from across recorded trees."""
    parent_rank, parent_children, root_hits, gaps = [], [], [], []
    n_improving = 0
    for tree in trees:
        best_gap_start = 0
        for node in tree.nodes[1:]:
            parent = tree.nodes[node.parent]  # type: ignore[index]
            if node.score is None or parent.score is None:
                continue
            earlier = [n.score for n in tree.nodes[: node.id] if n.score is not None]
            if node.score > parent.score + 1e-12:
                n_improving += 1
                parent_rank.append(float(np.mean([s <= parent.score for s in earlier])))
                parent_children.append(float(sum(1 for c in parent.children if c < node.id)))
                root_hits.append(1.0 if parent.id == 0 else 0.0)
            if node.score > max(earlier) + 1e-12:
                gaps.append(float(node.id - best_gap_start))
                best_gap_start = node.id
    return {
        "n_improving": float(n_improving),
        "mean_parent_rank": float(np.mean(parent_rank)) if parent_rank else 0.5,
        "mean_parent_children": float(np.mean(parent_children)) if parent_children else 0.0,
        "root_share": float(np.mean(root_hits)) if root_hits else 0.0,
        "stall_p90": float(np.percentile(gaps, 90)) if gaps else 1000.0,
    }


def propose_revisions(
    policy: SearchPolicy, trees: list[DiscoveryTree], rng: np.random.Generator, n: int = 3
) -> list[SearchPolicy]:
    """Return ``n`` revised policies (the caller adds the incumbent and replays all)."""
    st = history_stats(trees)
    revisions: list[SearchPolicy] = []
    # R1: follow the evidence on exploit vs explore
    exploit_more = st["mean_parent_rank"] >= 0.6
    r1 = replace(
        policy,
        temperature=policy.temperature * (0.5 if exploit_more else 1.5),
        explore_c=policy.explore_c + (0.0 if exploit_more else 0.3),
        restart_prob=max(policy.restart_prob, min(0.3, st["root_share"] * 0.5)),
    )
    revisions.append(r1.clamp())
    # R2: R1 plus a stopping rule fitted to observed stall lengths and some parallelism
    r2 = replace(r1, patience=max(3.0, st["stall_p90"] * 1.2), batch=min(policy.batch * 2, 4))
    revisions.append(r2.clamp())
    # R3 onwards: seeded multiplicative jitter (exploration of policy space)
    while len(revisions) < n:
        jit = lambda x: float(x * np.exp(rng.normal(0, 0.5)))
        revisions.append(
            replace(
                policy,
                temperature=jit(policy.temperature) if policy.temperature > 0 else float(rng.uniform(0, 0.5)),
                explore_c=float(abs(policy.explore_c + rng.normal(0, 0.2))),
                restart_prob=float(abs(policy.restart_prob + rng.normal(0, 0.05))),
                batch=int(rng.choice([1, 2, 4])),
                patience=jit(min(policy.patience, 40.0)),
            ).clamp()
        )
    return revisions[:n]
