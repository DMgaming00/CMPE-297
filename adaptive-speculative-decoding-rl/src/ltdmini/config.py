"""Experiment configuration loaded from YAML."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ModelsCfg:
    target: str = "random-tiny"          # HF id, or "random-tiny" for a local random model (no download)
    draft: str = "random-tiny-draft"
    dtype: str = "auto"                  # auto | float32 | float16 | bfloat16
    device: str = "auto"                 # auto | mps | cuda | cpu
    revision_target: str | None = None
    revision_draft: str | None = None


@dataclass
class DataCfg:
    train: list[str] = field(default_factory=lambda: ["humaneval"])
    val: list[str] = field(default_factory=lambda: ["humaneval"])
    test: list[str] = field(default_factory=lambda: ["gsm8k", "alpaca", "mtbench", "nq"])
    n_train: int = 120
    n_val: int = 24
    n_test_per_set: int = 40
    max_prompt_tokens: int = 512
    seed: int = 0


@dataclass
class DecodeCfg:
    max_new_tokens: int = 192
    dmax: int = 12                       # maximum draft depth (paper samples depths in [1, 12])
    temperature: float = 0.0             # v1 replicates the greedy setting (paper Table 1)


@dataclass
class TrainCfg:
    reward: str = "throughput"           # throughput | acceptance | time   (paper Table 2 ablation)
    total_timesteps: int = 300_000
    n_steps: int = 2048                  # paper: rollout buffer 2048
    batch_size: int = 256                # paper: minibatch 256
    learning_rate: float = 3e-4
    gamma: float = 0.99
    net_arch: list[int] = field(default_factory=lambda: [64, 64])
    eval_every: int = 20_000
    timing_noise: float = 0.05           # multiplicative log-normal noise on simulated step times
    seed: int = 0


@dataclass
class Config:
    name: str = "smoke"
    out_dir: str = "results/smoke"
    models: ModelsCfg = field(default_factory=ModelsCfg)
    data: DataCfg = field(default_factory=DataCfg)
    decode: DecodeCfg = field(default_factory=DecodeCfg)
    train: TrainCfg = field(default_factory=TrainCfg)

    @property
    def out(self) -> Path:
        p = Path(self.out_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config(path: str | Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    cfg = Config(
        name=raw.get("name", "experiment"),
        out_dir=raw.get("out_dir", f"results/{raw.get('name', 'experiment')}"),
        models=ModelsCfg(**raw.get("models", {})),
        data=DataCfg(**raw.get("data", {})),
        decode=DecodeCfg(**raw.get("decode", {})),
        train=TrainCfg(**raw.get("train", {})),
    )
    if cfg.decode.temperature != 0.0:
        raise ValueError("v1 replicates greedy decoding only (temperature 0). See docs/METHOD.md, 'Extensions'.")
    if cfg.train.reward not in {"throughput", "acceptance", "time"}:
        raise ValueError(f"unknown reward {cfg.train.reward!r}")
    return cfg
