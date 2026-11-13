"""The shared problem: discovering greedy construction heuristics for the Euclidean TSP.

A tour is built one city at a time: at every step a *priority expression* (see
:mod:`src.core.candidate`) scores each unvisited city from five features, and the
highest-scoring city is visited next. Nearest-Neighbour is the expression
``-d_cur``; the search space is every richer expression the DSL can write.

Quality on an instance is ``tour_length / reference_length - 1`` where the
reference is a 2-opt local optimum (computed once per instance, never visible to
agents as a program). Lower is better; the reported *score* is its negated
percentage so that higher is better.

A *task* is a family of instances (a city-layout distribution). All three RSI
methods and all baselines attack the same tasks with the same evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property, lru_cache

import numpy as np

from src.core import candidate as cand
from src.core.candidate import Expr

SPLITS = {"train": 0, "test": 1, "probe": 2, "fit": 3}
SOLVED_TOL = 0.12  # an instance counts as "solved" if within 12% of the 2-opt reference


@dataclass(frozen=True)
class TaskSpec:
    """Immutable description of an instance family."""

    name: str
    kind: str  # "uniform" | "clusters" | "ring" | "grid"
    n_cities: int = 30
    n_clusters: int = 3
    spread: float = 0.08
    n_train: int = 12
    n_test: int = 30
    seed: int = 0


@dataclass(frozen=True, eq=False)
class Instance:
    coords: np.ndarray  # (n, 2)

    @cached_property
    def dist(self) -> np.ndarray:
        diff = self.coords[:, None, :] - self.coords[None, :, :]
        return np.sqrt((diff**2).sum(-1))

    @cached_property
    def reference_length(self) -> float:
        return tour_length(self, two_opt(self, nn_tour(self)))

    @cached_property
    def nn_length(self) -> float:
        return tour_length(self, nn_tour(self))


def _draw_coords(spec: TaskSpec, rng: np.random.Generator) -> np.ndarray:
    n = spec.n_cities
    if spec.kind == "uniform":
        pts = rng.random((n, 2))
    elif spec.kind == "clusters":
        centres = rng.random((spec.n_clusters, 2)) * 0.8 + 0.1
        which = rng.integers(0, spec.n_clusters, size=n)
        pts = centres[which] + rng.normal(0, spec.spread, size=(n, 2))
    elif spec.kind == "ring":
        ang = rng.random(n) * 2 * np.pi
        rad = 0.4 + rng.normal(0, spec.spread / 2, size=n)
        pts = 0.5 + np.stack([rad * np.cos(ang), rad * np.sin(ang)], axis=1)
    elif spec.kind == "grid":
        side = int(np.ceil(np.sqrt(n)))
        cells = rng.permutation(side * side)[:n]
        pts = np.stack([cells % side, cells // side], axis=1) / max(side - 1, 1)
        pts = pts * 0.9 + 0.05 + rng.normal(0, spec.spread / 4, size=(n, 2))
    else:
        raise ValueError(f"unknown task kind {spec.kind!r}")
    return np.clip(pts, 0.0, 1.0)


@lru_cache(maxsize=256)
def make_instances(spec: TaskSpec, split: str, n: int | None = None) -> tuple[Instance, ...]:
    """Deterministically generate the instances of ``spec`` for a split."""
    if n is None:
        n = spec.n_test if split == "test" else spec.n_train
    rng = np.random.default_rng([spec.seed, SPLITS[split], 12345])
    return tuple(Instance(_draw_coords(spec, rng)) for _ in range(n))


def tour_length(inst: Instance, tour: list[int]) -> float:
    d = inst.dist
    return float(sum(d[a, b] for a, b in zip(tour, tour[1:] + tour[:1])))


def nn_tour(inst: Instance) -> list[int]:
    d, n = inst.dist, len(inst.coords)
    tour, left = [0], set(range(1, n))
    while left:
        nxt = min(left, key=lambda j: d[tour[-1], j])
        tour.append(nxt)
        left.remove(nxt)
    return tour


def two_opt(inst: Instance, tour: list[int]) -> list[int]:
    """First-improvement 2-opt until no improving swap remains."""
    d, n = inst.dist, len(tour)
    tour = list(tour)
    improved = True
    while improved:
        improved = False
        for i in range(n - 1):
            for j in range(i + 2, n if i > 0 else n - 1):
                a, b, c, e = tour[i], tour[i + 1], tour[j], tour[(j + 1) % n]
                if d[a, c] + d[b, e] < d[a, b] + d[c, e] - 1e-12:
                    tour[i + 1 : j + 1] = reversed(tour[i + 1 : j + 1])
                    improved = True
    return tour


def build_tour(inst: Instance, expr: Expr) -> list[int]:
    """Construct a tour greedily using the priority expression."""
    d, n = inst.dist, len(inst.coords)
    coords = inst.coords
    visited = np.zeros(n, dtype=bool)
    visited[0] = True
    tour, cur = [0], 0
    for step in range(1, n):
        free = np.nonzero(~visited)[0]
        sub = d[np.ix_(free, free)]
        if free.size > 1:
            np.fill_diagonal(sub, np.inf)
            iso = sub.min(axis=1)
        else:
            iso = np.zeros(1)
        env = {
            "d_cur": d[cur, free],
            "d_start": d[0, free],
            "d_cent": np.linalg.norm(coords[free] - coords[free].mean(axis=0), axis=1),
            "d_iso": iso,
            "t": np.full(free.size, 1.0 - step / n),
        }
        with np.errstate(all="ignore"):
            prio = np.asarray(cand.evaluate(expr, env), dtype=float)
        if prio.ndim == 0:
            prio = np.full(free.size, float(prio))
        prio = np.where(np.isfinite(prio), prio, -np.inf)
        cur = int(free[int(np.argmax(prio))])  # ties -> lowest city index
        visited[cur] = True
        tour.append(cur)
    return tour


def excess(inst: Instance, expr: Expr) -> float:
    """Relative excess of the constructed tour over the 2-opt reference."""
    return tour_length(inst, build_tour(inst, expr)) / inst.reference_length - 1.0


# Reference heuristic expressed in the same DSL: Nearest Neighbour.
NEAREST_NEIGHBOR: Expr = cand.Op("sub", cand.Const(0.0), cand.Var("d_cur"))
