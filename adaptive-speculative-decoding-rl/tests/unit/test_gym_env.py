"""Episode semantics of the Gymnasium wrapper used for PPO training."""
import numpy as np
import pytest

pytest.importorskip("gymnasium")

from ltdmini.gym_env import DraftDepthEnv
from ltdmini.sim import cycle_reward
from ltdmini.timing import TimingModel
from ltdmini.traces import synthetic_traces

TM = TimingModel(d0=0.004, d1=0.0, v0=0.02, v1=0.001, v2=0.0, a0=0.02, a1=0.0)
TRACES = synthetic_traces(6, 120, 8, seed=1)


def _cycle_ctx(env, c):
    # context length when the cycle ran = prompt + position before the cycle advanced
    return env.core.trace.prompt_len + env.core.pos - c.new_tokens


def _env(episode, reward="throughput"):
    return DraftDepthEnv(TRACES, TM, 100, 8, reward=reward, noise=0.0, seed=0, episode=episode)


@pytest.mark.parametrize("reward", ["throughput", "acceptance", "time"])
def test_cycle_episode_ends_after_exactly_one_cycle_with_that_cycles_reward(reward):
    env = _env("cycle", reward)
    rng = np.random.default_rng(0)
    for _ in range(40):
        obs, _ = env.reset()
        assert np.isfinite(obs).all()
        n_before = len(env.core.cycles)
        done, steps, total = False, 0, 0.0
        while not done:
            obs, r, done, _, _ = env.step(int(rng.integers(2)))
            total += r
            steps += 1
            assert steps <= 8, "an episode cannot exceed dmax decisions"
        assert len(env.core.cycles) == n_before + 1
        c = env.core.cycles[-1]
        assert np.isclose(total, c.reward)
        assert np.isclose(c.reward, cycle_reward(reward, c.accepted, c.t_draft, c.t_verify,
                                                 TM.ar_step(_cycle_ctx(env, c))))


def test_cycle_episodes_start_at_varied_positions():
    env = _env("cycle")
    starts = set()
    for _ in range(60):
        env.reset()
        starts.add(env.core.pos)
    assert len(starts) > 5, "warm-up should randomize the start position"


def test_sequence_episode_runs_to_the_end_of_the_trace():
    env = _env("sequence")
    env.reset()
    done = False
    while not done:
        _, _, done, _, _ = env.step(0)
    assert env.core.pos >= env.core.trace.n_tokens


def test_feature_mask_zeroes_exactly_the_requested_observation_indices():
    from ltdmini.policies import IDX

    idx = (IDX["recent_accept"], IDX["last_accept_frac"])
    env = DraftDepthEnv(TRACES, TM, 100, 8, reward="throughput", noise=0.0, seed=0, mask=idx)
    rng = np.random.default_rng(0)
    seen = []
    for _ in range(30):
        obs, _ = env.reset()
        done = False
        while True:
            assert all(obs[i] == 0.0 for i in idx)
            seen.append(obs.copy())
            if done:
                break
            obs, _, done, _, _ = env.step(int(rng.integers(2)))
            if done:
                break
    others = [i for i in range(len(seen[0])) if i not in idx]
    assert np.abs(np.array(seen)[:, others]).sum() > 0, "unmasked features must still carry information"
