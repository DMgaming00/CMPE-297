"""Prompt sets. Mirrors the paper: train on HumanEval; evaluate on MT-Bench, GSM8K,
Alpaca and Natural Questions (small samples). Falls back to bundled prompts when
offline or for the smoke pipeline."""
from __future__ import annotations

import json
import random
from pathlib import Path

BUNDLED = Path(__file__).resolve().parents[2] / "data" / "sample_prompts.jsonl"

# name -> (HF dataset id, config, split, text field builder)
SOURCES = {
    "humaneval": ("openai/openai_humaneval", None, "test",
                  lambda r: "Complete the following Python function.\n\n" + r["prompt"]),
    "gsm8k": ("openai/gsm8k", "main", "test", lambda r: r["question"]),
    "alpaca": ("tatsu-lab/alpaca", None, "train",
               lambda r: r["instruction"] + (("\n\n" + r["input"]) if r.get("input") else "")),
    "mtbench": ("HuggingFaceH4/mt_bench_prompts", None, "train", lambda r: r["prompt"][0]),
    "nq": ("google-research-datasets/nq_open", None, "validation", lambda r: r["question"]),
}


def bundled(name: str) -> list[str]:
    rows = [json.loads(l) for l in BUNDLED.read_text().splitlines() if l.strip()]
    return [r["text"] for r in rows if r["set"] == name] or [r["text"] for r in rows]


def load_prompts(name: str, n: int, seed: int = 0, offset: int = 0, offline: bool = False) -> list[tuple[str, str]]:
    """Returns [(source_tag, prompt_text)]. `offset` lets train/val draw disjoint slices of one set."""
    texts: list[str]
    if offline:
        texts = bundled(name)
    else:
        try:
            from datasets import load_dataset
            hf_id, cfg, split, fn = SOURCES[name]
            ds = load_dataset(hf_id, cfg, split=split)
            texts = [fn(r) for r in ds]
        except Exception as e:  # noqa: BLE001 - any Hub/schema failure falls back, loudly. network or schema problems -> be explicit, then fall back
            print(f"[data] could not load {name} from the Hub ({e!r}); using bundled prompts")
            texts = bundled(name)
    rng = random.Random(seed)
    idx = list(range(len(texts)))
    rng.shuffle(idx)
    if offline:   # bundled set is tiny: wrap around so smoke runs always get n prompts
        picked = [texts[idx[(offset + i) % len(idx)]] for i in range(n)]
    else:
        picked = [texts[i] for i in idx[offset: offset + n]]
    return [(f"{name}-{offset + i}", t) for i, t in enumerate(picked)]
