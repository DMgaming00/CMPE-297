import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

"""Codelab 05 - Dream-RSI: improve the exploration policy through replay worlds."""

from src.agents.tree_search import INITIAL_POLICY
from src.core.config import ExperimentConfig
from src.methods.dream_rsi.dream_rsi import run_dream_rsi


def main() -> None:
    cfg = ExperimentConfig()
    run = run_dream_rsi(cfg, seed=0)
    print("initial policy :", {k: round(v, 2) for k, v in INITIAL_POLICY.to_dict().items()})
    for g in run.log["generations"]:
        print(
            f"\ngeneration {g['generation']} (online rollout on '{g['task']}': best {g['online_best']:.2f}, {g['online_calls']} calls)"
        )
        for i, (pol, score) in enumerate(zip(g["candidate_policies"], g["replay_scores"])):
            tag = "incumbent" if i == 0 else f"revision {i}"
            mark = "  <== selected" if i == g["chosen"] else ""
            print(
                f"  {tag:<10} temp={pol['temperature']:.2f} explore={pol['explore_c']:.2f} restart={pol['restart_prob']:.2f} "
                f"batch={int(pol['batch'])} patience={pol['patience']:.0f}  replay score {score:+.3f}{mark}"
            )
    print("\nfinal policy   :", {k: round(v, 2) for k, v in run.log["final_policy"].items()})
    print("adaptation cost:", f"{run.adapt_units:.0f} units (online rollouts only; every replay was free)")
    for d in run.deployments:
        print(
            f"deployed on held-out '{d.task}': best train {d.tree.best().score:.2f} using {d.units_used:.0f} of {cfg.deploy_evals * cfg.n_train} units"
        )


if __name__ == "__main__":
    main()
