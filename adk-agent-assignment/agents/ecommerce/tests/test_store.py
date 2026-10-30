"""Unit tests for the SQLite commerce repository (no LLM, no network)."""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from adk_shared.config import DATA_DIR
from agents.ecommerce.mcp_server.store import CommerceError, CommerceStore, load_seed


@pytest.fixture
def store(tmp_path: Path) -> CommerceStore:
    s = CommerceStore(tmp_path / "shop.sqlite")
    s.initialize(load_seed(DATA_DIR / "ecommerce.json"))
    return s


def _stock(store: CommerceStore, sku: str, store_id: str) -> int:
    rows = store.check_inventory(sku, store_id)["availability"]
    return rows[0]["quantity"]


def test_search_ranks_relevant_products_and_filters_price(store):
    result = store.search_products("running shoes", max_price=100)
    names = [p["name"] for p in result["products"]]
    assert names[0] == "AeroRun Trainer"
    assert all(p["price_cents"] <= 10000 for p in result["products"])


def test_search_by_category(store):
    result = store.search_products("", category="outdoor")
    assert result["count"] == 4
    assert {p["category"] for p in result["products"]} == {"outdoor"}


def test_search_requires_terms(store):
    with pytest.raises(CommerceError) as err:
        store.search_products("   ")
    assert err.value.code == "INVALID_ARGUMENT"


def test_search_is_parameterised_against_sql_injection(store):
    hostile = "x' OR 1=1; DROP TABLE products; --"
    assert store.search_products(hostile, category="' OR '1'='1")["count"] == 0
    assert store.get_product("FTW-101")["ok"]  # table still exists


def test_unknown_and_malformed_product(store):
    with pytest.raises(CommerceError) as err:
        store.get_product("NOPE-999")
    assert err.value.code == "NOT_FOUND"
    with pytest.raises(CommerceError) as err:
        store.get_product("FTW-101; DROP")
    assert err.value.code == "INVALID_ARGUMENT"


def test_inventory_per_store(store):
    result = store.check_inventory("FTW-104")
    by_store = {r["store_id"]: r["quantity"] for r in result["availability"]}
    assert by_store["ST-SJC"] == 0 and by_store["WH-ONLINE"] == 2


@pytest.mark.parametrize("quantity", [0, -1, 11, True])
def test_invalid_quantity_rejected(store, quantity):
    with pytest.raises(CommerceError) as err:
        store.prepare_order("cust-alice", "FTW-101", quantity)
    assert err.value.code in {"INVALID_QUANTITY", "INVALID_ARGUMENT"}


def test_unavailable_inventory_rejected(store):
    with pytest.raises(CommerceError) as err:
        store.prepare_order("cust-alice", "FTW-104", 1, "ST-SJC")
    assert err.value.code == "INSUFFICIENT_STOCK"


def test_prepare_does_not_change_stock_and_place_does(store):
    before = _stock(store, "FTW-101", "WH-ONLINE")
    quote = store.prepare_order("cust-alice", "FTW-101", 2)["quote"]
    assert quote["total"] == "$179.98"
    assert _stock(store, "FTW-101", "WH-ONLINE") == before
    order = store.place_order("cust-alice", quote["quote_id"])["order"]
    assert order["status"] == "processing" and order["total"] == "$179.98"
    assert _stock(store, "FTW-101", "WH-ONLINE") == before - 2


def test_place_order_is_idempotent(store):
    quote = store.prepare_order("cust-alice", "FTW-101", 1)["quote"]
    first = store.place_order("cust-alice", quote["quote_id"])
    second = store.place_order("cust-alice", quote["quote_id"])
    assert second["already_placed"] is True
    assert second["order"]["order_id"] == first["order"]["order_id"]
    assert len(store.list_orders("cust-alice")["orders"]) == 3  # 2 seeded + 1


def test_user_isolation_for_quotes_and_orders(store):
    quote = store.prepare_order("cust-alice", "FTW-101", 1)["quote"]
    with pytest.raises(CommerceError) as err:
        store.place_order("cust-bob", quote["quote_id"])
    assert err.value.code == "NOT_FOUND"
    with pytest.raises(CommerceError) as err:
        store.get_order("cust-bob", "ORD-1001")  # Alice's order
    assert err.value.code == "NOT_FOUND"
    with pytest.raises(CommerceError):
        store.cancel_order("cust-alice", "ORD-1003")  # Bob's order
    assert {o["order_id"] for o in store.list_orders("cust-bob")["orders"]} == {"ORD-1003"}


def test_unknown_customer_is_rejected(store):
    with pytest.raises(CommerceError) as err:
        store.list_orders("cust-mallory")
    assert err.value.code == "UNAUTHENTICATED"


def test_quote_expiry(tmp_path):
    now = [datetime(2026, 10, 29, 12, 0, tzinfo=UTC)]
    s = CommerceStore(tmp_path / "exp.sqlite", clock=lambda: now[0])
    s.initialize(load_seed(DATA_DIR / "ecommerce.json"))
    quote = s.prepare_order("cust-alice", "FTW-101", 1)["quote"]
    now[0] += timedelta(minutes=16)
    with pytest.raises(CommerceError) as err:
        s.place_order("cust-alice", quote["quote_id"])
    assert err.value.code == "QUOTE_EXPIRED"


def test_stock_change_between_quote_and_order(store):
    q1 = store.prepare_order("cust-alice", "OUT-201", 1, "ST-SJC")["quote"]
    q2 = store.prepare_order("cust-bob", "OUT-201", 1, "ST-SJC")["quote"]
    store.place_order("cust-alice", q1["quote_id"])
    with pytest.raises(CommerceError) as err:
        store.place_order("cust-bob", q2["quote_id"])
    assert err.value.code == "INSUFFICIENT_STOCK"
    assert _stock(store, "OUT-201", "ST-SJC") == 0


def test_concurrent_orders_for_last_unit_never_oversell(store):
    quotes = [store.prepare_order(u, "OUT-201", 1, "ST-SJC")["quote"]["quote_id"]
              for u in ("cust-alice", "cust-bob", "cust-carol", "cust-dan")]
    users = ["cust-alice", "cust-bob", "cust-carol", "cust-dan"]
    results: list[str] = []

    def buy(user: str, quote_id: str) -> None:
        try:
            store.place_order(user, quote_id)
            results.append("ok")
        except CommerceError as exc:
            results.append(exc.code)

    threads = [threading.Thread(target=buy, args=pair) for pair in zip(users, quotes,
                                                                        strict=True)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("ok") == 1
    assert results.count("INSUFFICIENT_STOCK") == 3
    assert _stock(store, "OUT-201", "ST-SJC") == 0


def test_cancel_restocks_and_only_processing_orders(store):
    quote = store.prepare_order("cust-alice", "FTW-101", 3)["quote"]
    order = store.place_order("cust-alice", quote["quote_id"])["order"]
    before = _stock(store, "FTW-101", "WH-ONLINE")
    cancelled = store.cancel_order("cust-alice", order["order_id"])["order"]
    assert cancelled["status"] == "cancelled"
    assert _stock(store, "FTW-101", "WH-ONLINE") == before + 3
    with pytest.raises(CommerceError) as err:
        store.cancel_order("cust-alice", "ORD-1001")  # delivered
    assert err.value.code == "NOT_CANCELLABLE"


def test_database_constraint_blocks_negative_stock(store):
    conn = sqlite3.connect(store.db_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE inventory SET quantity = -1 WHERE sku = 'FTW-101'")
    conn.close()
