# Limitations

This repository is a bounded educational study. It does not oversell its conclusions.

## What this is not
* **Not a reproduction of the papers.** Each method is a minimal reproduction of its *central mechanism* on a small problem. No claim is made about the papers' benchmarks, models or headline numbers (e.g. 87.0% HumanEval+, +21.8 points on Lean 4, Terminal-Bench gains).
* **No LLM in any measured result.** The proposer is a seeded mutation operator, not a language model. The LLM proposer path (`src/agents/llm.py`) exists but was never used to produce a reported number; it was not exercised against the live API.
* **The "policy-development agent" in Dream-RSI is rule-based.** The paper's agent rewrites policy *code*. Ours edits five numeric parameters from simple history statistics, so the policy space is small.
* **Replay worlds are tiny.** Three trees of ≈60 nodes, versus the paper's long discovery runs. The paper itself notes replay cannot reach unrecorded branches; here that limit bites hard because the history-generating policy is nearly uniform.

## Problem-level limits
* One problem family (greedy TSP construction, 30 cities). Results may not transfer to code optimisation, proof search, or kernel tuning.
* The reference is a 2-opt local optimum, not optimal tours. "Improvement" means relative to that heuristic.
* Train/test gap is real: the best train program is worse on the hidden test split by ≈1.2–2.0 points on average, and in 6–14 of 60 runs the discovered program is *worse than the initial solution on test* even though it beat it on train (see codelab 09).
* The DSL is small (7 operators, 5 features) and the problem is low-dimensional; evaluations are cheap (~1 ms/instance), so "cost" is a proxy, not dollars.

## Statistical limits
* 60 paired runs; effects below ≈1 point are within noise. CIs are bootstrap intervals over pairs that share seeds across tasks, so they are somewhat optimistic.
* Many comparisons are reported (no multiplicity correction). Borderline findings (for example `so_no_probes` vs SO-RSI, CI lower bound +0.02) should be treated as suggestive.
* One implementation decision (Budget RSI's label definition) was made after looking at results on seeds that overlap the reporting seeds; it was then confirmed on separate dev seeds. See [methodology.md](methodology.md).
* The Dream-RSI and SO-RSI implementations were **not** tuned to make them look better. A different design (a richer policy class, larger replay pool, an LLM reviser) might change their ranking; this study cannot say.

* **Budget RSI's learned component is weak here.** Held-out rank correlation of the readout is ≈0 on average, so the experiment does not support 'a frozen linear readout predicts edit value' on this problem. The method's measured advantage is mostly attributable to Thompson-sampling parent selection.

## Conceptual limits
* **Bounded, shallow recursion.** Three generations of adaptation on three tasks. This does not test open-ended or accelerating self-improvement.
* **The recursion is weak in the Section 09 sense.** We show that a revised procedure was *inherited and used*; we do not show that a revised improver generates *better improvers* (no I0→I1→I2 improvement trend was measured).
* **Frozen components.** The proposer, evaluator and DSL never change, so no result speaks to improving the model or the evaluator.
