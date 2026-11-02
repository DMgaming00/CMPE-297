"""Train the depth policy with PPO (Stable-Baselines3, as in the paper) in the
trace-replay simulator, selecting the checkpoint with the best VALIDATION speedup
(paper: "checkpoints are chosen by validation speedup").

The trained policy is exported to NumPy weights (`MLPPolicy`) so evaluation and
real decoding never depend on Stable-Baselines3.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from .policies import MLPPolicy
from .sim import simulate, summarize
from .timing import TimingModel
from .traces import Trace


def export_sb3_policy(model, name: str, mask: tuple[int, ...] = ()) -> MLPPolicy:
    from torch import nn
    layers = [m for m in model.policy.mlp_extractor.policy_net if isinstance(m, nn.Linear)]
    layers.append(model.policy.action_net)
    W = [l.weight.detach().cpu().numpy().astype(np.float64) for l in layers]
    b = [l.bias.detach().cpu().numpy().astype(np.float64) for l in layers]
    for i in mask:                 # a masked feature is always 0 during training, so cut its first-layer weights:
        W[0][:, i] = 0.0           # the exported policy is then exactly invariant to that input
    return MLPPolicy(W, b, name=name)


def train_ppo(train: list[Trace], val: list[Trace], timing: TimingModel, vocab: int, dmax: int,
              reward: str, total_timesteps: int, n_steps: int, batch_size: int, learning_rate: float,
              gamma: float, net_arch: list[int], eval_every: int, noise: float, seed: int,
              out_dir: Path, mask: tuple[int, ...] = ()) -> tuple[MLPPolicy, list[dict]]:
    import torch
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback

    from .gym_env import DraftDepthEnv

    torch.manual_seed(seed)
    env = DraftDepthEnv(train, timing, vocab, dmax, reward=reward, noise=noise, seed=seed, mask=mask)
    model = PPO("MlpPolicy", env, n_steps=n_steps, batch_size=batch_size, learning_rate=learning_rate,
                gamma=gamma, policy_kwargs={"net_arch": {"pi": net_arch, "vf": net_arch}, "activation_fn": torch.nn.Tanh},
                seed=seed, verbose=0, device="cpu")
    name = f"ltd-mini-{reward}"
    history: list[dict] = []
    best = {"speedup": -1.0, "policy": None}

    class ValCallback(BaseCallback):
        def _on_step(self) -> bool:
            if self.num_timesteps % eval_every < 1 or self.num_timesteps == total_timesteps:
                pol = export_sb3_policy(self.model, name, mask)
                s = summarize(simulate(pol, val, timing, vocab, dmax))
                history.append({"timesteps": int(self.num_timesteps), **s})
                print(f"  [{reward}] step {self.num_timesteps:>8,}  val speedup {s['speedup']:.3f}  "
                      f"tau {s['tau']:.2f}  mean depth {s['mean_depth']:.2f}", flush=True)
                if s["speedup"] > best["speedup"]:
                    best.update(speedup=s["speedup"], policy=pol)
            return True

    t0 = time.time()
    model.learn(total_timesteps=total_timesteps, callback=ValCallback())
    final = export_sb3_policy(model, name, mask)
    s = summarize(simulate(final, val, timing, vocab, dmax))
    history.append({"timesteps": total_timesteps, **s})
    if s["speedup"] > best["speedup"]:
        best.update(speedup=s["speedup"], policy=final)
    policy: MLPPolicy = best["policy"]
    out_dir.mkdir(parents=True, exist_ok=True)
    policy.save(out_dir / f"policy_{reward}.json")
    (out_dir / f"train_history_{reward}.json").write_text(json.dumps(
        {"reward": reward, "train_seconds": time.time() - t0, "best_val_speedup": best["speedup"],
         "history": history}, indent=2))
    return policy, history
