"""Objective evaluator and budget accounting.

The evaluator is the *fixed* ground truth for every method. Cost is measured in
**instance-evaluations** (building one tour for one instance = 1 unit), so cheap
probes, fit-split labels and full evaluations are all comparable.

Agents only ever see the ``train`` split (plus explicitly-charged probe/fit
splits). The ``test`` split is used for reporting only and is never charged.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core import candidate as cand
from src.core.candidate import Expr
from src.core.problem import SOLVED_TOL, TaskSpec, excess, make_instances


class BudgetExceeded(RuntimeError):
    """Raised when an evaluation would exceed the allotted budget."""


class Budget:
    def __init__(self, total: float) -> None:
        self.total = float(total)
        self.used = 0.0

    @property
    def remaining(self) -> float:
        return self.total - self.used

    def can_afford(self, units: float) -> bool:
        return self.used + units <= self.total + 1e-9

    def charge(self, units: float) -> None:
        if not self.can_afford(units):
            raise BudgetExceeded(f"need {units}, only {self.remaining:.1f} left")
        self.used += units


@dataclass(frozen=True)
class EvalResult:
    score: float  # -100 * mean(tour/reference - 1): higher is better
    solved: int  # instances within SOLVED_TOL of the 2-opt reference
    n: int


def score_expr(task: TaskSpec, expr: Expr, split: str, n: int | None = None) -> EvalResult:
    """Uncharged scoring primitive (used internally and for test-set reporting)."""
    instances = make_instances(task, split, n)
    ex = [excess(inst, expr) for inst in instances]
    solved = sum(1 for e in ex if e <= SOLVED_TOL)
    return EvalResult(-100.0 * sum(ex) / len(ex), solved, len(ex))


class Evaluator:
    """Charged evaluator bound to one task and one budget."""

    def __init__(self, task: TaskSpec, budget: Budget) -> None:
        self.task = task
        self.budget = budget
        self.n_train = len(make_instances(task, "train"))
        self.full_calls = 0
        self.cache_hits = 0
        self._cache: dict[str, EvalResult] = {}

    @property
    def full_cost(self) -> float:
        return float(self.n_train)

    def can_afford_full(self) -> bool:
        return self.budget.can_afford(self.full_cost)

    def evaluate(self, expr: Expr) -> EvalResult:
        """Full train-split evaluation. Memoised: re-evaluating a known program is free."""
        key = cand.to_str(expr)
        if key in self._cache:
            self.cache_hits += 1
            return self._cache[key]
        self.budget.charge(self.full_cost)
        self.full_calls += 1
        result = score_expr(self.task, expr, "train")
        self._cache[key] = result
        return result

    def evaluate_split(self, expr: Expr, split: str, n: int) -> EvalResult:
        """Charged evaluation on ``n`` instances of a non-train split (probe / fit)."""
        self.budget.charge(n)
        return score_expr(self.task, expr, split, n)
