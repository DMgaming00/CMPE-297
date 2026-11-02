"""The NumPy MLP exported from a Stable-Baselines3 PPO policy must act exactly like the SB3 policy (deterministic)."""
import numpy as np
import pytest

pytest.importorskip("torch")
pytest.importorskip("stable_baselines3")
pytest.importorskip("gymnasium")

import torch
from stable_baselines3 import PPO

from ltdmini.gym_env import DraftDepthEnv
from ltdmini.policies import IDX
from ltdmini.timing import TimingModel
from ltdmini.traces import synthetic_traces
from ltdmini.train import export_sb3_policy


def _trained(mask=()):
    tr = synthetic_traces(10, 96, 8, seed=0)
    env = DraftDepthEnv(tr, TimingModel.synthetic(), 100, 8, seed=0, mask=mask)
    m = PPO("MlpPolicy", env, n_steps=256, batch_size=64, seed=0, device="cpu",
            policy_kwargs={"net_arch": {"pi": [16, 16], "vf": [16, 16]}, "activation_fn": torch.nn.Tanh})
    m.learn(1024)
    obs = []
    o, _ = env.reset()
    rng = np.random.default_rng(0)
    for _ in range(600):
        obs.append(o.copy())
        o, _, term, _, _ = env.step(int(rng.integers(2)))
        if term:
            o, _ = env.reset()
    return m, np.array(obs)


def test_exported_numpy_policy_matches_sb3_actions():
    m, X = _trained()
    pol = export_sb3_policy(m, "x")
    sb = np.array([int(m.predict(x, deterministic=True)[0]) for x in X])
    ex = np.array([int(pol.should_continue(x)) for x in X])
    assert (sb == ex).all()


def test_masked_policy_ignores_masked_features():
    idx = (IDX["recent_accept"], IDX["last_accept_frac"])
    m, X = _trained(mask=idx)
    pol = export_sb3_policy(m, "x", mask=idx)
    rng = np.random.default_rng(1)
    for x in X[:200]:
        y = x.copy()
        y[list(idx)] = rng.random(2)           # change only the masked inputs
        assert np.allclose(pol.logits(x), pol.logits(y))
