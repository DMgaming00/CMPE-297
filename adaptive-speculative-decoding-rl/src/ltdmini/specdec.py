"""Greedy autoregressive decoding and chain speculative decoding with a depth policy.

Written from scratch on top of Hugging Face forward passes (no `generate`, no vLLM),
so every step is visible and timed.

Cache invariant used throughout: a model's KV cache covers `seq[:cache_len]`; the
next forward pass feeds `seq[cache_len:]`. After verification, both caches are
cropped so they never contain rejected tokens.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import torch
from transformers import DynamicCache

from .device import Stopwatch
from .features import FeatureBuilder
from .policies import DepthPolicy
from .sampling import greedy_accept


def _ids(tokens: list[int], device) -> torch.Tensor:
    return torch.tensor([tokens], dtype=torch.long, device=device)


def crop_to(cache: DynamicCache, length: int) -> None:
    """Truncate the cache to `length` positions.

    `DynamicCache.crop` changed meaning across transformers versions: older ones take the absolute target length,
    v5 takes a *negative* number of tokens to remove. A negative argument means "remove |n| tokens" in both, so we
    always pass that form.
    """
    extra = cache.get_seq_length() - length
    if extra > 0:
        cache.crop(-extra)


def _top1_entropy(logits: torch.Tensor) -> tuple[int, float, float]:
    logp = torch.log_softmax(logits.float(), dim=-1)
    p = logp.exp()
    top1_p, tok = p.max(dim=-1)
    ent = float(-(p * logp).sum())
    return int(tok), float(top1_p), ent


@dataclass
class DecodeResult:
    tokens: list[int]
    prefill_s: float
    decode_s: float
    cycles: list[dict] = field(default_factory=list)

    @property
    def n_new(self) -> int:
        return len(self.tokens)


@torch.inference_mode()
def greedy_autoregressive(model, prompt: list[int], max_new_tokens: int, eos_ids: set[int],
                          device) -> DecodeResult:
    sw = Stopwatch(device)
    cache = DynamicCache()
    t0 = sw.now()
    out = model(input_ids=_ids(prompt, device), past_key_values=cache, use_cache=True)
    nxt = int(out.logits[0, -1].argmax())
    t1 = sw.now()
    tokens = [nxt]
    while len(tokens) < max_new_tokens and nxt not in eos_ids:
        out = model(input_ids=_ids([nxt], device), past_key_values=cache, use_cache=True)
        nxt = int(out.logits[0, -1].argmax())
        tokens.append(nxt)
    t2 = sw.now()
    return DecodeResult(tokens, t1 - t0, t2 - t1)


@torch.inference_mode()
def speculative_greedy(target, draft, prompt: list[int], policy: DepthPolicy, max_new_tokens: int,
                       dmax: int, eos_ids: set[int], vocab_size: int, device) -> DecodeResult:
    """Chain speculative decoding. After each draft step, `policy.should_continue(features)`
    decides whether to draft another token (up to `dmax`). Output is identical to
    `greedy_autoregressive(target, ...)` up to floating-point nondeterminism."""
    sw = Stopwatch(device)
    seq = list(prompt)
    tc, dc = DynamicCache(), DynamicCache()
    fb = FeatureBuilder(dmax, vocab_size)
    policy.reset()

    t0 = sw.now()
    if len(seq) > 1:  # prefill both models on seq[:-1]; the last prompt token is fed by the first cycle
        target(input_ids=_ids(seq[:-1], device), past_key_values=tc, use_cache=True)
        draft(input_ids=_ids(seq[:-1], device), past_key_values=dc, use_cache=True)
    t_len = d_len = len(seq) - 1
    t1 = sw.now()

    generated: list[int] = []
    cycles: list[dict] = []
    while len(generated) < max_new_tokens:
        L = len(seq)
        fb.start_cycle()
        # ---- draft phase -------------------------------------------------------------
        ta = sw.now()
        drafts: list[int] = []
        feed = seq[d_len:]
        for depth in range(1, dmax + 1):
            out = draft(input_ids=_ids(feed, device), past_key_values=dc, use_cache=True)
            d_len += len(feed)
            tok, top1, ent = _top1_entropy(out.logits[0, -1])
            drafts.append(tok)
            feat = fb.build(depth, L, top1, ent)
            if depth == dmax or not policy.should_continue(feat):
                break
            feed = [tok]
        tb = sw.now()
        # ---- verify phase: one target pass over [last token] + drafts -------------------
        feed_t = seq[t_len:] + drafts
        out = target(input_ids=_ids(feed_t, device), past_key_values=tc, use_cache=True)
        t_len += len(feed_t)
        k = len(drafts)
        target_argmax = out.logits[0, -(k + 1):].argmax(dim=-1).tolist()
        n, nxt = greedy_accept(drafts, target_argmax)
        tc_ = sw.now()
        # ---- roll back rejected positions in both caches ---------------------------------
        keep = L + n                      # caches must cover the new seq[:-1]
        crop_to(tc, keep); t_len = keep
        if d_len > keep:
            crop_to(dc, keep); d_len = keep
        new = drafts[:n] + [nxt]
        fb.end_cycle(n, k)
        cycles.append({"depth": k, "accepted": n, "t_draft": tb - ta, "t_verify": tc_ - tb, "ctx_len": L})
        seq += new
        generated += new
        hit = [i for i, t in enumerate(new) if t in eos_ids]
        if hit:
            generated = generated[: len(generated) - len(new) + hit[0] + 1]
            break
    t2 = sw.now()
    return DecodeResult(generated[:max_new_tokens], t1 - t0, t2 - t1, cycles)


@torch.inference_mode()
def draft_from_every_position(draft, prompt: list[int], continuation: list[int], dmax: int,
                              device) -> tuple[list[list[float]], list[list[float]], list[int]]:
    """For each position p of `continuation` (the target's greedy output), draft `dmax`
    tokens greedily from context prompt + continuation[:p] and record per-depth top-1
    probability, entropy, and how many leading drafts match continuation[p:].

    Uses one draft cache that is cropped back after every probe, so the cost is
    N * dmax single-token forward passes (no re-prefill)."""
    seq = list(prompt)
    dc = DynamicCache()
    if len(seq) > 1:
        draft(input_ids=_ids(seq[:-1], device), past_key_values=dc, use_cache=True)
    d_len = len(seq) - 1
    top1s, ents, accs = [], [], []
    N = len(continuation)
    for p in range(N):
        L = len(seq)
        feed = seq[d_len:]
        row_p, row_e, drafted = [], [], []
        for _ in range(dmax):
            out = draft(input_ids=_ids(feed, device), past_key_values=dc, use_cache=True)
            d_len += len(feed)
            tok, top1, ent = _top1_entropy(out.logits[0, -1])
            row_p.append(top1); row_e.append(ent); drafted.append(tok)
            feed = [tok]
        a = 0
        while a < dmax and p + a < N and drafted[a] == continuation[p + a]:
            a += 1
        top1s.append(row_p); ents.append(row_e); accs.append(a)
        crop_to(dc, L)                    # keep the entry for seq[-1] (fed in the first probe step)
        d_len = L
        seq.append(continuation[p])     # advance along the true greedy output
    return top1s, ents, accs
