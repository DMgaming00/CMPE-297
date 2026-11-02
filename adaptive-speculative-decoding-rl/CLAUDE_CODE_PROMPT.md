# Prompt for Claude Code

Paste everything below the line into Claude Code, opened in this repository on your Mac.

---

You are my ML-systems research engineer. This repository, **LTD-Mini**, is a laptop-scale, zero-cost
replication of *Learning to Draft: Adaptive Speculative Decoding with Reinforcement Learning* (Zhang et al.,
ICLR 2026, arXiv:2603.01639). It is my course assignment and will be public on GitHub, so it must be correct,
reproducible and honest. Read `README.md`, `docs/PAPER_SUMMARY.md`, `docs/METHOD.md` and
`docs/EXPERIMENTS.md` fully before doing anything.

## Ground rules (non-negotiable)

1. **Never invent or estimate results.** Every number in README, docs or my report must come from a file in
   `results/` produced by a run in this repo. Unmeasured → write "NOT YET MEASURED".
2. **Correctness before speed.** Speculative decoding must reproduce the target's greedy output (100% in fp32
   on CPU; report the match rate in fp16 on MPS and explain any gap).
3. **$0 budget.** Local Apple Silicon only (MPS or CPU). No paid APIs, no paid GPUs. Free Hugging Face models
   and datasets only.
4. **No silent scope changes.** Ask me before changing models, research questions, splits or the faithfulness
   table in `docs/METHOD.md`.
5. **Small, reviewable steps.** After each phase, stop and report: what you ran (exact commands), what passed
   or failed, artifact paths, and what's next. Commit at each phase boundary with a clear message.
6. **Explain as you go.** This is an assignment I must defend. For any non-obvious code you change, tell me why
   in plain words.

## Context: what already exists

- NumPy core (tested): `sampling.py` (greedy + lossless stochastic acceptance), `features.py`, `timing.py`,
  `traces.py`, `sim.py` (exact trace-replay simulator), `policies.py` (fixed / confidence / entropy /
  cumulative baselines + exported MLP), `tune.py`, `stats.py`, `evaluate.py`, `report.py`.
- PyTorch code (written, **not yet run on a real machine**): `device.py`, `models.py`, `specdec.py`
  (autoregressive + chain speculative decoding with KV-cache rollback via `DynamicCache.crop`), `profile.py`,
  `build_traces.py`, `real_eval.py`.
- Training (written, **not yet run**): `gym_env.py`, `train.py` (Stable-Baselines3 PPO, export to NumPy).
- Tests: `tests/unit` (25 passing), `tests/torch` (written, not yet run).

## Phase 1 — Environment and tests

1. Create a venv with `uv` or `python -m venv`, then `pip install -e ".[all]"`. Record versions.
2. `pytest tests/unit -q` → must pass.
3. `pytest tests/torch -q` → these exercise the real decoder with tiny random models on CPU. Fix any failure
   at its root (likely candidates: `DynamicCache` API differences across transformers versions, `crop`
   semantics, `apply_chat_template` return types). Never weaken an assertion to make a test pass; if you believe
   a test is wrong, explain why and ask me first.
4. Add a test that runs `speculative_greedy` on MPS (if available) with a tiny model in fp16 and reports the
   token-match rate (no hard equality assertion on MPS).
5. Run `ruff check src tests`.

## Phase 2 — Smoke pipeline

1. `ltdmini all --config configs/smoke.yaml` (random tiny models, no download). Every stage must complete and
   `results/smoke/REPORT.md` must render. These numbers are not results.
2. `ltdmini synthetic-demo` with `--train-steps 20000` to confirm PPO trains and exports.

## Phase 3 — Fast real run (SmolLM2 360M / 135M)

1. `ltdmini profile --config configs/tiny.yaml`; show me the fitted timing model and the raw measurements, and
   check the fit is sensible (verify cost should grow slowly with k; draft step much cheaper than target step).
   If the draft is not meaningfully cheaper than the target on this Mac, stop and tell me.
2. `ltdmini traces`, `tune`, `train --reward all`, `eval-sim`, `eval-real --n-prompts 8`, `report`.
3. Summarize: does the throughput policy beat the best tuned baseline (paired CI)? Did the reward ablation
   reproduce the paper's ordering (throughput > acceptance > time) and the "longer τ, lower speedup" effect for
   the acceptance reward? How close are simulated and real speedups?

## Phase 4 — Main run (Qwen2.5 1.5B / 0.5B)

Same as Phase 3 with `configs/mac.yaml`. Before starting, estimate runtime from Phase 3 measurements and tell
me; run trace building in the background with logging and resumability (add a resume-from-partial feature to
`build_traces` if it isn't there — save per-prompt and skip completed ones).

## Phase 5 — Robustness (what makes it A+)

1. **Seeds:** train each reward with 3 PPO seeds; report mean ± spread of test speedup.
2. **Ablations:** (a) remove history features from the observation; (b) no timing noise in training;
   (c) dmax 8 vs 12. Report each with CIs.
3. **Policy behaviour:** plot chosen depth vs draft top-1 probability for the learned policy vs baselines.
4. **Sim-to-real:** run `eval-real` twice (different times) and report variance; explain any sim/real gap.

## Phase 6 — Write-up

1. Fill `docs/RESULTS.md` from `results/*/REPORT.md` (tables + figures + one-paragraph interpretation each).
2. Update the README "Results" section with the headline numbers and links to the run folders.
3. Draft my report in `report/report.md` following `docs/REPORT_TEMPLATE.md`. Use only measured numbers.
   Mark anything uncertain. Keep a "Threats to validity" section.
4. Final checks: fresh clone → `pip install -e ".[all]"` → `pytest` → `ltdmini all --config configs/smoke.yaml`
   works end to end; README commands are all correct; no large files committed (traces stay out of git unless
   small; add them to a GitHub Release if needed).

## Optional Phase 7 — Extensions (ask me first)

- Tree drafting with a 4D attention mask + a size policy + alternating co-training (paper Sec. 4.3).
- Temperature 1 using the stochastic acceptance in `sampling.py` (simulator samples outcomes).
- Short online PPO fine-tuning against real decoding.

Start with Phase 1 now. Do not start Phase 3 before Phases 1–2 are green and I have approved.
