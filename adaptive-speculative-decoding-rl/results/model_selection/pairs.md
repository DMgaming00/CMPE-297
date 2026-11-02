Draft-step cost as a fraction of a target-step (lower = more room for speculation) and draft–target agreement (`scripts/compare_pairs.py`, `results/model_selection/pairs.json`).

| Target / draft | Layers | Params (M) | Cost ratio, MPS fp16 (L=128 / 512) | Cost ratio, CPU fp32 (L=128 / 512) | Agreement (CPU fp32, 24 HumanEval prompts × 64 tokens) |
|---|---|---|---|---|---|
| SmolLM2-360M-Instruct / SmolLM2-135M-Instruct | 32 / 30 | 362 / 135 | 0.56 / 0.59 | 0.54 / 0.42 | 0.932 |
| pythia-410m / pythia-70m | 24 / 6 | 405 / 70 | 0.18 / 0.18 | 0.15 / 0.13 | 0.783 |
| pythia-410m / pythia-160m | 24 / 12 | 405 / 162 | 0.42 / 0.48 | 0.38 / 0.32 | 0.858 |
| gpt2-medium / distilgpt2 | 24 / 6 | 355 / 82 | 0.24 / 0.20 | 0.23 / 0.16 | 0.809 |

`Qwen/Qwen2.5-1.5B-Instruct / Qwen2.5-0.5B-Instruct` (the original plan) was attempted on an 8 GB Mac: profiling did not finish because the machine exhausted RAM and swap, so its cost ratio is **NOT MEASURED**.
