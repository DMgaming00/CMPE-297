"""Depth policies: decide, after each draft step, whether to draft another token.

All policies share one interface so the simulator and the real decoder can run any
of them:  `should_continue(features) -> bool`.

Baselines (training-free, each tuned on validation traces by grid search):
    FixedDepth(k)            static draft length (the "Eagle3 + grid search" analogue)
    ConfidenceStop(h)        stop when the draft's top-1 probability < h  (max-confidence family)
    EntropyStop(h)           stop when the draft entropy > h               (SVIP-style)
    CumulativeStop(h)        stop when prod of top-1 probs < h              (SpecDec++-style estimate)
Learned:
    MLPPolicy                PPO-trained MLP, exported to NumPy weights (LTD-Mini)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .features import FEATURE_NAMES

IDX = {name: i for i, name in enumerate(FEATURE_NAMES)}


class DepthPolicy:
    name = "policy"

    def reset(self) -> None:  # called once per sequence
        pass

    def should_continue(self, feat: np.ndarray) -> bool:
        raise NotImplementedError

    def describe(self) -> str:
        return self.name


@dataclass
class FixedDepth(DepthPolicy):
    k: int
    dmax: int

    def __post_init__(self):
        self.name = f"fixed-k{self.k}"

    def should_continue(self, feat: np.ndarray) -> bool:
        depth = round(feat[IDX["depth_frac"]] * self.dmax)
        return depth < self.k


@dataclass
class ConfidenceStop(DepthPolicy):
    h: float

    def __post_init__(self):
        self.name = f"confidence-h{self.h:.2f}"

    def should_continue(self, feat: np.ndarray) -> bool:
        return bool(feat[IDX["top1_prob"]] >= self.h)


@dataclass
class EntropyStop(DepthPolicy):
    h: float  # threshold on normalized entropy

    def __post_init__(self):
        self.name = f"entropy-h{self.h:.3f}"

    def should_continue(self, feat: np.ndarray) -> bool:
        return bool(feat[IDX["entropy_norm"]] <= self.h)


@dataclass
class CumulativeStop(DepthPolicy):
    h: float

    def __post_init__(self):
        self.name = f"cumulative-h{self.h:.2f}"

    def should_continue(self, feat: np.ndarray) -> bool:
        return bool(feat[IDX["cum_top1"]] >= self.h)


class MLPPolicy(DepthPolicy):
    """Deterministic NumPy forward pass of a Stable-Baselines3 PPO MlpPolicy
    (tanh hidden layers -> 2 action logits; action 1 = continue)."""

    def __init__(self, weights: list[np.ndarray], biases: list[np.ndarray], name: str = "ltd-mini"):
        self.W, self.b, self.name = weights, biases, name

    def logits(self, feat: np.ndarray) -> np.ndarray:
        h = feat.astype(np.float64)
        for i, (W, b) in enumerate(zip(self.W, self.b)):
            h = h @ W.T + b
            if i < len(self.W) - 1:
                h = np.tanh(h)
        return h

    def should_continue(self, feat: np.ndarray) -> bool:
        return bool(np.argmax(self.logits(feat)) == 1)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps({
            "name": self.name,
            "weights": [w.tolist() for w in self.W],
            "biases": [b.tolist() for b in self.b],
        }))

    @classmethod
    def load(cls, path: str | Path) -> MLPPolicy:
        d = json.loads(Path(path).read_text())
        return cls([np.array(w) for w in d["weights"]], [np.array(b) for b in d["biases"]], d.get("name", "ltd-mini"))


def baseline_grid(dmax: int) -> list[DepthPolicy]:
    pols: list[DepthPolicy] = [FixedDepth(k, dmax) for k in range(1, dmax + 1)]
    pols += [ConfidenceStop(h) for h in np.round(np.arange(0.05, 0.96, 0.05), 2)]
    pols += [EntropyStop(h) for h in np.round(np.linspace(0.01, 0.5, 20), 3)]
    pols += [CumulativeStop(h) for h in np.round(np.arange(0.05, 0.96, 0.05), 2)]
    return pols


def family(policy: DepthPolicy) -> str:
    return policy.name.split("-")[0]
