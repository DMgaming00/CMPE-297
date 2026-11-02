# Paper summary: *Learning to Draft* (ICLR 2026)

**Citation.** Jiebin Zhang, Zhenghan Yu, Liang Wang, Nan Yang, Eugene J. Yu, Zheng Li, Yifan Song, Dawei Zhu,
Xingxing Zhang, Furu Wei, Sujian Li. *Learning to Draft: Adaptive Speculative Decoding with Reinforcement
Learning.* ICLR 2026. [arXiv:2603.01639](https://arxiv.org/abs/2603.01639) ·
[PDF](https://arxiv.org/pdf/2603.01639) · [official code](https://github.com/zhzihao/Learning-to-Draft)

## The problem

Speculative decoding speeds up LLM inference: a small **draft** model proposes several tokens, and the large
**target** model checks them all in one forward pass. Output quality is unchanged (the acceptance rule preserves
the target's distribution). How much speed you gain depends on a trade-off:

- **Draft longer** → more tokens can be accepted per expensive target pass, but drafting costs time and
  late drafts are often rejected.
- **Verify more candidates** (with tree drafting) → higher chance some branch is accepted, but a bigger
  verification pass.

Most systems fix these settings. Recent "dynamic" methods adapt them, but optimize **proxies** — usually
the *acceptance length* — and ignore the actual *time* each choice costs.

## The idea

Optimize what you actually care about: **throughput**. The paper frames draft-and-verify as a reinforcement
learning problem and trains two small MLP policies with **PPO** (Stable-Baselines3):

| Policy | Decides | Observes |
|---|---|---|
| **Depth policy** | After each draft forward pass: keep drafting or stop (binary) | Draft probabilities at the tree's last layer, current depth D, context length L |
| **Size policy** | How many tree candidates to verify (20–240) | The full state: depth, length, probabilities of all draft-tree tokens |

**Reward per cycle:** accepted tokens ÷ (draft time + verify time) — measured throughput.

**Training:** on HumanEval. Each policy is first trained alone with the other following a fixed heuristic
(size policy 100K steps; depth policy 1M steps), then the two are trained **alternately** for about two
rounds so they co-adapt. Checkpoints are chosen by validation speedup.

## Results (from the paper)

- Speedups of **2.24×–4.32×** over autoregressive decoding across five models (Llama-3.1-8B, Vicuna-13B,
  DeepSeek-R1-Distill-Llama-8B, Qwen3-14B, Qwen3-32B) and four benchmarks (MT-Bench, GSM8K, Alpaca,
  Natural Questions).
- Up to **36.4%** faster than the Eagle3 baseline (Qwen3-32B). Against a grid-searched Eagle3 the gains on
  Llama/Vicuna are smaller (~2–3%), larger on DeepSeek (~9%) and Qwen3-32B.
- At temperature 1 it keeps the best average speedup (~5% gain), even though it was trained only with greedy
  decoding.
- **Reward ablation (Vicuna-13B):** throughput reward → 4.13× (τ 6.84); acceptance-length reward → 3.59×
  despite the *highest* τ (6.89); time-cost reward → 3.45×. Optimizing acceptance length is the wrong goal.
- **Component ablation:** the **depth policy contributes most**; the size policy helps less; iterative
  co-training beats a naive combination.
- LTD does not always produce the longest acceptance length — it trades acceptance for time.

## What makes it interesting to replicate

The central claim is about *objectives*: a policy trained on measured time beats one trained on acceptance
length, even though acceptance length is what most work optimizes. That claim does not depend on model size or
on Eagle3 — it should show up on any hardware where draft and verify costs differ. Testing it on a laptop is a
genuine, falsifiable experiment.
