"""LTD-Mini: a laptop-scale replication of "Learning to Draft: Adaptive Speculative
Decoding with Reinforcement Learning" (Zhang et al., ICLR 2026).

Modules that need only NumPy (importable everywhere, unit-tested in CI):
    sampling, features, timing, traces (data format + synthetic traces), sim,
    policies, tune, stats, report, config

Modules that need PyTorch + Transformers (run on your Mac / CI with torch):
    device, models, specdec, profile, build_traces, real_eval

Modules that need Gymnasium + Stable-Baselines3 (training only):
    gym_env, train
"""

__version__ = "0.1.0"
