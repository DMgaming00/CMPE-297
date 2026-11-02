"""Compare candidate (target, draft) pairs BEFORE choosing the main experiment's models.

For each pair, on MPS fp16 and CPU fp32:
  * cost ratio  = draft 1-token step time / target 1-token step time   (the lower, the more room for speculation)
  * agreement   = how often the draft's top-1 token equals the target's greedy token, teacher-forced on the target's
                  own 64-token greedy continuation of HumanEval prompts that are disjoint from train/val/test.

Speculative decoding only pays when the draft is much cheaper AND agrees often, so both are reported.
Run it ALONE (timing-sensitive):   python scripts/compare_pairs.py
Writes results/model_selection/pairs.json and pairs.md.
"""
from __future__ import annotations

import gc
import json
from pathlib import Path

import torch

from ltdmini.data import load_prompts
from ltdmini.models import encode_prompt, load_pair
from ltdmini.profile import profile_pair
from ltdmini.specdec import greedy_autoregressive

PAIRS = [
    ("HuggingFaceTB/SmolLM2-360M-Instruct", "HuggingFaceTB/SmolLM2-135M-Instruct"),
    ("EleutherAI/pythia-410m", "EleutherAI/pythia-70m"),
    ("EleutherAI/pythia-410m", "EleutherAI/pythia-160m"),
    ("openai-community/gpt2-medium", "distilbert/distilgpt2"),
]
OUT = Path("results/model_selection")


def agreement(pair, prompts, n_new: int = 64) -> tuple[float, int]:
    hit = tot = 0
    with torch.inference_mode():
        for _, text in prompts:
            ids = encode_prompt(pair.tokenizer, text, 256)
            out = greedy_autoregressive(pair.target, ids, n_new, pair.eos_ids, pair.device).tokens
            seq = torch.tensor([ids + out], device=pair.device)
            d = pair.draft(input_ids=seq).logits[0, len(ids) - 1:-1].argmax(-1).cpu()
            hit += int((d == torch.tensor(out)).sum())
            tot += len(out)
    return hit / tot, tot


def nparams(m) -> int:
    return sum(p.numel() for p in m.parameters())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    prompts = load_prompts("humaneval", 24, seed=0, offset=124)      # disjoint from train(0:100) and val(100:124)
    rows = []
    for tgt, dr in PAIRS:
        rec = {"target": tgt, "draft": dr}
        for dev, dt in (("mps", "float16"), ("cpu", "float32")):
            pair = load_pair(tgt, dr, device=dev, dtype=dt)
            rec["target_params_m"] = nparams(pair.target) / 1e6
            rec["draft_params_m"] = nparams(pair.draft) / 1e6
            rec["target_layers"] = pair.target.config.num_hidden_layers
            rec["draft_layers"] = pair.draft.config.num_hidden_layers
            _, raw = profile_pair(pair, 8, ctx_lengths=(128, 512), repeats=9)
            a, d = dict(raw["ar"]), dict(raw["draft"])
            rec[f"{dev}_cost_ratio_L128"] = d[128] / a[128]
            rec[f"{dev}_cost_ratio_L512"] = d[512] / a[512]
            rec[f"{dev}_target_ms_L128"] = a[128] * 1e3
            rec[f"{dev}_draft_ms_L128"] = d[128] * 1e3
            if dev == "cpu":
                rec["agreement"], rec["agreement_tokens"] = agreement(pair, prompts)
            print(f"{tgt.split('/')[-1]} / {dr.split('/')[-1]} {dev}: ratio L128 {rec[f'{dev}_cost_ratio_L128']:.2f} "
                  f"L512 {rec[f'{dev}_cost_ratio_L512']:.2f}", flush=True)
            del pair
            gc.collect()
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
        print(f"   agreement {rec['agreement']:.3f} over {rec['agreement_tokens']} tokens", flush=True)
        rows.append(rec)
    (OUT / "pairs.json").write_text(json.dumps(rows, indent=2))
    intro = ("Draft-step cost as a fraction of a target-step (lower = more room for speculation) and draft–target "
             "agreement (`scripts/compare_pairs.py`, `results/model_selection/pairs.json`).\n")
    header = ("| Target / draft | Layers | Params (M) | Cost ratio, MPS fp16 (L=128 / 512) | Cost ratio, CPU fp32 "
              "(L=128 / 512) | Agreement (CPU fp32, 24 HumanEval prompts × 64 tokens) |")
    md = [intro, header, "|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['target'].split('/')[-1]} / {r['draft'].split('/')[-1]} | {r['target_layers']} / {r['draft_layers']} | "
                  f"{r['target_params_m']:.0f} / {r['draft_params_m']:.0f} | "
                  f"{r['mps_cost_ratio_L128']:.2f} / {r['mps_cost_ratio_L512']:.2f} | "
                  f"{r['cpu_cost_ratio_L128']:.2f} / {r['cpu_cost_ratio_L512']:.2f} | {r['agreement']:.3f} |")
    md.append("\n`Qwen/Qwen2.5-1.5B-Instruct / Qwen2.5-0.5B-Instruct` (the original plan) was attempted on an 8 GB Mac: "
              "profiling did not finish because the machine exhausted RAM and swap, so its cost ratio is "
              "**NOT MEASURED**.\n")
    (OUT / "pairs.md").write_text("\n".join(md))
    print(f"-> {OUT / 'pairs.md'}")


if __name__ == "__main__":
    main()
