# Experiment protocol

## Splits (no leakage)

| Split | Prompts | Used for |
|---|---|---|
| train | HumanEval slice A | PPO training only |
| val | HumanEval slice B (disjoint from A) | Baseline grid search and PPO checkpoint selection |
| test | MT-Bench, GSM8K, Alpaca, Natural Questions | Final simulated and real evaluation — never used for any choice |

## Order of operations

1. `profile` — measure step times on the device (warm-up runs excluded, median of 15 repeats, 3 context lengths).
2. `traces` — build train/val/test traces with the real models.
3. `tune` — grid-search every baseline family on **val**; keep the best of each.
4. `train --reward all` — PPO with throughput, acceptance and time rewards; keep the best **val** checkpoint.
5. `eval-sim` — all tuned baselines and learned policies on **test** traces; 3 timing-noise seeds; 95%
   bootstrap CIs over prompts; paired comparison against the best fixed depth.
6. `eval-real` — wall clock on a subset of held-out prompts: autoregressive vs each policy, interleaved order,
   synchronized timers, output equality checked.
7. `robust` — retrain every reward with 3 PPO seeds and run the three ablations (no history features, no timing
   noise in training, dmax 8 instead of 12); all evaluated on the same test traces. Resumable.
8. `behaviour` — replay the test traces and log every continue/stop decision (depth vs draft confidence).
9. `eval-real --tag _runN` — repeat the wall-clock evaluation at different times; plus one run on CPU in fp32
   (`configs/small_cpu_fp32.yaml --policies-from results/gpt2m-distilgpt2`) to check exact output equality.
10. `report` — regenerate tables and figures from the files above.

Model-pair selection (`scripts/compare_pairs.py`) is a separate, earlier experiment on HumanEval prompts that are
disjoint from train, val and test.

## Reporting rules

- Every number in `README.md` and the assignment report must come from a file in `results/`.
- Report speedup **with its 95% CI** and the number of prompts.
- Report τ (mean tokens per cycle) next to speedup — the paper's point is that they can disagree.
- Report real-decoding **exact output match** rates; fp16 on MPS can flip near-ties, so a rate slightly below
  100% is expected and should be explained, not hidden. fp32 on CPU must be 100% (tested).
- Close the laptop lid? No. Plug in power, close other apps, and note thermal state; run `eval-real` twice and
  report both if they differ.

## Expected runtime and cost (Apple Silicon, $0)

| Config | Models | Rough time | Memory |
|---|---|---|---|
| `smoke` | random tiny (no download) | ~20 s | < 1 GB |
| `small` (**used for all results**) | GPT-2 medium / DistilGPT-2 | profile ~1 min; traces ~75 min (244 prompts at ~18 s); PPO 3 rewards ~3 min; robustness ~20 min; eval-real ~10 min per run | < 2 GB |
| `tiny` | SmolLM2-360M / 135M | not used: draft step only ~0.58× target step on MPS | ~2 GB |
| `mac` | Qwen2.5-1.5B / 0.5B | not used: profiling exhausted RAM + swap on an 8 GB Mac | > 8 GB in practice |

Trace building dominates (N positions × dmax draft steps). Reduce `n_train` or `max_new_tokens` if needed.
PPO training in the simulator takes about a minute per reward on CPU (300k steps).
