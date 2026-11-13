"""Linear readout that predicts an edit's value from its diff features before evaluation.

Mirrors the central mechanism of Budget RSI (arXiv:2610.29121): a ridge-regularised
linear model over [bias, parent score, 8 diff features], fitted once on a small set of
labelled edits and then *frozen* (no further fitting at deployment time).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.core.candidate import EDIT_FEATURE_NAMES, EditRecord

FEATURE_NAMES: tuple[str, ...] = ("bias", "parent_score", *EDIT_FEATURE_NAMES)


def edit_vector(edit: EditRecord, parent_score: float, use_diff: bool = True) -> np.ndarray:
    """Feature vector for one proposed edit. ``use_diff=False`` gives the parent-rate-only ablation."""
    diff = [edit.features[k] if use_diff else 0.0 for k in EDIT_FEATURE_NAMES]
    return np.array([1.0, max(parent_score, -30.0) / 10.0, *diff])


@dataclass
class LinearReadout:
    weights: np.ndarray
    use_diff: bool = True

    def predict(self, edit: EditRecord, parent_score: float) -> float:
        return float(self.weights @ edit_vector(edit, parent_score, self.use_diff))

    def to_dict(self) -> dict[str, float]:
        return {n: float(w) for n, w in zip(FEATURE_NAMES, self.weights)}


def fit_readout(X: np.ndarray, y: np.ndarray, ridge: float = 1.0, use_diff: bool = True) -> LinearReadout:
    """Closed-form ridge regression (bias is not penalised)."""
    reg = ridge * np.eye(X.shape[1])
    reg[0, 0] = 0.0
    w = np.linalg.solve(X.T @ X + reg, X.T @ y)
    return LinearReadout(w, use_diff)


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return 0.0
    ra, rb = a.argsort().argsort().astype(float), b.argsort().argsort().astype(float)
    return float(np.corrcoef(ra, rb)[0, 1])
