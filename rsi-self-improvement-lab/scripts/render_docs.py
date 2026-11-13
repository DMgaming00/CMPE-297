"""Fill measured-result tables in README/docs and codelab outputs from the saved experiment files.

Replaces the text between ``<!-- TABLE:name -->`` / ``<!-- /TABLE:name -->`` markers in README.md and
docs/*.md, and between ``<!--OUTPUT-->`` / ``<!--/OUTPUT-->`` in each codelab README (by running run.py).
Nothing here invents numbers: every value is read from ``experiments/results/``.

Usage: python scripts/render_docs.py [--tables] [--codelabs]   (default: both)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.benchmarks import protocol as P  # noqa: E402

LABEL = {
    "initial": "Initial solution (NN)",
    "random_search": "Random search",
    "hill_climb": "Hill-climb (fixed)",
    "aide_style": "AIDE-style tree (fixed)",
    "fixed_tree": "Fixed tree search (Dream-RSI's start policy)",
    "hill_climb_matched": "Hill-climb, +adaptation budget",
    "fixed_tree_matched": "Fixed tree, +adaptation budget",
    "dream_rsi": "**Dream-RSI**",
    "budget_rsi": "**Budget RSI**",
    "so_rsi": "**SO-RSI**",
}


def md(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] + ["---:"] * (len(header) - 1)) + "|"]
    return "\n".join(out + ["| " + " | ".join(r) + " |" for r in rows])


def main_table(rows):
    summ = P.summarize(rows)
    body = [
        [
            LABEL.get(s["method"], s["method"]),
            f"{s['initial']:.2f}",
            f"{s['final']:.2f} [{s['final_ci_lo']:.2f}, {s['final_ci_hi']:.2f}]",
            f"{s['improvement']:+.2f}",
            f"{s['success_rate']:.0%}",
            f"{s['adapt_units']:.0f}",
            f"{s['deploy_units']:.0f}",
            f"{s['wall_s']:.2f}",
        ]
        for s in summ
        if s["method"] in P.MAIN_METHODS
    ]
    return md(
        [
            "Method",
            "Initial",
            "Final test score [95% CI]",
            "Improvement",
            "Success",
            "Adaptation units",
            "Deployment units",
            "Wall time per held-out task (s)",
        ],
        body,
    )


def paired_table(rows):
    refs = ["fixed_tree", "aide_style", "fixed_tree_matched"]
    body = []
    for m in ["dream_rsi", "budget_rsi", "so_rsi"]:
        cells = [LABEL[m]]
        for r in refs:
            d = P.paired_vs(rows, m, r)
            cells.append(f"{d['mean_diff']:+.2f} [{d['ci_lo']:+.2f}, {d['ci_hi']:+.2f}]")
        body.append(cells)
    return md(["RSI method minus ...", "Fixed tree search", "AIDE-style tree", "Fixed tree, +adaptation budget"], body)


def match_table(rows):
    c = P.cost_to_match(rows, "fixed_tree")
    body = [
        [LABEL.get(m, m), f"{v['match_rate']:.0%}", f"{v['deploy_units']:.0f}", f"{v['incl_adapt']:.0f}"]
        for m, v in c.items()
        if m in P.MAIN_METHODS and m != "initial"
    ]
    return md(["Method", "Runs that reach it", "Median deployment units", "Median incl. amortised adaptation"], body)


GROUPS = {
    "dream_rsi": ["dream_no_replay", "dream_no_evolution"],
    "budget_rsi": ["budget_parent_only", "budget_no_screen"],
    "so_rsi": ["naive_rsi", "so_no_probes", "so_no_memory"],
}
DESC = {
    "dream_no_replay": "accept a random revised policy (no replay evidence)",
    "dream_no_evolution": "never revise the policy (collect trees only)",
    "budget_parent_only": "readout sees parent score only (the paper's own ablation)",
    "budget_no_screen": "no screening: K=1 proposal, evaluate it",
    "naive_rsi": "first-order RSI: reward-following edit weights, no diagnosis",
    "so_no_probes": "anomalies detected, default reflex instead of probes",
    "so_no_memory": "improver reset each episode (no inquiry memory)",
}


def ablation_table(rows):
    summ = {s["method"]: s for s in P.summarize(rows)}
    body = []
    for full, abls in GROUPS.items():
        if full not in summ:
            continue
        body.append([f"**{full}** (full method)", f"{summ[full]['final']:.2f}", "-"])
        for a in abls:
            if a in summ:
                d = P.paired_vs(rows, a, full)
                body.append(
                    [
                        f"&nbsp;&nbsp;`{a}`: {DESC[a]}",
                        f"{summ[a]['final']:.2f}",
                        f"{d['mean_diff']:+.2f} [{d['ci_lo']:+.2f}, {d['ci_hi']:+.2f}]",
                    ]
                )
    return md(["Variant", "Final test score", "Ablation minus full method, paired [95% CI]"], body)


def reduced_table(rows):
    summ = P.summarize(rows)
    body = []
    for s in summ:
        d = P.paired_vs(rows, s["method"], "fixed_tree") if s["method"] != "fixed_tree" else None
        body.append(
            [
                LABEL.get(s["method"], s["method"]),
                f"{s['final']:.2f}",
                "-" if d is None else f"{d['mean_diff']:+.2f} [{d['ci_lo']:+.2f}, {d['ci_hi']:+.2f}]",
            ]
        )
    return md(["Method (20 evals per task)", "Final test score", "Paired Δ vs fixed tree [95% CI]"], body)


def tables() -> dict[str, str]:
    main = P.load_rows("default")
    out = {"main": main_table(main), "paired": paired_table(main), "match": match_table(main), "ablation": ablation_table(main)}
    red = P.RESULTS_DIR / "reduced_budget_ablations" / "runs.json"
    if red.exists():
        import json

        out["reduced"] = reduced_table(json.loads(red.read_text()))
    n_runs = len({(r["seed"], r["task"]) for r in main if r["method"] == "fixed_tree"})
    out["npairs"] = str(n_runs)
    return out


def fill(path: Path, tabs: dict[str, str]) -> None:
    text = path.read_text()
    for name, body in tabs.items():
        sep = "" if name == "npairs" else "\n"  # npairs is an inline value, the rest are block tables
        text = re.sub(
            rf"(<!-- TABLE:{name} -->).*?(<!-- /TABLE:{name} -->)",
            lambda m, sep=sep, body=body: m.group(1) + sep + body + sep + m.group(2),
            text,
            flags=re.S,
        )
    path.write_text(text)


def codelab_outputs() -> None:
    for readme in sorted((ROOT / "codelabs").glob("*/README.md")):
        run = readme.parent / "run.py"
        proc = subprocess.run([sys.executable, str(run)], cwd=ROOT, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise SystemExit(f"{run} failed:\n{proc.stderr}")
        block = "```text\n" + proc.stdout.rstrip() + "\n```"
        text = readme.read_text()
        text = re.sub(
            r"(<!--OUTPUT-->\n).*?(\n<!--/OUTPUT-->)",
            lambda m, block=block: m.group(1) + block + m.group(2),
            text,
            flags=re.S,
        )
        readme.write_text(text)
        print("refreshed", readme.relative_to(ROOT))


if __name__ == "__main__":
    flags = set(sys.argv[1:]) or {"--tables", "--codelabs"}
    if "--tables" in flags:
        tabs = tables()
        for f in [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]:
            if f.exists():
                fill(f, tabs)
        print("tables refreshed")
    if "--codelabs" in flags:
        codelab_outputs()
