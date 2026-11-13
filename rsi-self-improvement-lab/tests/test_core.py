import numpy as np
import pytest

from src.core import candidate as cand
from src.core.evaluator import Budget, BudgetExceeded, Evaluator, score_expr
from src.core.history import DiscoveryTree
from src.core.metrics import cost_to_reach, frontier_hypervolume, resample_curve
from src.core.problem import (
    NEAREST_NEIGHBOR,
    TaskSpec,
    build_tour,
    make_instances,
    tour_length,
)

TASK = TaskSpec(name="t", kind="uniform", n_cities=15, n_train=4, n_test=4, seed=1)


def test_instances_are_deterministic_and_splits_differ():
    a, b = make_instances(TASK, "train"), make_instances(TASK, "train")
    assert all(np.array_equal(x.coords, y.coords) for x, y in zip(a, b))
    assert not np.array_equal(a[0].coords, make_instances(TASK, "test")[0].coords)


def test_tour_is_a_permutation():
    inst = make_instances(TASK, "train")[0]
    for expr in (NEAREST_NEIGHBOR, cand.parse("add(d_iso, mul(0.3, d_start))")):
        tour = build_tour(inst, expr)
        assert sorted(tour) == list(range(15))


def test_nn_expression_matches_reference_nn_length():
    inst = make_instances(TASK, "train")[0]
    assert tour_length(inst, build_tour(inst, NEAREST_NEIGHBOR)) == pytest.approx(inst.nn_length)


def test_reference_is_no_worse_than_nn_and_score_sign():
    inst = make_instances(TASK, "train")[0]
    assert inst.reference_length <= inst.nn_length + 1e-9
    assert score_expr(TASK, NEAREST_NEIGHBOR, "train").score < 0  # NN is above the 2-opt reference


def test_score_is_negated_percent_excess():
    res = score_expr(TASK, NEAREST_NEIGHBOR, "train")
    ex = [tour_length(i, build_tour(i, NEAREST_NEIGHBOR)) / i.reference_length - 1 for i in make_instances(TASK, "train")]
    assert res.score == pytest.approx(-100 * np.mean(ex))


def test_budget_charges_and_refuses():
    ev = Evaluator(TASK, Budget(4 * 2))  # two full evaluations
    ev.evaluate(NEAREST_NEIGHBOR)
    ev.evaluate(cand.parse("d_start"))
    assert ev.budget.used == 8
    with pytest.raises(BudgetExceeded):
        ev.evaluate(cand.parse("d_iso"))


def test_memoised_evaluation_is_free():
    ev = Evaluator(TASK, Budget(100))
    ev.evaluate(NEAREST_NEIGHBOR)
    used = ev.budget.used
    ev.evaluate(NEAREST_NEIGHBOR)
    assert ev.budget.used == used and ev.cache_hits == 1


def test_parse_roundtrip_and_rejects_unknown():
    e = cand.parse("sub(0, adiff(d_cur, 0.25))")
    assert cand.parse(cand.to_str(e)) == e
    assert cand.from_dict(cand.to_dict(e)) == e
    for bad in ("exec(d_cur)", "add(d_cur)", "add(d_cur, d_cur) extra", "foo"):
        with pytest.raises(ValueError):
            cand.parse(bad)


def test_diff_features_identity_is_zero():
    e = cand.parse("add(d_cur, 0.5)")
    assert all(v == 0.0 for v in cand.diff_features(e, e).values())
    f = cand.diff_features(e, cand.parse("add(d_cur, 0.9)"))
    assert f["const_shift"] == pytest.approx(0.4)


def test_hypervolume_and_curves():
    assert frontier_hypervolume([(0.0, 1.0)]) == pytest.approx(1.0)
    assert frontier_hypervolume([(1.0, 1.0)]) == pytest.approx(0.0)
    assert frontier_hypervolume([(0.2, 0.5), (0.6, 1.0)]) == pytest.approx(0.4 * 0.5 + 0.4 * 1.0)
    curve = [(10.0, -5.0), (20.0, -3.0)]
    assert resample_curve(curve, [5, 10, 25], -9.0) == [-9.0, -5.0, -3.0]
    assert cost_to_reach(curve, -4.0) == 20.0 and cost_to_reach(curve, 0.0) is None


def test_history_save_load_roundtrip(tmp_path):
    tree = DiscoveryTree("t", NEAREST_NEIGHBOR)
    tree.root.score = -10.0
    child = tree.add_child(0, cand.parse("d_start"), None, 1)
    child.score, child.cost = -4.0, 4.0
    tree.save(tmp_path / "t.json")
    loaded = DiscoveryTree.load(tmp_path / "t.json")
    assert loaded.best().id == 1 and loaded.nodes[0].children == [1]
    assert loaded.lineage(1) == [0, 1] and loaded.best_curve() == tree.best_curve()
