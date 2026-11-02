"""Features, policies, timing fits, stats, trace I/O, tuning and the report."""
import json

import numpy as np

from ltdmini.evaluate import evaluate_sim
from ltdmini.features import N_FEATURES, FeatureBuilder
from ltdmini.policies import ConfidenceStop, CumulativeStop, EntropyStop, FixedDepth, MLPPolicy
from ltdmini.report import build_report
from ltdmini.stats import bootstrap_ci, paired_bootstrap_diff, ratio_bootstrap_ci
from ltdmini.timing import TimingModel, fit_timing_model
from ltdmini.traces import load_traces, save_traces, synthetic_traces
from ltdmini.tune import tune_baselines


def test_features_shape_and_cumulative_product():
    fb = FeatureBuilder(dmax=8, vocab_size=1000)
    fb.start_cycle()
    f1 = fb.build(1, 100, 0.5, 1.0)
    f2 = fb.build(2, 100, 0.5, 1.0)
    assert f1.shape == (N_FEATURES,) and np.isclose(f2[4], 0.25)
    fb.end_cycle(2, 4)
    assert 0.5 < fb.recent < 1 or np.isclose(fb.recent, 0.5)


def test_policies_decisions():
    fb = FeatureBuilder(dmax=8, vocab_size=1000)
    fb.start_cycle()
    f = fb.build(3, 100, 0.7, 0.5)
    assert FixedDepth(4, 8).should_continue(f) and not FixedDepth(3, 8).should_continue(f)
    assert ConfidenceStop(0.6).should_continue(f) and not ConfidenceStop(0.8).should_continue(f)
    assert EntropyStop(0.1).should_continue(f)
    assert not CumulativeStop(0.9).should_continue(f)


def test_mlp_policy_roundtrip(tmp_path):
    rng = np.random.default_rng(0)
    W = [rng.normal(size=(8, N_FEATURES)), rng.normal(size=(2, 8))]
    b = [rng.normal(size=8), rng.normal(size=2)]
    p = MLPPolicy(W, b, "ltd-test")
    p.save(tmp_path / "p.json")
    q = MLPPolicy.load(tmp_path / "p.json")
    x = rng.normal(size=N_FEATURES).astype(np.float32)
    assert np.allclose(p.logits(x), q.logits(x)) and q.name == "ltd-test"


def test_timing_fit_recovers_coefficients():
    rng = np.random.default_rng(0)
    draft = [(L, 0.003 + 1e-6 * L + rng.normal(0, 1e-6)) for L in range(100, 1000, 100)]
    verify = [(k, L, 0.02 + 0.001 * k + 2e-6 * L) for k in range(1, 9) for L in (128, 512, 900)]
    ar = [(L, 0.019 + 2e-6 * L) for L in range(100, 1000, 100)]
    tm = fit_timing_model(draft, verify, ar, "test")
    assert abs(tm.v1 - 0.001) < 1e-6 and abs(tm.a0 - 0.019) < 1e-6 and abs(tm.d0 - 0.003) < 1e-4


def test_trace_roundtrip(tmp_path):
    tr = synthetic_traces(3, 20, 6, seed=0, vocab_size=500)
    save_traces(tr, tmp_path / "t.npz", 500, meta={"x": 1})
    back, vocab = load_traces(tmp_path / "t.npz")
    assert vocab == 500 and len(back) == 3
    for a, b in zip(tr, back):
        b.validate()
        assert np.array_equal(a.accept_len, b.accept_len) and a.source == b.source


def test_stats():
    m, lo, hi = bootstrap_ci([1, 2, 3, 4, 5])
    assert lo < m < hi
    r, lo, hi = ratio_bootstrap_ci([2, 2, 2], [1, 1, 1])
    assert r == 2 and lo == 2 and hi == 2
    d = paired_bootstrap_diff([2, 3, 4, 5], [1, 2, 3, 4])
    assert d["mean_diff"] == 1 and d["significant"] and d["win_rate"] == 1


def test_tune_evaluate_and_report(tmp_path):
    tm = TimingModel.synthetic()
    val = synthetic_traces(8, 64, 12, seed=1)
    test = synthetic_traces(8, 64, 12, seed=2)
    best, rows = tune_baselines(val, tm, 32000, 12)
    assert set(best) == {"fixed", "confidence", "entropy", "cumulative"} and len(rows) > 40
    res = evaluate_sim({p.name: p for p in best.values()}, test, tm, 32000, 12,
                       reference=best["fixed"].name, seeds=(0,))
    assert "overall" in res["groups"] and res["paired_vs_reference"]
    (tmp_path / "sim_results.json").write_text(json.dumps(res, default=float))
    tm.save(tmp_path / "timing.json")
    out = build_report(tmp_path)
    text = out.read_text()
    assert "Simulated evaluation" in text and (tmp_path / "figures" / "headline_speedup.png").exists()
