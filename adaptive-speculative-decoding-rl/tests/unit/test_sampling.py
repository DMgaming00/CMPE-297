"""The math of speculative decoding, tested without any model."""
import numpy as np
import pytest
from scipy.stats import chisquare

from ltdmini.sampling import expected_tokens_per_step, greedy_accept, residual_distribution, speculative_sample


def test_greedy_accept_all_and_bonus():
    assert greedy_accept([5, 6, 7], [5, 6, 7, 9]) == (3, 9)


def test_greedy_accept_first_reject_gives_correction():
    assert greedy_accept([5, 6, 7], [5, 8, 7, 9]) == (1, 8)


def test_greedy_accept_none():
    assert greedy_accept([5], [4, 3]) == (0, 4)


def test_greedy_accept_shape_check():
    with pytest.raises(ValueError):
        greedy_accept([1, 2], [1, 2])


def test_residual_is_normalized_and_nonnegative():
    p = np.array([0.5, 0.3, 0.2]); q = np.array([0.2, 0.5, 0.3])
    r = residual_distribution(p, q)
    assert np.isclose(r.sum(), 1) and (r >= 0).all() and r[1] == 0 and r[2] == 0


def test_residual_falls_back_when_equal():
    p = np.array([0.25, 0.75])
    assert np.allclose(residual_distribution(p, p), p)


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_speculative_sampling_is_lossless_first_token(seed):
    """The first emitted token must be distributed exactly as the target p, whatever q is."""
    rng = np.random.default_rng(seed)
    V = 6
    p = rng.dirichlet(np.ones(V)); q = rng.dirichlet(np.ones(V))
    p2 = rng.dirichlet(np.ones(V))  # target dist after the first draft (irrelevant to the first token)
    n = 40_000
    counts = np.zeros(V)
    for _ in range(n):
        x = int(rng.choice(V, p=q))
        acc, nxt = speculative_sample([x], q[None], np.stack([p, p2]), rng)
        first = x if acc >= 1 else nxt
        counts[first] += 1
    _stat, pval = chisquare(counts, n * p)
    assert pval > 1e-3, (counts / n, p)


def test_speculative_sampling_identical_dists_accepts_everything():
    rng = np.random.default_rng(0)
    p = np.array([0.1, 0.6, 0.3])
    for _ in range(200):
        x = int(rng.choice(3, p=p))
        acc, _ = speculative_sample([x], p[None], np.stack([p, p]), rng)
        assert acc == 1


def test_expected_tokens_formula():
    assert expected_tokens_per_step(0.0, 4) == 1.0
    assert expected_tokens_per_step(1.0, 4) == 5.0
    assert np.isclose(expected_tokens_per_step(0.8, 4), (1 - 0.8 ** 5) / 0.2)
