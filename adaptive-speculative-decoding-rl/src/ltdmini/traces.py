"""Decoding traces: the data the simulator replays.

Key idea (why the simulator is EXACT for greedy decoding): with greedy speculative
decoding, the final output equals the target model's greedy output regardless of the
draft depths chosen. So for every position p of that output we can precompute what
the draft would propose from context `prompt + y[:p]` (up to `dmax` tokens) and how
many of those proposals the target would accept. Any depth policy can then be
replayed exactly; only the step *times* come from the measured timing model.

One `Trace` per prompt:
    prompt_len : int
    n_tokens   : int                (N = length of the target's greedy output)
    top1       : float32 [N, dmax]  draft top-1 probability at each depth
    entropy    : float32 [N, dmax]  draft entropy at each depth
    accept_len : int16   [N]        leading draft tokens that match y[p], y[p+1], ...
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class Trace:
    prompt_len: int
    top1: np.ndarray
    entropy: np.ndarray
    accept_len: np.ndarray
    source: str = ""

    @property
    def n_tokens(self) -> int:
        return int(self.accept_len.shape[0])

    @property
    def dmax(self) -> int:
        return int(self.top1.shape[1])

    def validate(self) -> None:
        N, D = self.top1.shape
        assert self.entropy.shape == (N, D), "entropy shape mismatch"
        assert self.accept_len.shape == (N,), "accept_len shape mismatch"
        assert np.all((self.accept_len >= 0) & (self.accept_len <= D)), "accept_len out of range"
        assert np.all((self.top1 >= 0) & (self.top1 <= 1.0 + 1e-5)), "top1 out of range"


def save_traces(traces: list[Trace], path: str | Path, vocab_size: int, meta: dict | None = None) -> None:
    arrays: dict[str, np.ndarray] = {
        "prompt_len": np.array([t.prompt_len for t in traces], dtype=np.int32),
        "n_tokens": np.array([t.n_tokens for t in traces], dtype=np.int32),
        "top1": np.concatenate([t.top1 for t in traces]).astype(np.float32),
        "entropy": np.concatenate([t.entropy for t in traces]).astype(np.float32),
        "accept_len": np.concatenate([t.accept_len for t in traces]).astype(np.int16),
        "source": np.array([t.source for t in traces]),
        "vocab_size": np.array(vocab_size),
    }
    if meta:
        arrays["meta_json"] = np.array(__import__("json").dumps(meta))
    np.savez_compressed(path, **arrays)


def load_traces(path: str | Path) -> tuple[list[Trace], int]:
    z = np.load(path, allow_pickle=False)
    out, off = [], 0
    for i, (pl, n) in enumerate(zip(z["prompt_len"], z["n_tokens"])):
        n = int(n)
        out.append(Trace(int(pl), z["top1"][off:off + n], z["entropy"][off:off + n],
                         z["accept_len"][off:off + n], str(z["source"][i])))
        off += n
    return out, int(z["vocab_size"])


def synthetic_traces(n: int, n_tokens: int = 128, dmax: int = 12, seed: int = 0,
                     vocab_size: int = 32_000, difficulty: float = 0.0) -> list[Trace]:
    """Synthetic traces whose draft confidence is *informative* about acceptance,
    like real ones: easy stretches (high confidence, long accepts) alternate with hard
    ones. Used for unit tests and the zero-download smoke pipeline - never for results.
    """
    rng = np.random.default_rng(seed)
    traces = []
    for i in range(n):
        # latent per-position "easiness" following a slow random walk
        z = np.cumsum(rng.normal(0, 0.35, n_tokens)) * 0.5 - difficulty
        easiness = 1 / (1 + np.exp(-(z - z.mean())))
        alpha = 0.35 + 0.6 * easiness                       # per-position acceptance prob
        top1 = np.zeros((n_tokens, dmax), np.float32)
        ent = np.zeros((n_tokens, dmax), np.float32)
        acc = np.zeros(n_tokens, np.int16)
        for p in range(n_tokens):
            a = 0
            alive = True
            for d in range(dmax):
                pos = min(p + d, n_tokens - 1)
                conf = np.clip(alpha[pos] + rng.normal(0, 0.08), 0.02, 0.999)
                top1[p, d] = conf
                ent[p, d] = float(-np.log(conf) * 2.0 + rng.uniform(0, 0.3))
                if alive and rng.random() < alpha[pos]:
                    a += 1
                else:
                    alive = False
            acc[p] = a
        traces.append(Trace(prompt_len=int(rng.integers(40, 300)), top1=top1, entropy=ent,
                            accept_len=acc, source=f"synthetic-{i}"))
    return traces
