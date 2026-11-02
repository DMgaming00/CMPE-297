"""The trace-replay simulator: exact bookkeeping, rewards, and sanity properties."""
import numpy as np
import pytest

from ltdmini.policies import ConfidenceStop, FixedDepth
from ltdmini.sim import SimCore, ar_time, cycle_reward, simulate, summarize
from ltdmini.timing import TimingModel
from ltdmini.traces import Trace, synthetic_traces

TM = TimingModel(d0=0.004, d1=0.0, v0=0.02, v1=0.001, v2=0.0, a0=0.02, a1=0.0)


def hand_trace():
    # 6 output tokens; accept-run lengths chosen by hand
    acc = np.array([3, 0, 2, 1, 0, 0], np.int16)
    top1 = np.full((6, 4), 0.9, np.float32)
    return Trace(prompt_len=10, top1=top1, entropy=np.ones((6, 4), np.float32), accept_len=acc, source="hand-0")


def test_fixed_depth_bookkeeping_matches_hand_calculation():
    tr = hand_trace()
    m = simulate(FixedDepth(2, 4), [tr], TM, vocab_size=100, dmax=4)[0]
    # cycles: pos0 acc=min(3,2)=2 -> +3 (pos3); pos3 acc=min(1,2)=1 -> +2 (pos5); pos5 acc 0 -> +1 (pos6)
    assert m.cycles == 3
    assert np.isclose(m.mean_accept_len, (3 + 2 + 1) / 3)
    expected_sd = 3 * (2 * 0.004 + 0.02 + 0.001 * 2)
    assert np.isclose(m.sd_time, expected_sd)
    assert np.isclose(m.ar_time, 6 * 0.02)


def test_every_token_is_produced_exactly_once():
    for tr in synthetic_traces(5, 80, 8, seed=3):
        core = SimCore(TM, 100, 8)
        core.reset(tr)
        done = False
        rng = np.random.default_rng(0)
        while not done:
            _, _, done, _ = core.step(bool(rng.random() < 0.6))
        assert sum(c.new_tokens for c in core.cycles) == tr.n_tokens


def test_depth_never_exceeds_dmax():
    tr = synthetic_traces(1, 60, 6, seed=1)[0]
    core = SimCore(TM, 100, 6)
    core.reset(tr)
    done = False
    while not done:
        _, _, done, _ = core.step(True)  # always ask to continue
    assert max(c.depth for c in core.cycles) == 6


def test_reward_variants():
    assert cycle_reward("acceptance", 3, 0.1, 0.1, 0.02) == 4
    assert np.isclose(cycle_reward("throughput", 3, 0.01, 0.03, 0.02), 4 / 0.04 * 0.02)
    assert np.isclose(cycle_reward("time", 3, 0.01, 0.03, 0.02), -2.0)
    with pytest.raises(ValueError):
        cycle_reward("nope", 1, 1, 1, 1)


def test_k1_with_free_drafting_and_perfect_acceptance_doubles_speed():
    tm = TimingModel(d0=1e-9, d1=0, v0=0.02, v1=0, v2=0, a0=0.02, a1=0)
    acc = np.full(100, 8, np.int16)
    tr = Trace(5, np.ones((100, 8), np.float32), np.zeros((100, 8), np.float32), acc, "perfect-0")
    s = summarize(simulate(FixedDepth(1, 8), [tr], tm, 100, 8))
    assert abs(s["speedup"] - 2.0) < 1e-3


def test_informative_confidence_beats_bad_fixed_depth_on_synthetic():
    traces = synthetic_traces(20, 96, 12, seed=0)
    tm = TimingModel.synthetic()
    fixed12 = summarize(simulate(FixedDepth(12, 12), traces, tm, 32000, 12))["speedup"]
    conf = summarize(simulate(ConfidenceStop(0.6), traces, tm, 32000, 12))["speedup"]
    assert conf > fixed12


def test_ar_time_uses_context_length():
    tm = TimingModel(d0=0, d1=0, v0=0, v1=0, v2=0, a0=0.01, a1=0.001)
    tr = hand_trace()
    assert np.isclose(ar_time(tr, tm), sum(0.01 + 0.001 * (10 + i) for i in range(6)))
