"""Speculative decoding acceptance rules, independent of any model.

These pure-NumPy functions are the mathematical core and are unit-tested on toy
distributions. `specdec.py` uses the greedy rule; the stochastic rule is provided
(and tested) for the temperature > 0 extension.

References: Leviathan et al. 2023 ("Fast Inference from Transformers via
Speculative Decoding"); Chen et al. 2023 ("Accelerating LLM Decoding with
Speculative Sampling").
"""
from __future__ import annotations

import numpy as np


def greedy_accept(draft_tokens: list[int], target_argmax: list[int]) -> tuple[int, int]:
    """Greedy verification.

    Args:
        draft_tokens: k drafted tokens d_1..d_k.
        target_argmax: k+1 target argmax tokens g_0..g_k, where g_i is the target's
            choice after the prefix extended by d_1..d_i.

    Returns:
        (n_accepted, next_token): the number of leading drafts that match, and the
        token appended after them (the correction g_n, or the bonus g_k if all match).
    """
    if len(target_argmax) != len(draft_tokens) + 1:
        raise ValueError("target_argmax must have exactly len(draft_tokens) + 1 entries")
    n = 0
    while n < len(draft_tokens) and draft_tokens[n] == target_argmax[n]:
        n += 1
    return n, int(target_argmax[n])


def residual_distribution(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    """norm(max(0, p - q)); falls back to p if the residual has no mass (p == q)."""
    r = np.clip(p - q, 0.0, None)
    s = r.sum()
    return p / p.sum() if s <= 0 else r / s


def speculative_sample(
    draft_tokens: list[int],
    q_dists: np.ndarray,
    p_dists: np.ndarray,
    rng: np.random.Generator,
) -> tuple[int, int]:
    """Stochastic speculative sampling (lossless w.r.t. the target distribution).

    Args:
        draft_tokens: k tokens sampled from the draft distributions.
        q_dists: (k, V) draft distributions used to sample each draft token.
        p_dists: (k+1, V) target distributions at each position (last row = bonus).
        rng: random generator.

    Returns:
        (n_accepted, next_token) exactly as in `greedy_accept`.
    """
    k = len(draft_tokens)
    if q_dists.shape[0] != k or p_dists.shape[0] != k + 1:
        raise ValueError("shape mismatch between drafts, q_dists and p_dists")
    for i, x in enumerate(draft_tokens):
        p_x, q_x = p_dists[i, x], q_dists[i, x]
        if q_x <= 0:
            raise ValueError("draft token has zero draft probability")
        if rng.random() < min(1.0, p_x / q_x):
            continue
        r = residual_distribution(p_dists[i], q_dists[i])
        return i, int(rng.choice(len(r), p=r))
    bonus = p_dists[k] / p_dists[k].sum()
    return k, int(rng.choice(len(bonus), p=bonus))


def expected_tokens_per_step(alpha: float, gamma: int) -> float:
    """Expected tokens per verify step with i.i.d. acceptance rate alpha and gamma drafts:
    (1 - alpha^(gamma+1)) / (1 - alpha)."""
    if not 0 <= alpha <= 1:
        raise ValueError("alpha must be in [0, 1]")
    if alpha == 1.0:
        return float(gamma + 1)
    return (1 - alpha ** (gamma + 1)) / (1 - alpha)
