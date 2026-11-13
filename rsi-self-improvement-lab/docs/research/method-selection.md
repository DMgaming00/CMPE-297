# Method selection

This document records what was inspected, what was verified, and why Dream-RSI, Budget RSI and SO-RSI were
chosen. Research was done on **2026-11-12**. Everything marked *verified* was read directly from the arXiv
abstract/HTML page or the course repository; everything marked *not verified* is stated as such.

## 1. What the assignment actually points at

The brief refers to `rsi/COURSE-MAP.md`. In the course repository
([dlmastery/simple-coding-harness](https://github.com/dlmastery/simple-coding-harness), cloned at commit
`fabd4c7`, dated 2026-10-26) that path does not exist. The map is the root-level `COURSE-MAP.md`, and **Section 10 is
"Read and Rebuild October 2026 Research"**: 6 groups, 17 labs (10.01–10.17).

| Group | Labs | Paper focus (per the course map) |
|---|---|---|
| Read a frontier claim | 10.01–10.02 | Which claim does the evidence support? |
| Budget RSI | 10.03–10.05 | Score code edits before full evaluation |
| Second-order diagnostics (SO-RSI) | 10.06–10.08 | Why do failures occur before patching? |
| Scaling / coordination (AReaL-RSI, SwarmRSI) | 10.09–10.11 | Multi-agent coordination |
| Adaptive workflows (RSIFlow, Self-HPO) | 10.12–10.14 | Workflows that adapt to bottlenecks |
| Environments & metrics (RSIGym) | 10.15–10.17 | RSI-Index, tracks |

The course map states that Budget RSI and SO-RSI have **full laptop demos** (`12_october_2026_papers/01_budget_rsi/demo.py`,
`02_second_order_rsi/demo.py`) and the rest are partial or mechanism-only. Section 10's "ready to continue when" criterion is:

> Compare October 2026 RSI systems by their **changed object, feedback, inheritance, evaluation, and cost**. Distinguish a
> source claim from your laptop adaptation and its observed result.

That criterion drives the repository: every method is described by those five attributes
([comparison.md](../comparison.md)), and every README separates source claims from what *this* repository measured.

Dream-RSI, AIDE² and the "Scientist" systems named by the instructor are not in the current map's Section 10, but they appear
in the course's authoring notes (`how-did-i-generate-it/rsi/RSI-MASTERCLASS-PLAN.md`), which lists labs
"Dream-RSI: discovery trees / replay / return online (*test the selected policy on new work and account for total cost*)",
"AIDE²: inner/outer research" and "ScientistTwo". The Dream-RSI lab sequence in that plan is exactly the loop implemented here.

## 2. Candidates investigated

| Method | Source | Date | Verified? | Recursively improved component | Laptop-reproducible core? |
|---|---|---|---|---|---|
| **Dream-RSI** | [arXiv 2609.14858](https://arxiv.org/abs/2609.14858), Zheng et al.; official repo [zhengkid/Dream-RSI](https://github.com/zhengkid/Dream-RSI) (found by search; code not inspected) | 2026-09-14 | Paper text read | Exploration policy (which nodes to expand, parallelism, stopping) | **Yes** – replay over recorded trees needs no LLM |
| **Budget RSI** | [arXiv 2610.29121](https://arxiv.org/abs/2610.29121), Darzi, Balija, He | 2026-10-21 | Abstract read | Edit *selection* scorer (frozen linear readout) | **Yes** – ridge regression + Thompson sampling |
| **SO-RSI** | [arXiv 2610.05701](https://arxiv.org/abs/2610.05701), Jiang, Vempaty, Jagmohan | 2026-10-05 (v2 10-06) | Abstract read | The improver's *edit procedure*, driven by diagnosed failure mechanisms | **Yes** – trace anomaly detectors + probes |
| AIDE | [arXiv 2502.13138](https://arxiv.org/abs/2502.13138), Weco AI; [WecoAI/aideml](https://github.com/WecoAI/aideml) | 2025-02-18 | Search results | Nothing recursive: tree search over code with a fixed policy | Yes – used here as the **non-RSI baseline** |
| AIDE² | [arXiv 2609.26457](https://arxiv.org/abs/2609.26457), Weco AI | 2026-09-22 (a secondary blog gives 2026-07-14; unresolved) | Search summary only | An inner research agent, rewritten by an outer loop and accepted only on held-out data | **No** – the central step is an LLM rewriting agent code over an 8-day run |
| "Scientist2" | No paper by that name found. Closest: [AI Scientist-v2, arXiv 2504.08066](https://arxiv.org/abs/2504.08066), Sakana AI, [repo](https://github.com/SakanaAI/AI-Scientist-v2) | 2025-04-10 | Search results | Not RSI: agentic tree search to produce papers | No – end-to-end paper pipeline |
| AReaL-RSI, RSIFlow, RSIGym, Self-HPO, Terminal-RSI, R2Orch, SwarmRSI | arXiv 2610.18083, 2610.21791, 2610.10310, 2610.22791, 2610.22192, 2610.22740, 2610.20431 | Oct 2026 | **Not independently verified** – taken from the course's `PAPER_SUMMARIES.md` | Various (team coordination, workflow graph, harness+policy RL, ...) | The course itself marks these partial or mechanism-only; several need RL training |

## 3. The three selected methods

### Dream-RSI – improve the *search policy* from replayed history
- **Core algorithm (paper):** online exploration records a *discovery tree* (each node = an attempt, its score and workspace).
  Completed trees become *replay worlds*: a candidate policy is run against a tree that reveals recorded children as the policy
  expands nodes, with no new agent or evaluator calls. A policy-development agent writes revised policy code; every version is replayed over all
  trees at several budget preferences ρ; the version with the best quality-vs-calls hypervolume (minus a parallelism penalty) is
  deployed. The current policy is always a candidate, so selection cannot lower average replay score.
- **Strengths:** improves the *process*, not the model; offline policy comparison is free; directly yields cost reductions.
- **Limitations (stated in the paper):** replay can only reach recorded outcomes; the paper's harness experiment omitted a fixed-policy baseline for cost reasons.
- **Difficulty here:** medium. The central mechanism is fully implementable; the LLM policy-writer is replaced by a rule-based reviser.
- **Why selected:** it is the instructor's first named example, appears in the course authoring plan, and its replay idea is the clearest
  demonstration that *the harness* – not the model – is what improves.

### Budget RSI – improve *which edit gets evaluated*
- **Core algorithm (paper):** fit a linear readout on a small set of labelled scaffold edits (96 edits, four evaluations each on a 16-instance fit split) predicting edit quality from the parent's solve rate and eight diff features;
  freeze it; choose parents by Thompson sampling over steering-split counts (Huxley–Gödel-Machine style).
- **Reported (not reproduced here):** GPT-4o 87.0% vs 84.2% for the parent-rate-only ablation on held-out HumanEval+.
- **Strengths:** very cheap; explicit ablation (parent-rate-only) built into the method.
- **Limitations:** the readout is frozen and fit on one distribution of edits; predictive power may not transfer.
- **Difficulty here:** low–medium.
- **Why selected:** it is one of the two Section 10 methods with a full laptop demo, and it is the budget-accounting counterpoint to Dream-RSI.

### SO-RSI – improve the *improver* by diagnosing failures first
- **Core algorithm (paper):** monitor traces for three structural anomalies – recurrence, opposing edits, expectation mismatch; on detection, run
  lightweight diagnostic probes, store causal evidence in persistent inquiry memory, and apply structural (not parameter) edits.
- **Reported (not reproduced here):** +21.8 (Lean 4) and +25.8 (Verus) held-out points over naive RSI under matched 24-hour budgets.
- **Strengths:** targets thrashing; explicitly second-order.
- **Limitations:** needs a task where failures have diagnosable mechanisms; probes cost budget.
- **Difficulty here:** medium (anomaly detectors, probes, memory, interventions on a *bounded* improver config).
- **Why selected:** the other Section 10 method with a full laptop demo, and the only one of the three whose changed object is the *improver itself* – the closest of the three to the course's Section 09 definition of recursion.

### Why these three together
They change three different objects, so they are not "the same loop renamed":

| Method | Changed object | Feedback used |
|---|---|---|
| Dream-RSI | exploration policy | recorded outcomes replayed offline |
| Budget RSI | edit-selection scorer | labelled edit outcomes on a cheap split |
| SO-RSI | improver's edit procedure | diagnosed failure mechanisms from probes |

AIDE (v1) is included as the strongest relevant *non-RSI* baseline: it is a fixed tree-search policy, which is exactly what Dream-RSI tries to improve.
AIDE² and the Scientist systems were rejected because their central mechanism depends on an LLM rewriting large pieces of agent code over days of compute, which cannot be reproduced honestly offline.
This repository claims **educational minimal reproductions of the central mechanisms**, not reproductions of the papers' systems, models or benchmarks.
