"""SQLite commerce repository used by the LOCAL MCP server.

Design rules (mirrored by the production Toolbox SQL in configs/toolbox/ecommerce_tools.yaml):

* every query is parameterised - user text is never concatenated into SQL;
* every order/quote read and write is scoped by ``user_id``;
* purchases are two-phase: ``prepare_order`` creates a short-lived, non-binding quote,
  ``place_order`` atomically consumes the quote and decrements stock;
* ``place_order`` is idempotent per quote (replaying it returns the same order);
* money is stored as integer cents.
"""

from __future__ import annotations

import json
import re
import secrets
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

MAX_QUANTITY_PER_ORDER = 10
QUOTE_TTL = timedelta(minutes=15)
MAX_SEARCH_RESULTS = 20

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  user_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  city TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stores (
  store_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  city TEXT NOT NULL,
  address TEXT NOT NULL,
  hours TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
  sku TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  brand TEXT NOT NULL,
  category TEXT NOT NULL,
  description TEXT NOT NULL,
  price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
  tags TEXT NOT NULL DEFAULT '',
  active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS inventory (
  store_id TEXT NOT NULL REFERENCES stores(store_id),
  sku TEXT NOT NULL REFERENCES products(sku),
  quantity INTEGER NOT NULL CHECK (quantity >= 0),
  PRIMARY KEY (store_id, sku)
);
CREATE TABLE IF NOT EXISTS quotes (
  quote_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(user_id),
  sku TEXT NOT NULL REFERENCES products(sku),
  store_id TEXT NOT NULL REFERENCES stores(store_id),
  quantity INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 10),
  unit_price_cents INTEGER NOT NULL,
  total_cents INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('open', 'consumed')),
  order_id TEXT,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
  order_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(user_id),
  quote_id TEXT UNIQUE REFERENCES quotes(quote_id),
  sku TEXT NOT NULL REFERENCES products(sku),
  store_id TEXT NOT NULL REFERENCES stores(store_id),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  unit_price_cents INTEGER NOT NULL,
  total_cents INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('processing', 'shipped', 'delivered', 'cancelled')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS orders_user_idx ON orders(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS quotes_user_idx ON quotes(user_id);
"""

_STOP_WORDS = frozenset(
    [
        "a", "an", "and", "any", "are", "for", "from", "have", "i", "in", "is", "me", "my", "of",
        "on", "or", "please", "show", "some", "the", "to", "under", "over", "with", "want", "need",
        "looking", "find", "get", "products", "product", "items", "item"
    ]
)
_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,40}$")


class CommerceError(Exception):
    """Domain error returned to the agent as structured data."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def as_dict(self) -> dict[str, Any]:
        return {"ok": False, "error": {"code": self.code, "message": self.message}}


def format_money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_id(value: str, field: str) -> str:
    value = (value or "").strip()
    if not _ID_RE.fullmatch(value):
        raise CommerceError("INVALID_ARGUMENT", f"{field} is missing or malformed.")
    return value


def _stem(token: str) -> str:
    """Tiny suffix stripper so "running shoes" matches "run" / "shoe"."""
    if token.endswith("ing") and len(token) > 5:
        token = token[:-3]
        if len(token) > 2 and token[-1] == token[-2]:
            token = token[:-1]
    elif token.endswith("es") and len(token) > 4 and token[-3] in "sxz":
        token = token[:-2]
    elif token.endswith("s") and len(token) > 3 and not token.endswith("ss"):
        token = token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    return [_stem(t) for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP_WORDS]


@dataclass
class CommerceStore:
    db_path: Path
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    # ------------------------------------------------------------------ plumbing
    @contextmanager
    def _connect(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        try:
            if write:
                # IMMEDIATE takes the write lock up-front so check-then-update is atomic
                # across concurrent MCP server processes.
                conn.execute("BEGIN IMMEDIATE")
                try:
                    yield conn
                except BaseException:
                    conn.execute("ROLLBACK")
                    raise
                conn.execute("COMMIT")
            else:
                yield conn
        finally:
            conn.close()

    def initialize(self, seed: dict[str, Any], *, reset: bool = False) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if reset and self.db_path.exists():
            self.db_path.unlink()
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(_SCHEMA)
            if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]:
                return
        with self._connect(write=True) as conn:
            conn.executemany("INSERT INTO users VALUES (:user_id, :display_name, :email, :city)",
                             seed["users"])
            conn.executemany(
                "INSERT INTO stores VALUES (:store_id, :name, :city, :address, :hours)",
                seed["stores"])
            conn.executemany(
                "INSERT INTO products (sku, name, brand, category, description, price_cents, tags)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(p["sku"], p["name"], p["brand"], p["category"], p["description"],
                  p["price_cents"], " ".join(p["tags"])) for p in seed["products"]])
            conn.executemany("INSERT INTO inventory VALUES (:store_id, :sku, :quantity)",
                             seed["inventory"])
            for o in seed["orders"]:
                conn.execute(
                    "INSERT INTO orders (order_id, user_id, quote_id, sku, store_id, quantity,"
                    " unit_price_cents, total_cents, status, created_at, updated_at)"
                    " VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (o["order_id"], o["user_id"], o["sku"], o["store_id"], o["quantity"],
                     o["unit_price_cents"], o["unit_price_cents"] * o["quantity"], o["status"],
                     o["created_at"], o["created_at"]))

    # ------------------------------------------------------------------ catalog
    def search_products(self, query: str, category: str = "", max_price: float | None = None,
                        limit: int = 10) -> dict[str, Any]:
        tokens = tokenize(query)
        if not tokens and not category.strip():
            raise CommerceError("INVALID_ARGUMENT", "Provide search terms or a category.")
        limit = max(1, min(int(limit), MAX_SEARCH_RESULTS))
        sql = ("SELECT p.*, COALESCE(SUM(i.quantity), 0) AS total_stock FROM products p "
               "LEFT JOIN inventory i ON i.sku = p.sku WHERE p.active = 1")
        params: list[Any] = []
        if category.strip():
            sql += " AND lower(p.category) = lower(?)"
            params.append(category.strip())
        if max_price is not None:
            if max_price < 0:
                raise CommerceError("INVALID_ARGUMENT", "max_price must be non-negative.")
            sql += " AND p.price_cents <= ?"
            params.append(round(max_price * 100))
        sql += " GROUP BY p.sku"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        fields = {"name": 3, "tags": 2, "category": 2, "brand": 2, "description": 1}
        scored = []
        for row in rows:
            field_tokens = {f: set(tokenize(str(row[f]))) for f in fields}
            matched = {t for t in tokens if any(t in ft for ft in field_tokens.values())}
            if tokens and not matched:
                continue
            # Rank by how many distinct query terms match, then by field weight.
            score = 10 * len(matched) + sum(
                w for t in tokens for f, w in fields.items() if t in field_tokens[f])
            scored.append((score, row))
        scored.sort(key=lambda item: (-item[0], item[1]["price_cents"]))
        results = [self._product_summary(row) | {"relevance": score}
                   for score, row in scored[:limit]]
        return {"ok": True, "count": len(results), "products": results}

    def get_product(self, sku: str) -> dict[str, Any]:
        sku = _require_id(sku, "sku").upper()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT p.*, COALESCE(SUM(i.quantity), 0) AS total_stock FROM products p "
                "LEFT JOIN inventory i ON i.sku = p.sku WHERE p.sku = ? GROUP BY p.sku",
                (sku,)).fetchone()
        if row is None or not row["active"]:
            raise CommerceError("NOT_FOUND", f"No active product with SKU {sku}.")
        return {"ok": True, "product": self._product_summary(row) | {
            "description": row["description"], "tags": row["tags"].split()}}

    def check_inventory(self, sku: str, store_id: str = "") -> dict[str, Any]:
        sku = _require_id(sku, "sku").upper()
        self.get_product(sku)
        sql = ("SELECT s.store_id, s.name, s.city, i.quantity FROM inventory i "
               "JOIN stores s ON s.store_id = i.store_id WHERE i.sku = ?")
        params: list[Any] = [sku]
        if store_id.strip():
            sql += " AND s.store_id = ?"
            params.append(_require_id(store_id, "store_id").upper())
        with self._connect() as conn:
            rows = conn.execute(sql + " ORDER BY i.quantity DESC", params).fetchall()
        if store_id.strip() and not rows:
            raise CommerceError("NOT_FOUND", f"Unknown store {store_id}.")
        return {"ok": True, "sku": sku, "availability": [
            {"store_id": r["store_id"], "store_name": r["name"], "city": r["city"],
             "quantity": r["quantity"], "in_stock": r["quantity"] > 0} for r in rows]}

    def find_stores(self, city: str = "") -> dict[str, Any]:
        with self._connect() as conn:
            if city.strip():
                rows = conn.execute("SELECT * FROM stores WHERE lower(city) = lower(?)",
                                    (city.strip(),)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM stores ORDER BY city").fetchall()
        return {"ok": True, "stores": [dict(r) for r in rows]}

    # ------------------------------------------------------------------ orders
    def prepare_order(self, user_id: str, sku: str, quantity: int,
                      store_id: str = "WH-ONLINE") -> dict[str, Any]:
        user_id = self._require_user(user_id)
        sku = _require_id(sku, "sku").upper()
        store_id = _require_id(store_id or "WH-ONLINE", "store_id").upper()
        if not isinstance(quantity, int) or isinstance(quantity, bool):
            raise CommerceError("INVALID_ARGUMENT", "quantity must be an integer.")
        if not 1 <= quantity <= MAX_QUANTITY_PER_ORDER:
            raise CommerceError("INVALID_QUANTITY",
                                f"quantity must be between 1 and {MAX_QUANTITY_PER_ORDER}.")
        now = self.clock()
        with self._connect(write=True) as conn:
            product = conn.execute("SELECT * FROM products WHERE sku = ? AND active = 1",
                                   (sku,)).fetchone()
            if product is None:
                raise CommerceError("NOT_FOUND", f"No active product with SKU {sku}.")
            stock = conn.execute("SELECT quantity FROM inventory WHERE sku = ? AND store_id = ?",
                                 (sku, store_id)).fetchone()
            if stock is None:
                raise CommerceError("NOT_FOUND", f"{sku} is not carried at store {store_id}.")
            if stock["quantity"] < quantity:
                raise CommerceError(
                    "INSUFFICIENT_STOCK",
                    f"Only {stock['quantity']} unit(s) of {sku} available at {store_id}.")
            quote_id = "Q-" + secrets.token_hex(6).upper()
            total = product["price_cents"] * quantity
            conn.execute(
                "INSERT INTO quotes VALUES (?, ?, ?, ?, ?, ?, ?, 'open', NULL, ?, ?)",
                (quote_id, user_id, sku, store_id, quantity, product["price_cents"], total,
                 _iso(now), _iso(now + QUOTE_TTL)))
        return {"ok": True, "quote": {
            "quote_id": quote_id, "sku": sku, "product_name": product["name"],
            "store_id": store_id, "quantity": quantity,
            "unit_price": format_money(product["price_cents"]),
            "total": format_money(total), "total_cents": total,
            "expires_at": _iso(now + QUOTE_TTL),
            "note": "Non-binding quote. Stock is not reserved and nothing has been charged."}}

    def place_order(self, user_id: str, quote_id: str) -> dict[str, Any]:
        user_id = self._require_user(user_id)
        quote_id = _require_id(quote_id, "quote_id").upper()
        now = self.clock()
        with self._connect(write=True) as conn:
            quote = conn.execute("SELECT * FROM quotes WHERE quote_id = ? AND user_id = ?",
                                 (quote_id, user_id)).fetchone()
            if quote is None:
                raise CommerceError("NOT_FOUND", "Quote not found for this customer.")
            if quote["status"] == "consumed":
                order = self._order_row(conn, user_id, quote["order_id"])
                return {"ok": True, "already_placed": True, "order": order}
            if quote["expires_at"] < _iso(now):
                raise CommerceError("QUOTE_EXPIRED", "Quote expired. Prepare a new quote.")
            updated = conn.execute(
                "UPDATE inventory SET quantity = quantity - ? "
                "WHERE store_id = ? AND sku = ? AND quantity >= ?",
                (quote["quantity"], quote["store_id"], quote["sku"], quote["quantity"]))
            if updated.rowcount != 1:
                raise CommerceError("INSUFFICIENT_STOCK",
                                    "Stock changed since the quote was prepared.")
            order_id = "ORD-" + secrets.token_hex(4).upper()
            conn.execute(
                "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'processing', ?, ?)",
                (order_id, user_id, quote_id, quote["sku"], quote["store_id"],
                 quote["quantity"], quote["unit_price_cents"], quote["total_cents"],
                 _iso(now), _iso(now)))
            conn.execute("UPDATE quotes SET status = 'consumed', order_id = ? WHERE quote_id = ?",
                         (order_id, quote_id))
            order = self._order_row(conn, user_id, order_id)
        return {"ok": True, "already_placed": False, "order": order}

    def list_orders(self, user_id: str, limit: int = 10) -> dict[str, Any]:
        user_id = self._require_user(user_id)
        limit = max(1, min(int(limit), 50))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT order_id FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)).fetchall()
            orders = [self._order_row(conn, user_id, r["order_id"]) for r in rows]
        return {"ok": True, "orders": orders}

    def get_order(self, user_id: str, order_id: str) -> dict[str, Any]:
        user_id = self._require_user(user_id)
        order_id = _require_id(order_id, "order_id").upper()
        with self._connect() as conn:
            order = self._order_row(conn, user_id, order_id)
        return {"ok": True, "order": order}

    def cancel_order(self, user_id: str, order_id: str) -> dict[str, Any]:
        user_id = self._require_user(user_id)
        order_id = _require_id(order_id, "order_id").upper()
        now = self.clock()
        with self._connect(write=True) as conn:
            order = self._order_row(conn, user_id, order_id)
            if order["status"] != "processing":
                raise CommerceError("NOT_CANCELLABLE",
                                    f"Order is {order['status']}; only processing orders can "
                                    "be cancelled.")
            conn.execute("UPDATE orders SET status = 'cancelled', updated_at = ? "
                         "WHERE order_id = ? AND user_id = ?", (_iso(now), order_id, user_id))
            conn.execute("UPDATE inventory SET quantity = quantity + ? WHERE store_id = ? AND "
                         "sku = ?", (order["quantity"], order["store_id"], order["sku"]))
            order = self._order_row(conn, user_id, order_id)
        return {"ok": True, "order": order}

    # ------------------------------------------------------------------ helpers
    def _require_user(self, user_id: str) -> str:
        user_id = _require_id(user_id, "user_id")
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone() is None:
                raise CommerceError("UNAUTHENTICATED", "Unknown customer identity.")
        return user_id

    @staticmethod
    def _order_row(conn: sqlite3.Connection, user_id: str, order_id: str | None
                   ) -> dict[str, Any]:
        row = conn.execute(
            "SELECT o.*, p.name AS product_name, s.name AS store_name FROM orders o "
            "JOIN products p ON p.sku = o.sku JOIN stores s ON s.store_id = o.store_id "
            "WHERE o.order_id = ? AND o.user_id = ?", (order_id, user_id)).fetchone()
        if row is None:
            # Same message whether the order is missing or owned by someone else:
            # never confirm the existence of another customer's order.
            raise CommerceError("NOT_FOUND", "Order not found for this customer.")
        return {"order_id": row["order_id"], "status": row["status"], "sku": row["sku"],
                "product_name": row["product_name"], "store_id": row["store_id"],
                "store": row["store_name"],
                "quantity": row["quantity"], "unit_price": format_money(row["unit_price_cents"]),
                "total": format_money(row["total_cents"]), "created_at": row["created_at"],
                "updated_at": row["updated_at"]}

    @staticmethod
    def _product_summary(row: sqlite3.Row) -> dict[str, Any]:
        return {"sku": row["sku"], "name": row["name"], "brand": row["brand"],
                "category": row["category"], "price": format_money(row["price_cents"]),
                "price_cents": row["price_cents"], "total_stock": row["total_stock"]}


def load_seed(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
