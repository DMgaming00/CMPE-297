"""End-to-end evaluation with real models and wall-clock time.

For every held-out prompt and every policy: run greedy autoregressive decoding and
speculative decoding, time both (prefill + decode, synchronized), check that outputs
match, and record per-prompt results. Policies are run in an interleaved order per
prompt to spread thermal and background-load effects evenly.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from .models import ModelPair, encode_prompt
from .policies import DepthPolicy
from .specdec import greedy_autoregressive, speculative_greedy


def warmup(pair: ModelPair, dmax: int, policy: DepthPolicy) -> None:
    ids = encode_prompt(pair.tokenizer, "Warm-up prompt for compilation and caches.", 64)
    for _ in range(2):
        greedy_autoregressive(pair.target, ids, 16, pair.eos_ids, pair.device)
        speculative_greedy(pair.target, pair.draft, ids, policy, 16, dmax, pair.eos_ids, pair.vocab_size, pair.device)


def evaluate_real(pair: ModelPair, prompts: list[tuple[str, str]], policies: dict[str, DepthPolicy],
                  max_new_tokens: int, dmax: int, max_prompt_tokens: int, out_path: Path,
                  seed: int = 0) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    warmup(pair, dmax, next(iter(policies.values())))
    with out_path.open("w") as f:
        for i, (tag, text) in enumerate(prompts):
            ids = encode_prompt(pair.tokenizer, text, max_prompt_tokens)
            ar = greedy_autoregressive(pair.target, ids, max_new_tokens, pair.eos_ids, pair.device)
            ar_total = ar.prefill_s + ar.decode_s
            order = list(policies.items())
            rng.shuffle(order)
            for name, pol in order:
                sd = speculative_greedy(pair.target, pair.draft, ids, pol, max_new_tokens, dmax,
                                        pair.eos_ids, pair.vocab_size, pair.device)
                sd_total = sd.prefill_s + sd.decode_s
                n = min(len(ar.tokens), len(sd.tokens))
                eq = [a == b for a, b in zip(ar.tokens[:n], sd.tokens[:n], strict=True)]
                match = sum(eq) / max(n, 1)
                first_div = eq.index(False) if not all(eq) else -1      # -1 = identical over the compared length
                cyc = sd.cycles
                row = {
                    "prompt": tag, "policy": name, "prompt_tokens": len(ids),
                    "ar_tokens": len(ar.tokens), "sd_tokens": len(sd.tokens),
                    "ar_seconds": ar_total, "sd_seconds": sd_total,
                    "ar_tok_per_s": len(ar.tokens) / ar_total, "sd_tok_per_s": len(sd.tokens) / sd_total,
                    "speedup": (sd.n_new / sd_total) / (len(ar.tokens) / ar_total),
                    "tau": sum(c["accepted"] + 1 for c in cyc) / max(len(cyc), 1),
                    "mean_depth": sum(c["depth"] for c in cyc) / max(len(cyc), 1),
                    "draft_seconds": sum(c["t_draft"] for c in cyc),
                    "verify_seconds": sum(c["t_verify"] for c in cyc),
                    "token_match_rate": match, "exact_match": all(eq), "first_divergence": first_div,
                }
                rows.append(row)
                f.write(json.dumps(row) + "\n")
                f.flush()
            done = [r for r in rows if r["prompt"] == tag]
            print(f"  [{i + 1}/{len(prompts)}] {tag:<16} " +
                  "  ".join(f"{r['policy']}: {r['speedup']:.2f}x" for r in sorted(done, key=lambda r: r["policy"])),
                  flush=True)
    return rows
