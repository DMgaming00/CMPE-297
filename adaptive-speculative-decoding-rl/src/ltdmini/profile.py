"""Measure draft-step, verify and autoregressive-step times on this machine and fit
the TimingModel used by the simulator."""
from __future__ import annotations

import statistics

import torch
from transformers import DynamicCache

from .device import Stopwatch
from .specdec import crop_to
from .timing import TimingModel, fit_timing_model


@torch.inference_mode()
def _time_forward(model, ctx: list[int], n_new: int, device, repeats: int) -> float:
    """Median time of one forward pass over `n_new` tokens with a cache of len(ctx)."""
    sw = Stopwatch(device)
    cache = DynamicCache()
    model(input_ids=torch.tensor([ctx], device=device), past_key_values=cache, use_cache=True)
    L = len(ctx)
    times = []
    for _ in range(repeats + 2):          # first 2 = warm-up
        feed = torch.randint(3, 200, (1, n_new), device=device)
        t0 = sw.now()
        model(input_ids=feed, past_key_values=cache, use_cache=True)
        times.append(sw.now() - t0)
        crop_to(cache, L)
    return statistics.median(times[2:])


def profile_pair(pair, dmax: int, ctx_lengths=(128, 384, 768), repeats: int = 15) -> tuple[TimingModel, dict]:
    dev = pair.device
    g = torch.Generator().manual_seed(0)
    draft_s, verify_s, ar_s = [], [], []
    for L in ctx_lengths:
        ctx = torch.randint(3, 200, (L,), generator=g).tolist()
        draft_s.append((L, _time_forward(pair.draft, ctx, 1, dev, repeats)))
        ar_s.append((L, _time_forward(pair.target, ctx, 1, dev, repeats)))
        for k in range(1, dmax + 1):
            verify_s.append((k, L, _time_forward(pair.target, ctx, k + 1, dev, repeats)))
        print(f"  L={L:4d}  draft {draft_s[-1][1]*1e3:6.2f} ms  target 1-tok {ar_s[-1][1]*1e3:6.2f} ms  "
              f"verify k={dmax} {verify_s[-1][2]*1e3:6.2f} ms", flush=True)
    tm = fit_timing_model(draft_s, verify_s, ar_s, device=str(dev))
    raw = {"draft": draft_s, "verify": verify_s, "ar": ar_s}
    return tm, raw
