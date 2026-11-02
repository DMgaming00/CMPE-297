"""Gymnasium wrapper: one step = one "keep drafting?" decision (paper: binary depth action).

Two episode definitions:
  * "cycle" (default): an episode is ONE draft-verify cycle, started at a random point of a random trace. The reward
    is that cycle's reward, so credit assignment is immediate. Full-sequence episodes did not train: the return was a
    sum of per-cycle rates dominated by the unobservable number of remaining tokens (see docs/METHOD.md).
  * "sequence": an episode is a whole generation (kept for comparison).
"""
from __future__ import annotations

from typing import ClassVar

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .features import N_FEATURES
from .sim import SimCore
from .timing import TimingModel
from .traces import Trace

MAX_WARMUP_CYCLES = 30


class DraftDepthEnv(gym.Env):
    metadata: ClassVar[dict] = {"render_modes": []}

    def __init__(self, traces: list[Trace], timing: TimingModel, vocab_size: int, dmax: int,
                 reward: str = "throughput", noise: float = 0.05, seed: int = 0, episode: str = "cycle",
                 mask: tuple[int, ...] = ()):
        super().__init__()
        if episode not in ("cycle", "sequence"):
            raise ValueError(episode)
        self.traces = traces
        self.episode = episode
        self.mask = list(mask)   # observation indices zeroed out (feature ablation)
        self.np_rng = np.random.default_rng(seed)
        self.core = SimCore(timing, vocab_size, dmax, reward, noise, self.np_rng)
        self.observation_space = spaces.Box(low=-1.0, high=8.0, shape=(N_FEATURES,), dtype=np.float32)
        self.action_space = spaces.Discrete(2)   # 0 = stop and verify, 1 = draft another token

    def _masked(self, obs: np.ndarray) -> np.ndarray:
        if self.mask:
            obs = obs.copy()
            obs[self.mask] = 0.0
        return obs

    def _warm_up(self, trace: Trace) -> np.ndarray:
        """Advance a random number of cycles with a random-depth behaviour policy, so the episode starts mid-sequence
        with realistic context length and populated history features."""
        obs = self.core.reset(trace)
        n_warm = int(self.np_rng.integers(0, MAX_WARMUP_CYCLES))
        p_stop = float(self.np_rng.uniform(0.15, 0.7))      # varied typical depths in the history
        cycles_done = 0
        while cycles_done < n_warm:
            n_before = len(self.core.cycles)
            nxt, _, done, _ = self.core.step(bool(self.np_rng.random() > p_stop))
            if done:                                         # ran off the end: restart from the beginning
                return self.core.reset(trace)
            obs = nxt
            cycles_done += len(self.core.cycles) - n_before
        return obs

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        trace = self.traces[int(self.np_rng.integers(len(self.traces)))]
        obs = self._warm_up(trace) if self.episode == "cycle" else self.core.reset(trace)
        return self._masked(obs), {}

    def step(self, action):
        obs, reward, done, info = self.core.step(bool(int(action) == 1))
        if self.episode == "cycle" and "cycle" in info:      # the cycle just ended -> episode over
            done = True
        obs = np.zeros(N_FEATURES, dtype=np.float32) if done else self._masked(obs)
        return obs, float(reward), done, False, {}
