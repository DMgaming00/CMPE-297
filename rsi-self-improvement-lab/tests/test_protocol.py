import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.benchmarks import protocol as P
from src.core.config import ExperimentConfig

ROOT = Path(__file__).resolve().parents[1]
CFG = ExperimentConfig.load("smoke")


def test_every_method_runs_on_the_shared_protocol(tmp_path):
    cfg = ExperimentConfig.from_dict(
        {**CFG.to_dict(), "seeds": [0], "adapt_evals": 10, "deploy_evals": 10, "so_episode_evals": 5, "budget_label_edits": 12}
    )
    rows = P.run_experiment(cfg, P.MAIN_METHODS + P.ABLATIONS, out_dir=tmp_path, workers=1, quiet=True)
    assert {r["method"] for r in rows} == set(P.MAIN_METHODS + P.ABLATIONS)
    for r in rows:
        assert r["deploy_units"] <= (cfg.deploy_evals + P.run_baseline.__globals__["matched_extra"](cfg)) * cfg.n_train + 1e-6
        assert r["final_train"] >= r["initial_train"]  # best-so-far never below the seed program
    assert (tmp_path / "summary.csv").exists() and json.loads((tmp_path / "runs.json").read_text())


def test_unknown_method_is_a_clean_error():
    with pytest.raises(KeyError):
        P.run_method("nope", CFG, 0)


def test_fair_budget_all_non_matched_methods_get_equal_deploy_budget(tmp_path):
    cfg = ExperimentConfig.from_dict(
        {**CFG.to_dict(), "seeds": [0], "adapt_evals": 10, "deploy_evals": 12, "so_episode_evals": 5, "budget_label_edits": 12}
    )
    rows = P.run_experiment(cfg, ["fixed_tree", "dream_rsi", "budget_rsi", "so_rsi"], out_dir=tmp_path, workers=1, quiet=True)
    cap = cfg.deploy_evals * cfg.n_train
    assert all(r["deploy_units"] <= cap + 1e-6 for r in rows)


def test_paired_comparison_math():
    rows = [
        {"method": m, "seed": s, "task": "t", "final_test": v}
        for m, vals in (("a", [-3, -4]), ("b", [-5, -4]))
        for s, v in enumerate(vals)
    ]
    d = P.paired_vs(rows, "a", "b")
    assert d["mean_diff"] == 1.0 and d["win_rate"] == 0.5


def test_regression_nearest_neighbour_baseline_score():
    """Pin the initial-solution score so evaluator / instance-generation changes are noticed."""
    from src.core.evaluator import score_expr
    from src.core.problem import NEAREST_NEIGHBOR

    task = ExperimentConfig().train_specs()[0]
    assert score_expr(task, NEAREST_NEIGHBOR, "train").score == pytest.approx(-15.15, abs=0.01)


def test_cli_smoke(tmp_path):
    out = subprocess.run([sys.executable, "-m", "src.cli", "--help"], cwd=ROOT, capture_output=True, text=True, check=True)
    assert "compare" in out.stdout and "demo" in out.stdout
    bad = subprocess.run(
        [sys.executable, "-m", "src.cli", "run", "--method", "bogus"], check=False, cwd=ROOT, capture_output=True, text=True
    )
    assert bad.returncode != 0 and "unknown method" in bad.stderr
    key = subprocess.run(
        [sys.executable, "-m", "src.cli", "llm-check"],
        check=False,
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
    )
    assert key.returncode == 2 and "LLM_API_KEY" in key.stderr
