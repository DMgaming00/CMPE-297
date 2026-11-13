import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

"""Codelab 09 - ablations and failure analysis on the saved full experiment (no re-run needed)."""

from src.benchmarks import protocol as P


def main() -> None:
    try:
        rows = P.load_rows("default")
    except FileNotFoundError as exc:
        raise SystemExit(f"{exc}\n(this codelab analyses the full experiment)") from exc
    summ = {s["method"]: s for s in P.summarize(rows)}
    print(f"{'variant':<22}{'final test':>11}{'vs full method':>16}")
    for full, abls in {
        "dream_rsi": ["dream_no_replay", "dream_no_evolution"],
        "budget_rsi": ["budget_parent_only", "budget_no_screen"],
        "so_rsi": ["naive_rsi", "so_no_probes", "so_no_memory"],
    }.items():
        print(f"{full:<22}{summ[full]['final']:>11.2f}")
        for a in abls:
            d = P.paired_vs(rows, a, full)
            print(f"  - {a:<18}{summ[a]['final']:>11.2f}{d['mean_diff']:>+10.2f} [{d['ci_lo']:+.2f},{d['ci_hi']:+.2f}]")

    print("\nFailure analysis: runs where the discovered program did NOT beat the initial solution on the hidden test split")
    for m in P.RSI_METHODS + ["fixed_tree"]:
        rs = [r for r in rows if r["method"] == m]
        bad = [r for r in rs if r["improvement"] < 1.0]
        worse = [r for r in rs if r["final_test"] < r["initial_test"] - 1e-9]
        print(
            f"  {m:<11} no meaningful gain in {len(bad)}/{len(rs)} runs; test score WORSE than initial in {len(worse)}/{len(rs)} (train/test gap)"
        )


if __name__ == "__main__":
    main()
