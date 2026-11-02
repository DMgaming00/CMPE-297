"""Trace-replay simulator for chain speculative decoding (greedy).

`SimCore` is a step-wise environment: one step = one depth decision.
`simulate()` runs any DepthPolicy over a list of traces and returns metrics.

Reward variants (paper Sec. 6.3, Table 2), computed once per draft-and-verify cycle:
    throughput : (accepted + 1) / (t_draft + t_verify), scaled by ar_step(L)
                 -> "tokens per autoregressive-step-equivalent" (~ local speedup)
    acceptance : accepted + 1                    (acceptance length only)
    time       : -(t_draft + t_verify) / ar_step(L)   (time cost only)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .features import FeatureBuilder
from .policies import DepthPolicy
from .timing import TimingModel
from .traces import Trace

REWARDS = ("throughput", "acceptance", "time")


@dataclass
class CycleResult:
    depth: int
    accepted: int
    new_tokens: int
    t_draft: float
    t_verify: float
    reward: float


def cycle_reward(kind: str, accepted: int, t_draft: float, t_verify: float, ar_step: float) -> float:
    if kind == "throughput":
        return (accepted + 1) / (t_draft + t_verify) * ar_step
    if kind == "acceptance":
        return float(accepted + 1)
    if kind == "time":
        return -(t_draft + t_verify) / ar_step
    raise ValueError(kind)


class SimCore:
    """Replays one trace. Usage:
        obs = core.reset(trace); while not done: obs, r, done, info = core.step(continue_flag)
    """

    def __init__(self, timing: TimingModel, vocab_size: int, dmax: int, reward: str = "throughput",
                 noise: float = 0.0, rng: np.random.Generator | None = None):
        self.timing, self.dmax, self.reward_kind, self.noise = timing, dmax, reward, noise
        self.fb = FeatureBuilder(dmax, vocab_size)
        self.rng = rng or np.random.default_rng(0)

    def _jitter(self, t: float) -> float:
        return t * float(np.exp(self.rng.normal(0, self.noise))) if self.noise > 0 else t

    def reset(self, trace: Trace) -> np.ndarray:
        assert trace.dmax >= self.dmax, "trace was recorded with a smaller dmax"
        self.trace, self.pos, self.depth = trace, 0, 1
        self.fb.reset()
        self.fb.start_cycle()
        self.cycles: list[CycleResult] = []
        return self._obs()

    @property
    def ctx_len(self) -> int:
        return self.trace.prompt_len + self.pos

    def _obs(self) -> np.ndarray:
        d = self.depth
        return self.fb.build(d, self.ctx_len, float(self.trace.top1[self.pos, d - 1]),
                             float(self.trace.entropy[self.pos, d - 1]))

    def step(self, cont: bool) -> tuple[np.ndarray | None, float, bool, dict]:
        """`cont`: draft another token (True) or stop and verify now (False)."""
        if cont and self.depth < self.dmax:
            self.depth += 1
            return self._obs(), 0.0, False, {}
        k = self.depth
        L = self.ctx_len
        n = int(min(self.trace.accept_len[self.pos], k))
        remaining = self.trace.n_tokens - self.pos
        new = min(n + 1, remaining)
        t_d = self._jitter(self.timing.draft_total(k, L))
        t_v = self._jitter(self.timing.verify(k, L))
        r = cycle_reward(self.reward_kind, n, t_d, t_v, self.timing.ar_step(L))
        self.cycles.append(CycleResult(k, n, new, t_d, t_v, r))
        self.fb.end_cycle(n, k)
        self.pos += new
        done = self.pos >= self.trace.n_tokens
        info = {"cycle": self.cycles[-1]}
        if done:
            return None, r, True, info
        self.depth = 1
        self.fb.start_cycle()
        return self._obs(), r, False, info


@dataclass
class SeqMetrics:
    source: str
    n_tokens: int
    sd_time: float
    ar_time: float
    cycles: int
    mean_accept_len: float          # tau: mean tokens produced per cycle (accepted + 1)
    mean_depth: float
    speedup: float = field(init=False)

    def __post_init__(self):
        self.speedup = self.ar_time / self.sd_time if self.sd_time > 0 else float("nan")


def ar_time(trace: Trace, timing: TimingModel) -> float:
    return sum(timing.ar_step(trace.prompt_len + i) for i in range(trace.n_tokens))


def simulate(policy: DepthPolicy, traces: list[Trace], timing: TimingModel, vocab_size: int,
             dmax: int, noise: float = 0.0, seed: int = 0) -> list[SeqMetrics]:
    core = SimCore(timing, vocab_size, dmax, "throughput", noise, np.random.default_rng(seed))
    out = []
    for tr in traces:
        policy.reset()
        obs = core.reset(tr)
        done = False
        while not done:
            obs, _, done, _ = core.step(policy.should_continue(obs))
        cyc = core.cycles
        out.append(SeqMetrics(
            source=tr.source, n_tokens=tr.n_tokens,
            sd_time=sum(c.t_draft + c.t_verify for c in cyc), ar_time=ar_time(tr, timing),
            cycles=len(cyc), mean_accept_len=float(np.mean([c.new_tokens for c in cyc])),
            mean_depth=float(np.mean([c.depth for c in cyc])),
        ))
    return out


def summarize(metrics: list[SeqMetrics]) -> dict:
    """Aggregate speedup = total AR time / total SD time (token-weighted), plus mean per-sequence."""
    ar = sum(m.ar_time for m in metrics)
    sd = sum(m.sd_time for m in metrics)
    return {
        "speedup": ar / sd,
        "speedup_mean_per_seq": float(np.mean([m.speedup for m in metrics])),
        "tau": float(np.sum([m.mean_accept_len * m.cycles for m in metrics]) / np.sum([m.cycles for m in metrics])),
        "mean_depth": float(np.mean([m.mean_depth for m in metrics])),
        "n_seqs": len(metrics),
        "n_tokens": int(sum(m.n_tokens for m in metrics)),
    }
