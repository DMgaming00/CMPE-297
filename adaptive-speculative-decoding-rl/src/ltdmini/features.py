"""Observation features for the depth policy.

The SAME code builds features in the trace-replay simulator (training) and during
real decoding (evaluation), so a learned policy sees identical inputs in both.

Paper (Sec. 4): the depth policy observes the probabilities of the draft tree's
last-layer tokens, the current draft depth D and the context length L. With chain
drafting, the "last layer" is a single token, so we use its top-1 probability and
entropy, plus two cheap history signals (documented deviation, docs/METHOD.md).
"""
from __future__ import annotations

import numpy as np

FEATURE_NAMES = [
    "depth_frac",        # d / dmax
    "ctx_len_norm",      # L / 2048
    "top1_prob",         # draft's top-1 probability at depth d
    "entropy_norm",      # draft entropy at depth d / log(vocab)
    "cum_top1",          # product of top-1 probs for depths 1..d (proxy for P(all accepted))
    "recent_accept",     # EMA of (accepted / drafted) over previous cycles
    "last_accept_frac",  # accepted in previous cycle / dmax
]
N_FEATURES = len(FEATURE_NAMES)


class FeatureBuilder:
    """Stateful feature builder; call `reset()` per sequence, `start_cycle()` per cycle,
    `build()` after each draft step and `end_cycle()` after verification."""

    def __init__(self, dmax: int, vocab_size: int, ema: float = 0.7):
        self.dmax = dmax
        self.log_v = float(np.log(max(vocab_size, 2)))
        self.ema = ema
        self.reset()

    def reset(self) -> None:
        self.recent = 0.5
        self.last_frac = 0.0
        self.cum = 1.0

    def start_cycle(self) -> None:
        self.cum = 1.0

    def build(self, depth: int, ctx_len: int, top1: float, entropy: float) -> np.ndarray:
        self.cum *= float(top1)
        return np.array(
            [
                depth / self.dmax,
                min(ctx_len / 2048.0, 4.0),
                float(top1),
                float(entropy) / self.log_v,
                self.cum,
                self.recent,
                self.last_frac,
            ],
            dtype=np.float32,
        )

    def end_cycle(self, n_accepted: int, n_drafted: int) -> None:
        rate = n_accepted / max(n_drafted, 1)
        self.recent = self.ema * self.recent + (1 - self.ema) * rate
        self.last_frac = n_accepted / self.dmax
