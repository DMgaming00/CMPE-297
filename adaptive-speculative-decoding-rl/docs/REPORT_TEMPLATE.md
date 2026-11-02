# Assignment report template

> Fill every bracketed item from `results/<run>/REPORT.md`. Do not type numbers from memory.
> Target length: 6–8 pages including figures.

## 1. Introduction (½ page)
- The problem: LLM decoding is slow and memory-bound; speculative decoding trades cheap drafting for fewer
  expensive target passes.
- The paper's claim in one sentence: optimizing measured throughput with RL beats optimizing acceptance length.
- What you did: a $0, laptop-scale replication of the depth-policy component and the reward ablation, with an
  exact trace-replay simulator and wall-clock validation on Apple Silicon.

## 2. Background (1 page)
- Speculative decoding and the acceptance rule (cite Leviathan et al. 2023; Chen et al. 2023). Explain why it
  is lossless (`src/ltdmini/sampling.py`, tests).
- Why draft length matters: expected tokens per verify step `(1 − α^(γ+1)) / (1 − α)`; costs of drafting.
- Adaptive drafting prior work: confidence/entropy stopping (SVIP, SpecDec++), and the paper's critique.

## 3. The paper (1 page)
- RL formulation: depth and size policies, observation, binary depth action, throughput reward, PPO,
  iterative co-training. Key results and the reward ablation (see `docs/PAPER_SUMMARY.md`).

## 4. Replication design (1–1½ pages)
- Hardware: [chip, RAM, macOS], cost $0.
- Models: [target / draft], tokenizer check.
- The simulator and why it is exact for greedy decoding; the test that proves it.
- Timing model fit: [coefficients] and fit quality.
- Faithfulness table (copy from `docs/METHOD.md`) — be explicit about chain vs tree and no size policy.

## 5. Results (1½–2 pages)
- **RQ1 table:** speedup [95% CI] and τ per policy per test set (simulated).
- **RQ2 table (reward ablation):** throughput vs acceptance vs time — speedup and τ. Did acceptance reward
  give longer τ but lower speedup, as in the paper?
- **RQ3:** transfer from HumanEval to MT-Bench/GSM8K/Alpaca/NQ — where does the policy help most?
- **RQ4:** real wall-clock results; sim-vs-real figure; exact-match rate.
- Training curves figure.

## 6. Discussion (1 page)
- Does your evidence support the paper's central claim at small scale? Quantify with the paired CI.
- Why results may differ from the paper: chain vs tree drafting, Apple Silicon cost profile (verification of a
  few extra tokens is nearly free when memory-bound), small models with high acceptance, sample size.
- What the learned policy actually does: mean depth, when it stops early (plot depth vs top-1 probability).
- Threats to validity: simulator timing model, thermal throttling, small samples, single run of PPO per reward
  (report seeds if you ran several).

## 7. Conclusion and future work (½ page)
- One-paragraph verdict.
- v2: tree drafting + size policy + co-training; temperature 1; online fine-tuning.

## Appendix
- Exact commands, config files, environment (`environment.json`), git commit.
- Link to the GitHub repository.
