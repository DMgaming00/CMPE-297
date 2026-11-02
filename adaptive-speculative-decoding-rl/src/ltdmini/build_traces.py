"""Generate traces from real models: target greedy output + draft probes at every position."""
from __future__ import annotations

import time

import numpy as np

from .models import ModelPair, encode_prompt
from .specdec import draft_from_every_position, greedy_autoregressive
from .traces import Trace


def build_traces(pair: ModelPair, prompts: list[tuple[str, str]], max_new_tokens: int, dmax: int,
                 max_prompt_tokens: int) -> list[Trace]:
    traces = []
    t0 = time.time()
    for i, (tag, text) in enumerate(prompts):
        ids = encode_prompt(pair.tokenizer, text, max_prompt_tokens)
        ar = greedy_autoregressive(pair.target, ids, max_new_tokens, pair.eos_ids, pair.device)
        y = ar.tokens
        top1, ent, acc = draft_from_every_position(pair.draft, ids, y, dmax, pair.device)
        tr = Trace(prompt_len=len(ids), top1=np.array(top1, np.float32), entropy=np.array(ent, np.float32),
                   accept_len=np.array(acc, np.int16), source=tag)
        tr.validate()
        traces.append(tr)
        mean_acc = float(np.mean(acc)) if acc else 0.0
        print(f"  [{i + 1}/{len(prompts)}] {tag:<16} prompt {len(ids):4d} tok  output {len(y):4d} tok  "
              f"mean accept-run {mean_acc:.2f}  elapsed {time.time() - t0:6.0f}s", flush=True)
    return traces
