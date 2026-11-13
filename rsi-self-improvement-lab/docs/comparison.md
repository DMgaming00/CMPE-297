# Technical comparison of the three methods

Section 10 asks for a comparison by **changed object, feedback, inheritance, evaluation and cost**. Source claims below are from the papers
(see [method-selection.md](research/method-selection.md)); "here" is what this repository implements and measured.

## Mechanism

| | Dream-RSI | Budget RSI | SO-RSI |
|---|---|---|---|
| **Changed object** | exploration policy (`SearchPolicy`: temperature, explore bonus, restart prob., batch, patience) | edit-selection scorer (ridge readout over 8 diff features + parent score) | the improver (`ImproverConfig`: edit-kind weights, step size, validation rule) |
| **Improvement operator** | rule-based reviser writes 3 revised policies (paper: an LLM agent rewrites policy code) | ridge regression on labelled edits, then *frozen* | structural interventions chosen by a diagnosed mechanism |
| **Feedback signal** | replay score on recorded trees: quality-vs-calls hypervolume − λ·rounds/call | change in score on a small fit split (label = max(gain, 0)) | anomalies in the edit trace + probe verdicts |
| **Memory / history** | pool of `DiscoveryTree`s (replay worlds) | the labelled-edit set; node archive with solved counts | `InquiryMemory` of (anomaly, probe, verdict, intervention) |
| **Selection / update rule** | argmax replay score; incumbent is a candidate (never worse on replay) | argmax predicted gain among K=8 proposals; Thompson sampling over parents | apply intervention for the diagnosed verdict; reuse remembered verdicts |
| **Inheritance** | policy of generation *g* drives the rollout that produces generation *g+1*'s trees | frozen readout drives deployment | improver config persists across episodes and into deployment |
| **Stopping / bounds** | budget, patience rule (ρ-dependent), max 3 generations | budget; fixed 96 labelled edits | budget; 3 episodes per task; clamped config |
| **Safeguards** | clamped policy parameters; incumbent always candidate | label clipping; readout frozen; train-only parent statistics | edits restricted to ImproverConfig; optional validation acceptance |

## Where each spends and saves compute

| | Dream-RSI | Budget RSI | SO-RSI |
|---|---|---|---|
| Adaptation cost | high (full online rollouts) but replays are free | very low (cheap fit split, no full rollouts) | high (episodes) plus probe cost |
| Saves | evaluator calls via early stopping and better ordering | full evaluations spent on bad edits | repeated failing edit kinds |
| Needs | enough *recorded* coverage for replay to discriminate policies | edit features that predict value | failures with diagnosable structure |
| Best use | long, expensive discovery where cost dominates | any proposal-heavy search with a cheap proxy | agents that thrash on repeated fixes |
| Weakness | cannot evaluate unseen branches; sensitive to the history-generating policy | frozen scorer can be wrong off-distribution; favours safe edits if mislabelled | probes cost budget and the diagnosis can be wrong |

## Measured comparison (this repository)

Mean over **<!-- TABLE:npairs -->60<!-- /TABLE:npairs --> paired runs** (30 seeds × 2 held-out tasks). Scores are on the hidden test split; higher is better.

<!-- TABLE:paired -->
| RSI method minus ... | Fixed tree search | AIDE-style tree | Fixed tree, +adaptation budget |
|---|---:|---:|---:|
| **Dream-RSI** | -0.24 [-1.39, +0.97] | -1.67 [-2.79, -0.65] | -2.22 [-3.31, -1.23] |
| **Budget RSI** | +1.94 [+0.89, +2.94] | +0.51 [-0.41, +1.39] | -0.04 [-0.93, +0.84] |
| **SO-RSI** | +0.99 [-0.06, +2.06] | -0.44 [-1.48, +0.54] | -0.99 [-1.88, -0.12] |
<!-- /TABLE:paired -->

Budget needed to match the fixed tree search's final train score:

<!-- TABLE:match -->
| Method | Runs that reach it | Median deployment units | Median incl. amortised adaptation |
|---|---:|---:|---:|
| Random search | 18% | 156 | 156 |
| Hill-climb (fixed) | 65% | 204 | 204 |
| AIDE-style tree (fixed) | 78% | 228 | 228 |
| Fixed tree search (Dream-RSI's start policy) | 55% | 420 | 420 |
| Hill-climb, +adaptation budget | 85% | 276 | 276 |
| Fixed tree, +adaptation budget | 78% | 456 | 456 |
| **Dream-RSI** | 45% | 228 | 1284 |
| **Budget RSI** | 75% | 204 | 402 |
| **SO-RSI** | 63% | 243 | 1202 |
<!-- /TABLE:match -->

### Reading the numbers
* **Budget RSI** is the only RSI method that clearly beats the fixed tree search at equal deployment budget, and it does so with ~5× less adaptation than the others.
  Against the stronger fixed baselines the margin disappears: it is **statistically indistinguishable** from the AIDE-style tree and from the fixed tree given 2.5× the evaluations.
  **Most of its gain is not from the learned readout.** `budget_no_screen` (Thompson-sampled parents, one proposal, no readout) already beats the fixed tree by about +1.2; screening adds a further ≈+0.7 whose CI touches 0.
  The readout's rank correlation with held-out labels averages **−0.00** over 30 seeds (range −0.20 to +0.27): it is not a validated predictor here, so the small residual gain should not be credited to prediction.
* **Dream-RSI** did **not** beat its own starting policy (paired difference's CI spans 0) and is clearly worse than the simple AIDE-style greedy policy. Its learned policy does stop earlier (≈617 of 720 units used; median 228 units to match vs 420 for the fixed tree) but reaches the target in fewer runs (45% vs 55%).
* **SO-RSI** is slightly better than the fixed tree search but **not better than** its first-order counterpart `naive_rsi` or the plain hill-climb. In this toy the probes cost budget and the interventions did not pay for it. Its most common diagnosis was real (overfitting to the 12 train instances was diagnosed in 21 of 30 runs; see the train/test gap in [limitations](limitations.md)), but requiring validation-split agreement did not improve held-out scores.
* The most robust finding is about **baselines**: a good fixed search policy (hill-climb, AIDE-style) beats Dream-RSI's naive starting policy by more than any RSI method's improvement over it. A claim of "RSI helps" is only meaningful against a strong fixed baseline.

## Ablations (full experiment)

<!-- TABLE:ablation -->
| Variant | Final test score | Ablation minus full method, paired [95% CI] |
|---|---:|---:|
| **dream_rsi** (full method) | -8.41 | - |
| &nbsp;&nbsp;`dream_no_replay`: accept a random revised policy (no replay evidence) | -8.27 | +0.14 [-0.95, +1.25] |
| &nbsp;&nbsp;`dream_no_evolution`: never revise the policy (collect trees only) | -7.77 | +0.64 [-0.54, +1.91] |
| **budget_rsi** (full method) | -6.24 | - |
| &nbsp;&nbsp;`budget_parent_only`: readout sees parent score only (the paper's own ablation) | -7.11 | -0.87 [-1.78, +0.07] |
| &nbsp;&nbsp;`budget_no_screen`: no screening: K=1 proposal, evaluate it | -6.96 | -0.72 [-1.51, +0.04] |
| **so_rsi** (full method) | -7.18 | - |
| &nbsp;&nbsp;`naive_rsi`: first-order RSI: reward-following edit weights, no diagnosis | -6.36 | +0.82 [-0.08, +1.71] |
| &nbsp;&nbsp;`so_no_probes`: anomalies detected, default reflex instead of probes | -6.49 | +0.69 [+0.02, +1.47] |
| &nbsp;&nbsp;`so_no_memory`: improver reset each episode (no inquiry memory) | -6.78 | +0.40 [-0.24, +1.09] |
<!-- /TABLE:ablation -->

Interpretation is in the [README](../README.md#ablation-study).
