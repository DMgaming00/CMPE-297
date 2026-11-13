# Experimental methodology and fairness

## Question
Do three recent RSI mechanisms improve the *process* that discovers good programs, as measured on tasks they were never adapted to, at a stated cost?

## Problem and protocol
* **Task family.** Greedy TSP construction: a program scores each unvisited city from five features (`d_cur`, `d_start`, `d_cent`, `d_iso`, `t`); the best-scoring city is visited next. Seed = Nearest-Neighbour.
* **Objective.** `score = -100 × mean(tour_length / reference_length − 1)`. The reference is a 2-opt local optimum (not the true optimum, so scores are relative to a strong heuristic, not to optimality).
* **Instances.** 30 cities. 12 train instances per task (what the agent sees), 30 test instances (never queried by agents).
* **Tasks.** Adaptation (RSI methods only): `uniform`, `clusters`, `ring`. Deployment, for every method: held-out `clusters_tight` and `grid_jitter`. Layout distributions differ, so the claim is transfer of the *improved procedure*, not of one good program.
* **Seeds.** 30 seeds (0–29) × 2 held-out tasks = 60 paired runs per method. Dev seeds 100+ were used for the single tuning decision described below.

## What is held constant
| Factor | Control |
|---|---|
| Initial solution | Nearest-Neighbour for everyone |
| Evaluator | one `Evaluator`, one scoring function |
| Deployment budget | 60 full evaluations = 720 units per held-out task |
| Proposer | the same `MutationProposer` (an offline stand-in for an LLM) |
| Seeds / tasks | identical, so comparisons are **paired** |
| Selection signal | train split only; reporting on the hidden test split |

## What differs, and how cost is counted
RSI methods spend budget *before* deployment (adaptation). That cost is reported separately and never hidden:

| Method | Adaptation cost (units, mean) | What it buys |
|---|---|---|
| Dream-RSI | ≈1 980 (3 online rollouts; every replay is free) | revised policy |
| Budget RSI | 396 (96 labelled edits × 4 fit instances + seeds) | frozen readout |
| SO-RSI | ≈1 910 (9 episodes + probes) | revised improver config |

To keep the comparison honest there are **budget-matched controls**: `hill_climb_matched` and `fixed_tree_matched` get the *entire* adaptation allowance (3 × 60 evaluations) added to their deployment budget, split across the 2 held-out tasks (150 evaluations each instead of 60). This favours the baselines: RSI adaptation is amortised across tasks in principle, but the matched controls pay it per task.

## Baselines
1. **Initial solution** – no search.
2. **Random search** – independent random programs; no use of history.
3. **Hill-climb** – (1+1) with a fixed improver.
4. **AIDE-style tree** – greedy best-first with occasional fresh drafts (the best relevant non-RSI baseline; AIDE's own search policy, not its LLM).
5. **Fixed tree search** – tree search under Dream-RSI's *starting* policy: the exact ablation "never revise the policy".
6. **Matched-budget** versions of 3 and 5.

## Statistics
* Paired differences (same seed, same held-out task) with 95% percentile bootstrap CIs (2 000 resamples) over the 60 pairs. Pairs from the same seed share a random stream partly (adaptation), so CIs are **somewhat optimistic**; treat borderline intervals as inconclusive.
* **Success** = a run improves its test score by ≥ 1.0 point over the initial solution.
* **Cost-to-match** = budget at which a method first reaches the fixed tree search's final *train* score on the same seed and task.

## Integrity measures
* Test instances are only touched by `score_expr(..., "test")` inside `protocol.to_rows`; unit tests pin the budget cap for every method.
* A regression test pins the initial-solution score so evaluator or generator drift is noticed.
* **Disclosed tuning.** The first version of Budget RSI labelled edits with the *signed* score change; it chose harmless no-op edits and hurt deployment (observed on seeds 0–5, which overlap the reporting seeds). The label was changed to expected improvement `max(gain, 0)` and the change was then confirmed on dev seeds 100–109 (screening −6.97 vs no screening −9.29, before the final run). No other method was tuned after seeing results. Dream-RSI and SO-RSI were run as first implemented; a dev-seed check of Dream-RSI showed no benefit and was not tuned further.
* All numbers in the README are generated from `experiments/results/` by `scripts/render_docs.py`.
