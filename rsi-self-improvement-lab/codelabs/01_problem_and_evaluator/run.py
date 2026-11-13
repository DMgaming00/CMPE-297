import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

"""Codelab 01 - the problem and its objective evaluator."""

from src.core.config import ExperimentConfig
from src.core.evaluator import Budget, BudgetExceeded, Evaluator, score_expr
from src.core.problem import NEAREST_NEIGHBOR, build_tour, make_instances, tour_length


def main() -> None:
    task = ExperimentConfig().train_specs()[0]
    inst = make_instances(task, "train")[0]
    print(
        f"task '{task.name}': {task.n_cities} cities, {len(make_instances(task, 'train'))} train / {task.n_test} test instances"
    )

    nn = tour_length(inst, build_tour(inst, NEAREST_NEIGHBOR))
    print(
        f"instance 0: NN tour {nn:.3f}  2-opt reference {inst.reference_length:.3f}  excess {nn / inst.reference_length - 1:.1%}"
    )

    res = score_expr(task, NEAREST_NEIGHBOR, "train")
    print(f"train score of Nearest-Neighbour = {res.score:.2f}  (score = -100 x mean excess; higher is better)")
    print(f"solved (within 12% of reference): {res.solved}/{res.n}")

    ev = Evaluator(task, Budget(total=2 * ev_cost(task)))
    ev.evaluate(NEAREST_NEIGHBOR)
    print(f"after 1 evaluation: used {ev.budget.used:.0f} of {ev.budget.total:.0f} units")
    ev.evaluate(NEAREST_NEIGHBOR)
    print(f"re-evaluating the same program is memoised and free: used {ev.budget.used:.0f}, cache hits {ev.cache_hits}")
    try:
        ev.evaluate(build_expr("d_start"))
        ev.evaluate(build_expr("d_iso"))
    except BudgetExceeded as exc:
        print(f"third distinct program refused: {exc}")


def ev_cost(task) -> float:
    return float(len(make_instances(task, "train")))


def build_expr(text: str):
    from src.core.candidate import parse

    return parse(text)


if __name__ == "__main__":
    main()
