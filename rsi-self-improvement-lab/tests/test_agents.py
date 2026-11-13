import numpy as np
import pytest

from src.agents.llm import LLMProposer, MissingCredentialsError, parse_reply
from src.agents.proposer import (
    EDIT_KINDS,
    ImproverConfig,
    MutationProposer,
    random_expr,
)
from src.agents.tree_search import (
    INITIAL_POLICY,
    SearchPolicy,
    hill_climb,
    random_search,
    run_tree_search,
    seed_program,
    select_batch,
)
from src.core import candidate as cand
from src.core.candidate import Candidate
from src.core.evaluator import Budget, Evaluator
from src.core.problem import TaskSpec

TASK = TaskSpec(name="t", kind="clusters", n_cities=15, n_train=4, n_test=4, seed=2)


def test_proposer_is_deterministic_and_changes_program():
    seed = seed_program()
    a = MutationProposer().propose(seed, np.random.default_rng(7), ImproverConfig())
    b = MutationProposer().propose(seed, np.random.default_rng(7), ImproverConfig())
    assert a[0] == b[0] and a[0] != seed
    assert cand.size(a[0]) <= 25 and a[1].kind in EDIT_KINDS + ("add_term",)


def test_edit_weights_steer_the_proposer():
    cfg = ImproverConfig(edit_weights={k: (1.0 if k == "swap_op" else 0.0) for k in EDIT_KINDS})
    prop, rng = MutationProposer(), np.random.default_rng(0)
    parent = cand.parse("add(d_cur, mul(0.5, d_iso))")
    kinds = {prop.propose(parent, rng, cfg)[1].kind for _ in range(20)}
    assert kinds <= {"swap_op", "add_term"}  # add_term only as the documented fallback


def test_random_expr_is_valid_dsl():
    rng = np.random.default_rng(0)
    for _ in range(30):
        e = random_expr(rng)
        assert cand.parse(cand.to_str(e)) is not None


def test_searches_respect_budget_and_never_regress_best():
    for fn in (
        lambda ev, r: hill_climb(ev, MutationProposer(), seed_program(), r, ImproverConfig()),
        lambda ev, r: run_tree_search(ev, MutationProposer(), seed_program(), INITIAL_POLICY, r),
        lambda ev, r: random_search(ev, seed_program(), r),
    ):
        ev = Evaluator(TASK, Budget(4 * 25))
        tree = fn(ev, np.random.default_rng(0))
        assert ev.budget.used <= 4 * 25
        curve = [s for _, s in tree.best_curve()]
        assert curve == sorted(curve)  # best-so-far is monotone
        assert tree.best().score >= tree.root.score


def test_search_is_reproducible():
    def go():
        ev = Evaluator(TASK, Budget(4 * 30))
        return run_tree_search(ev, MutationProposer(), seed_program(), INITIAL_POLICY, np.random.default_rng(3)).best().score

    assert go() == go()


def test_patience_stops_search_early():
    ev = Evaluator(TASK, Budget(4 * 200))
    policy = SearchPolicy(temperature=0.0, patience=2.0)
    tree = run_tree_search(ev, MutationProposer(), seed_program(), policy, np.random.default_rng(0), rho=0.0)
    assert len(tree.nodes) < 200


def test_greedy_selection_picks_best_node():
    nodes = [Candidate(i, None, seed_program(), score=s) for i, s in enumerate([-9.0, -3.0, -6.0])]
    pol = SearchPolicy(temperature=0.0, restart_prob=0.0)
    assert select_batch(nodes, 0, pol, np.random.default_rng(0)) == [1]


def test_llm_proposer_fails_loudly_without_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(MissingCredentialsError):
        LLMProposer()


def test_llm_reply_parser_accepts_only_the_dsl():
    assert parse_reply("```\nadd(d_cur, 0.2)\n```") == cand.parse("add(d_cur, 0.2)")
    with pytest.raises(ValueError):
        parse_reply("__import__('os')")
