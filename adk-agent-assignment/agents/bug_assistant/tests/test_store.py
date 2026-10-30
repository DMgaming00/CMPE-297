"""Unit tests for the bug-tracker repository and duplicate detection (no LLM)."""

from __future__ import annotations

from pathlib import Path

import pytest

from adk_shared.config import DATA_DIR
from agents.bug_assistant.mcp_server.similarity import rank, tokenize
from agents.bug_assistant.mcp_server.store import TicketError, TicketStore, load_seed


@pytest.fixture
def store(tmp_path: Path) -> TicketStore:
    s = TicketStore(tmp_path / "bugs.sqlite")
    s.initialize(load_seed(DATA_DIR / "bug_tickets.json"))
    return s


def test_tokenizer_drops_stop_words_and_normalises_plurals():
    assert tokenize("The coupons are removed at checkout") == ["coupon", "removed", "checkout"]


def test_rank_orders_by_similarity():
    docs = [(1, "checkout coupon crash"), (2, "login cookie loop"), (3, "coupon expiry")]
    ranked = rank("coupon checkout 500", docs)
    assert [doc_id for doc_id, _, _ in ranked][:2] == [1, 3]
    assert 2 not in [doc_id for doc_id, _, _ in ranked]


def test_search_finds_relevant_ticket(store):
    results = store.search("checkout 500 error after removing coupon")["results"]
    assert results[0]["id"] == 1
    assert "coupon" in results[0]["matched_terms"]


def test_search_status_filter(store):
    results = store.search("email", status="closed")["results"]
    assert {r["status"] for r in results} == {"closed"}


def test_get_ticket_includes_comments(store):
    ticket = store.get(2)
    assert ticket["ticket"]["title"].startswith("Login redirect loop")
    assert ticket["comments"][0]["author"] == "ana.silva"


def test_get_unknown_ticket(store):
    with pytest.raises(TicketError) as err:
        store.get(999)
    assert err.value.code == "NOT_FOUND"


def test_list_filters(store):
    p0 = store.list_tickets(priority="P0")["tickets"]
    assert {t["id"] for t in p0} == {6, 10}


def test_duplicate_detection_flags_near_duplicate(store):
    result = store.find_duplicates(
        "Stock becomes negative when two people buy the last item",
        "Concurrent purchases made inventory quantity negative; decrement not atomic.")
    top = result["candidates"][0]
    assert top["id"] == 6 and top["likely_duplicate"] is True


@pytest.mark.parametrize("title,description,expected_id", [
    ("Users stuck in login loop", "After session expires the browser keeps redirecting.", 2),
    ("Android app crash in orders screen", "App crashes opening order history.", 5),
])
def test_paraphrased_duplicates_are_flagged(store, title, description, expected_id):
    top = store.find_duplicates(title, description)["candidates"][0]
    assert top["id"] == expected_id and top["likely_duplicate"] is True


@pytest.mark.parametrize("title,description", [
    ("Typo on the about page footer", "The footer says 'Copywrite' instead of 'Copyright'."),
    ("Add wishlist feature", "Customers want to save products for later."),
])
def test_unrelated_report_is_not_flagged(store, title, description):
    result = store.find_duplicates(title, description)
    assert not any(c["likely_duplicate"] for c in result["candidates"])


def test_create_refuses_likely_duplicate_unless_allowed(store):
    kwargs = {"title": "Checkout 500 error when removing a coupon",
              "description": "Removing a coupon from the cart crashes checkout with HTTP 500 "
                             "TypeError in apply_discount.",
              "priority": "P1", "component": "checkout"}
    refused = store.create(**kwargs)
    assert refused["created"] is False
    assert refused["error"]["code"] == "POSSIBLE_DUPLICATE"
    assert refused["possible_duplicates"][0]["id"] == 1
    created = store.create(**kwargs, allow_duplicate=True)
    assert created["created"] is True and created["ticket"]["status"] == "open"


@pytest.mark.parametrize("field,value", [("title", "short"), ("priority", "urgent"),
                                         ("component", "Check Out!"),
                                         ("description", "too short")])
def test_create_validation(store, field, value):
    kwargs = {"title": "Profile page shows wrong avatar", "priority": "P3",
              "description": "After uploading a new avatar the old image is still shown.",
              "component": "web-ui"}
    kwargs[field] = value
    with pytest.raises(TicketError) as err:
        store.create(**kwargs)
    assert err.value.code == "INVALID_ARGUMENT"


def test_control_characters_are_stripped(store):
    created = store.create("Header\x00 injection in export", "CSV export writes raw \x1b"
                           "control characters into the header row.", "P3", "admin",
                           allow_duplicate=True)
    assert "\x00" not in created["ticket"]["title"]


def test_status_state_machine_and_audit_trail(store):
    store.update_status(1, "in_progress", "Investigating discount code path")
    with pytest.raises(TicketError) as err:
        store.update_status(1, "closed", "skip resolution")
    assert err.value.code == "INVALID_TRANSITION"
    comments = store.get(1)["comments"]
    assert comments[-1]["body"].startswith("Status open -> in_progress")


def test_priority_update_requires_valid_priority(store):
    assert store.update_priority(8, "P2", "Accessibility affects checkout")["ticket"][
        "priority"] == "P2"
    with pytest.raises(TicketError):
        store.update_priority(8, "P9", "nope nope")


def test_mark_duplicate(store):
    created = store.create("Coupon removal crashes checkout page", "Checkout fails with a "
                           "500 after removing a coupon code.", "P1", "checkout",
                           allow_duplicate=True)["ticket"]
    result = store.mark_duplicate(created["id"], 1, "Same root cause as #1")
    assert result["ticket"]["status"] == "duplicate" and result["ticket"]["duplicate_of"] == 1
    with pytest.raises(TicketError):
        store.mark_duplicate(1, 1, "self reference")
