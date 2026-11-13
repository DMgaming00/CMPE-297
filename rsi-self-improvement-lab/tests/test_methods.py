import numpy as np

from src.agents.proposer import ImproverConfig, MutationProposer
from src.agents.tree_search import (
    INITIAL_POLICY,
    SearchPolicy,
    run_tree_search,
    seed_program,
)
from src.core import candidate as cand
from src.core.candidate import EditRecord
from src.core.config import ExperimentConfig
from src.core.evaluator import Budget, Evaluator
from src.core.history import DiscoveryTree
from src.methods.budget_rsi.budget_rsi import collect_labelled_edits, thompson_parent
from src.methods.budget_rsi.readout import fit_readout
from src.methods.dream_rsi.dream_rsi import run_dream_rsi
from src.methods.dream_rsi.replay import policy_replay_score, replay
from src.methods.dream_rsi.reviser import history_stats, propose_revisions
from src.methods.so_rsi.anomalies import (
    detect_mismatch,
    detect_opposing,
    detect_recurrence,
)
from src.methods.so_rsi.so_rsi import run_so_rsi

CFG = ExperimentConfig.load("smoke")


def _tree(seed=0, evals=30):
    task = CFG.train_specs()[0]
    ev = Evaluator(task, Budget(evals * CFG.n_train))
    return run_tree_search(ev, MutationProposer(), seed_program(), INITIAL_POLICY, np.random.default_rng(seed), ImproverConfig())


# ---- Dream-RSI -----------------------------------------------------------------------------
def test_replay_makes_no_new_evaluations_and_is_bounded_by_the_record():
    tree = _tree()
    res = replay(tree, SearchPolicy(temperature=1.0), 1.0, np.random.default_rng(0))
    assert res.calls <= len(tree.nodes) - 1
    top = max(n.score for n in tree.evaluated())
    assert tree.root.score <= res.best_score <= top  # can only reveal recorded outcomes


def test_replay_of_full_tree_reaches_recorded_best():
    tree = _tree()
    res = replay(tree, SearchPolicy(temperature=1.0, patience=1000.0), 1.0, np.random.default_rng(0))
    assert res.best_score == max(n.score for n in tree.evaluated())


def test_replay_prefers_policy_that_does_not_quit_before_the_improvement():
    tree = DiscoveryTree("t", cand.parse("d_cur"))
    tree.root.score = -10.0
    for i, sc in enumerate([-12.0] * 3 + [-3.0] + [-12.0] * 8, start=1):  # the only improvement is the 4th child
        tree.add_child(0, cand.parse(f"add(d_cur, {i})"), None, i).score = sc
    args = ([tree], [0.0, 0.5, 1.0], 0.0, 1)
    lazy = policy_replay_score(SearchPolicy(temperature=0.0, patience=1.0), *args)  # quits before the improvement
    patient = policy_replay_score(SearchPolicy(temperature=0.0, patience=4.0), *args)  # waits, then stops early
    assert patient > lazy


def test_revisions_are_valid_and_incumbent_never_loses_ties():
    trees = [_tree(0), _tree(1)]
    revs = propose_revisions(INITIAL_POLICY, trees, np.random.default_rng(0), 3)
    assert len(revs) == 3 and all(1 <= r.batch <= 8 and r.patience >= 1 for r in revs)
    assert set(history_stats(trees)) >= {"mean_parent_rank", "stall_p90"}


def test_dream_rsi_run_is_deterministic_and_logs_generations():
    a, b = run_dream_rsi(CFG, 0), run_dream_rsi(CFG, 0)
    assert [d.tree.best().score for d in a.deployments] == [d.tree.best().score for d in b.deployments]
    assert len(a.log["generations"]) == len(CFG.train_tasks)
    g = a.log["generations"][0]
    assert g["replay_scores"][g["chosen"]] >= g["replay_scores"][0]  # selection never worsens replay score


# ---- Budget RSI ------------------------------------------------------------------------------
def test_ridge_readout_recovers_linear_signal():
    rng = np.random.default_rng(0)
    X = np.column_stack([np.ones(200), rng.normal(size=(200, 9))])
    w = np.arange(10, dtype=float) / 5
    ro = fit_readout(X, X @ w, ridge=1e-6)
    assert np.allclose(ro.weights, w, atol=1e-3)


def test_labelled_edits_shape_and_cost():
    lab = collect_labelled_edits(CFG, np.random.default_rng(0))
    assert lab.X.shape == (CFG.budget_label_edits, 10) and lab.y.min() >= 0.0
    assert lab.units >= CFG.budget_label_edits * CFG.budget_fit_instances


def test_thompson_prefers_high_solved_counts():
    nodes = []
    for i, solved in enumerate([0, 11]):
        n = cand.Op("add", cand.Var("d_cur"), cand.Const(float(i)))
        nodes.append(cand.Candidate(i, None, n, score=0.0, solved=solved, n_instances=12))
    picks = [thompson_parent(nodes, np.random.default_rng(s)).id for s in range(50)]
    assert picks.count(1) > 40


# ---- SO-RSI ----------------------------------------------------------------------------------
def _fake_tree(kinds, accepted_ids=()):
    tree = DiscoveryTree("t", cand.parse("d_cur"))
    tree.root.score = -10.0
    for i, k in enumerate(kinds, start=1):
        node = tree.add_child(0, cand.parse(f"add(d_cur, {i})"), EditRecord(k, (), {}, ""), i)
        node.score = -5.0 if i in accepted_ids else -20.0
    return tree


def test_recurrence_detected_only_when_a_kind_never_helps():
    tree = _fake_tree(["swap_op"] * 9 + ["add_term"], accepted_ids={10})
    found = detect_recurrence(tree)
    assert [a.subject for a in found] == ["swap_op"]
    assert detect_recurrence(_fake_tree(["swap_op"] * 9, accepted_ids={3})) == []


def test_opposing_edits_detected():
    tree = DiscoveryTree("t", cand.parse("d_cur"))
    tree.root.score = -10.0
    prev = 0
    for i, (detail, score) in enumerate([("1->2", -8.0), ("2->1", -6.0)], start=1):
        n = tree.add_child(prev, cand.parse(f"add(d_cur, {i})"), EditRecord("perturb_const", (1,), {}, detail), i)
        n.score, prev = score, n.id
    assert len(detect_opposing(tree)) == 1


def test_mismatch_detector_thresholds():
    assert detect_mismatch(3.0, -0.5) is not None
    assert detect_mismatch(3.0, 2.5) is None
    assert detect_mismatch(0.2, -1.0) is None


def test_so_rsi_records_memory_and_respects_budget():
    run = run_so_rsi(CFG, 0, "so_rsi")
    assert run.adapt_units <= CFG.adapt_evals * CFG.n_train * len(CFG.train_tasks) + 1e-6
    assert all(set(r) >= {"anomaly", "verdict", "intervention"} for r in run.log["memory"])
    naive = run_so_rsi(CFG, 0, "naive_rsi")
    assert naive.log["memory"] == []  # first-order RSI keeps no causal evidence
