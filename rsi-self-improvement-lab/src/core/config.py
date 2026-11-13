"""Experiment configuration (JSON on disk, dataclasses in memory)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from src.core.problem import TaskSpec

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "experiments" / "configs"


def _task(name: str, kind: str, seed: int, **kw: Any) -> dict[str, Any]:
    return {"name": name, "kind": kind, "seed": seed, **kw}


DEFAULT_TRAIN_TASKS = [
    _task("uniform", "uniform", 11),
    _task("clusters", "clusters", 12, n_clusters=4, spread=0.07),
    _task("ring", "ring", 13, spread=0.08),
]
DEFAULT_HELD_OUT_TASKS = [
    _task("clusters_tight", "clusters", 21, n_clusters=6, spread=0.04),
    _task("grid_jitter", "grid", 22, spread=0.06),
]


@dataclass
class ExperimentConfig:
    name: str = "default"
    seeds: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])
    train_tasks: list[dict[str, Any]] = field(default_factory=lambda: list(DEFAULT_TRAIN_TASKS))
    held_out_tasks: list[dict[str, Any]] = field(default_factory=lambda: list(DEFAULT_HELD_OUT_TASKS))
    n_train: int = 12
    n_test: int = 30
    n_cities: int = 30
    adapt_evals: int = 60  # full evaluations per training task (adaptation phase)
    deploy_evals: int = 60  # full evaluations per held-out task (deployment phase)
    # Dream-RSI
    dream_candidates: int = 4
    dream_rhos: list[float] = field(default_factory=lambda: [0.0, 0.25, 0.5, 0.75, 1.0])
    dream_lambda: float = 0.05
    dream_deploy_rho: float = 1.0
    # Budget RSI
    budget_label_edits: int = 96
    budget_fit_instances: int = 4
    budget_proposals: int = 8
    # SO-RSI
    so_episode_evals: int = 20
    so_probe_instances: int = 3
    so_validation_instances: int = 6

    def train_specs(self) -> tuple[TaskSpec, ...]:
        return tuple(self._spec(t) for t in self.train_tasks)

    def held_out_specs(self) -> tuple[TaskSpec, ...]:
        return tuple(self._spec(t) for t in self.held_out_tasks)

    def _spec(self, raw: dict[str, Any]) -> TaskSpec:
        return TaskSpec(n_train=self.n_train, n_test=self.n_test, n_cities=self.n_cities, **raw)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentConfig:
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")
        return cls(**data)

    @classmethod
    def load(cls, name_or_path: str | Path) -> ExperimentConfig:
        path = Path(name_or_path)
        if not path.exists():
            path = CONFIG_DIR / f"{name_or_path}.json"
        if not path.exists():
            raise FileNotFoundError(f"no config {name_or_path!r} (looked in {CONFIG_DIR})")
        return cls.from_dict(json.loads(path.read_text()))

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n")
