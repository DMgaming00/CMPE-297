"""Plain containers returned by every method so the protocol can treat them uniformly."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.history import DiscoveryTree


@dataclass
class DeployRun:
    """One deployment search on a held-out task."""

    task: str
    tree: DiscoveryTree
    units_used: float  # budget units consumed on this task (includes probes/labels)
    wall_s: float = 0.0


@dataclass
class MethodRun:
    method: str
    seed: int
    adapt_units: float  # total evaluator units spent before deployment (0 for baselines)
    deployments: list[DeployRun]
    log: dict[str, Any] = field(default_factory=dict)  # method-specific evidence (policies, readout, memory...)
