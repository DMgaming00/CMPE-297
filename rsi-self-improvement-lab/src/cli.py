"""Command line interface.  ``python -m src.cli --help``"""

from __future__ import annotations

import argparse
import sys

from src.benchmarks import protocol as P
from src.core.config import ExperimentConfig
from src.utils.log import get_logger
from src.utils.table import summary_table

log = get_logger()
METHOD_ALIASES = {"dream-rsi": "dream_rsi", "budget-rsi": "budget_rsi", "so-rsi": "so_rsi"}


def _method(name: str) -> str:
    name = METHOD_ALIASES.get(name, name.replace("-", "_"))
    if name not in P.MAIN_METHODS + P.ABLATIONS:
        raise SystemExit(f"unknown method {name!r}. Available: {', '.join(P.MAIN_METHODS + P.ABLATIONS)}")
    return name


def _load(args: argparse.Namespace) -> ExperimentConfig:
    cfg = ExperimentConfig.load(args.config)
    if getattr(args, "seeds", None):
        cfg.seeds = list(range(args.seeds))
    return cfg


def _report(rows: list[dict], reference: str = "fixed_tree") -> None:
    summary = P.summarize(rows)
    print(summary_table(summary))
    methods = [s["method"] for s in summary]
    if reference in methods:
        print(f"\nPaired difference in final test score vs {reference} (same seed & task; higher is better):")
        for m in methods:
            if m != reference and m != "initial":
                d = P.paired_vs(rows, m, reference)
                print(
                    f"  {m:<22} {d['mean_diff']:+.2f}  95% CI [{d['ci_lo']:+.2f}, {d['ci_hi']:+.2f}]"
                    f"  win-rate {d['win_rate']:.0%}"
                )
        print(f"\nBudget needed to match {reference}'s final train score (median over runs that reach it):")
        for m, c in P.cost_to_match(rows, reference).items():
            if m != "initial":
                print(
                    f"  {m:<22} reached {c['match_rate']:.0%}  "
                    f"deploy units {c['deploy_units']:.0f}  incl. adaptation {c['incl_adapt']:.0f}"
                )


def cmd_baseline(args: argparse.Namespace) -> None:
    cfg = _load(args)
    rows = P.run_experiment(cfg, P.BASELINES, out_dir=P.RESULTS_DIR / f"{cfg.name}_baselines", workers=args.workers)
    _report(rows)


def cmd_run(args: argparse.Namespace) -> None:
    cfg = _load(args)
    method = _method(args.method)
    rows = P.run_experiment(cfg, ["initial", method], out_dir=P.RESULTS_DIR / f"{cfg.name}_{method}", workers=args.workers)
    _report(rows, reference="initial")


def cmd_compare(args: argparse.Namespace) -> None:
    cfg = _load(args)
    methods = P.MAIN_METHODS + (P.ABLATIONS if args.ablations else [])
    rows = P.run_experiment(cfg, methods, workers=args.workers)
    _report(rows)
    if not args.no_plots:
        from src.visualization.plots import make_all_figures

        print("\nfigures:", *make_all_figures(cfg.name), sep="\n  ")


def cmd_visualize(args: argparse.Namespace) -> None:
    from src.visualization.plots import make_all_figures

    print("figures:", *make_all_figures(args.config), sep="\n  ")


def cmd_demo(args: argparse.Namespace) -> None:
    cfg = ExperimentConfig.load("smoke")
    print("RSI demo: three RSI methods vs baselines on greedy-TSP heuristic discovery (smoke config)\n")
    rows = P.run_experiment(cfg, P.MAIN_METHODS, workers=args.workers, quiet=True)
    _report(rows)
    from src.visualization.plots import make_all_figures

    print("\nfigures:", *make_all_figures("smoke"), sep="\n  ")
    print("\nNOTE: smoke config is tiny (2 seeds, 20 evals). For the real experiment run `make compare`.")


def cmd_ablate(args: argparse.Namespace) -> None:
    cfg = _load(args)
    keep = ["fixed_tree", "dream_rsi", "budget_rsi", "so_rsi"] + P.ABLATIONS
    rows = P.run_experiment(cfg, keep, out_dir=P.RESULTS_DIR / f"{cfg.name}_ablations", workers=args.workers)
    _report(rows)


def cmd_llm_check(args: argparse.Namespace) -> None:
    import numpy as np

    from src.agents.llm import LLMProposer, MissingCredentialsError
    from src.agents.proposer import ImproverConfig
    from src.agents.tree_search import seed_program

    try:
        child, edit = LLMProposer().propose(seed_program(), np.random.default_rng(0), ImproverConfig())
    except MissingCredentialsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    from src.core import candidate as cand

    print("LLM proposed:", cand.to_str(child), edit.features)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m src.cli", description="RSI self-improvement lab")
    sub = p.add_subparsers(dest="command", required=True)

    def add(name: str, fn, help_: str, config: bool = True) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        if config:
            sp.add_argument("--config", default="default", help="config name in experiments/configs or a JSON path")
            sp.add_argument("--seeds", type=int, help="override: use seeds 0..N-1")
            sp.add_argument("--workers", type=int, default=None, help="processes (1 = serial)")
        return sp

    add("baseline", cmd_baseline, "run the non-RSI baselines")
    add("run", cmd_run, "run one method (plus the initial solution)").add_argument("--method", required=True)
    cp = add("compare", cmd_compare, "run all baselines and the three RSI methods")
    cp.add_argument("--ablations", action="store_true")
    cp.add_argument("--no-plots", action="store_true")
    add("ablate", cmd_ablate, "run the ablation suite")
    vp = sub.add_parser("visualize", help="regenerate figures from saved results")
    vp.add_argument("--config", default="default")
    vp.set_defaults(fn=cmd_visualize)
    dp = sub.add_parser("demo", help="fast deterministic end-to-end demo")
    dp.add_argument("--workers", type=int, default=None)
    dp.set_defaults(fn=cmd_demo)
    sub.add_parser("llm-check", help="try the optional real-LLM proposer").set_defaults(fn=cmd_llm_check)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
