"""SQLite ticket repository behind the LOCAL bug-tracker MCP server."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .similarity import rank

PRIORITIES = ("P0", "P1", "P2", "P3")
STATUSES = ("open", "in_progress", "resolved", "closed", "duplicate")
TRANSITIONS: dict[str, frozenset[str]] = {
    "open": frozenset({"in_progress", "resolved", "closed", "duplicate"}),
    "in_progress": frozenset({"open", "resolved", "duplicate"}),
    "resolved": frozenset({"closed", "open"}),
    "closed": frozenset({"open"}),
    "duplicate": frozenset({"open"}),
}
# Calibrated on the demo corpus (true duplicates scored 0.30-0.64, unrelated reports
# <= 0.24).  Re-calibrate on real data before relying on it in production.
DUPLICATE_THRESHOLD = 0.28
RELATED_THRESHOLD = 0.15
_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{1,39}$")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('open','in_progress','resolved','closed','duplicate')),
  priority TEXT NOT NULL CHECK (priority IN ('P0','P1','P2','P3')),
  component TEXT NOT NULL,
  reporter TEXT NOT NULL,
  assignee TEXT NOT NULL DEFAULT '',
  duplicate_of INTEGER REFERENCES tickets(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_id INTEGER NOT NULL REFERENCES tickets(id),
  author TEXT NOT NULL,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


class TicketError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def as_dict(self) -> dict[str, Any]:
        return {"ok": False, "error": {"code": self.code, "message": self.message}}


def _clean(text: str, field: str, min_len: int, max_len: int) -> str:
    value = _CONTROL.sub("", (text or "")).strip()
    if not min_len <= len(value) <= max_len:
        raise TicketError("INVALID_ARGUMENT",
                          f"{field} must be {min_len}-{max_len} characters (got {len(value)}).")
    return value


def _slug(value: str, field: str) -> str:
    value = (value or "").strip().lower()
    if not _SLUG.fullmatch(value):
        raise TicketError("INVALID_ARGUMENT", f"{field} must be a short lowercase slug.")
    return value


def _priority(value: str) -> str:
    value = (value or "").strip().upper()
    if value not in PRIORITIES:
        raise TicketError("INVALID_ARGUMENT", "priority must be one of P0, P1, P2, P3.")
    return value


@dataclass
class TicketStore:
    db_path: Path
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    @contextmanager
    def _connect(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            if write:
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

    def _now(self) -> str:
        return self.clock().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def initialize(self, seed: dict[str, Any], *, reset: bool = False) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if reset and self.db_path.exists():
            self.db_path.unlink()
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(_SCHEMA)
            if conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]:
                return
        with self._connect(write=True) as conn:
            for t in seed["tickets"]:
                conn.execute(
                    "INSERT INTO tickets (id, title, description, status, priority, component,"
                    " reporter, assignee, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (t["id"], t["title"], t["description"], t["status"], t["priority"],
                     t["component"], t["reporter"], t["assignee"], t["created_at"],
                     t["created_at"]))
            for c in seed.get("comments", []):
                conn.execute("INSERT INTO comments (ticket_id, author, body, created_at)"
                             " VALUES (?, ?, ?, ?)",
                             (c["ticket_id"], c["author"], c["body"], c["created_at"]))

    # ------------------------------------------------------------------ reads
    def _all(self, conn: sqlite3.Connection, status: str = "") -> list[sqlite3.Row]:
        if status:
            return conn.execute("SELECT * FROM tickets WHERE status = ?", (status,)).fetchall()
        return conn.execute("SELECT * FROM tickets").fetchall()

    def search(self, query: str, status: str = "", limit: int = 5) -> dict[str, Any]:
        query = _clean(query, "query", 2, 500)
        status = self._status(status) if status else ""
        limit = max(1, min(int(limit), 20))
        with self._connect() as conn:
            rows = {r["id"]: r for r in self._all(conn, status)}
        ranked = rank(query, [(i, f"{r['title']} {r['title']} {r['description']} "
                                  f"{r['component']}") for i, r in rows.items()])
        return {"ok": True, "query": query, "results": [
            self._summary(rows[i]) | {"score": score, "matched_terms": terms}
            for i, score, terms in ranked[:limit]]}

    def get(self, ticket_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            row = self._row(conn, ticket_id)
            comments = conn.execute(
                "SELECT author, body, created_at FROM comments WHERE ticket_id = ? ORDER BY id",
                (row["id"],)).fetchall()
        return {"ok": True, "ticket": dict(row), "comments": [dict(c) for c in comments]}

    def list_tickets(self, status: str = "", priority: str = "", component: str = "",
             limit: int = 10) -> dict[str, Any]:
        sql, params = "SELECT * FROM tickets WHERE 1 = 1", []
        if status:
            sql += " AND status = ?"
            params.append(self._status(status))
        if priority:
            sql += " AND priority = ?"
            params.append(_priority(priority))
        if component:
            sql += " AND component = ?"
            params.append(_slug(component, "component"))
        sql += " ORDER BY priority ASC, updated_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 50)))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return {"ok": True, "tickets": [self._summary(r) for r in rows]}

    def find_duplicates(self, title: str, description: str, limit: int = 5) -> dict[str, Any]:
        title = _clean(title, "title", 3, 160)
        description = _clean(description, "description", 0, 5000)
        with self._connect() as conn:
            rows = {r["id"]: r for r in conn.execute(
                "SELECT * FROM tickets WHERE status != 'duplicate'").fetchall()}
        ranked = rank(f"{title} {title} {description}",
                      [(i, f"{r['title']} {r['title']} {r['description']}")
                       for i, r in rows.items()])
        candidates = [self._summary(rows[i]) | {
            "similarity": score, "matched_terms": terms,
            "likely_duplicate": score >= DUPLICATE_THRESHOLD,
            "related": score >= RELATED_THRESHOLD}
            for i, score, terms in ranked[:max(1, min(int(limit), 10))]]
        return {"ok": True, "threshold": DUPLICATE_THRESHOLD, "candidates": candidates}

    # ------------------------------------------------------------------ writes
    def create(self, title: str, description: str, priority: str, component: str,
               reporter: str = "bug-assistant", allow_duplicate: bool = False) -> dict[str, Any]:
        title = _clean(title, "title", 8, 160)
        description = _clean(description, "description", 20, 5000)
        priority = _priority(priority)
        component = _slug(component, "component")
        reporter = _slug(reporter, "reporter")
        if not allow_duplicate:
            dupes = [c for c in self.find_duplicates(title, description)["candidates"]
                     if c["likely_duplicate"] and c["status"] in {"open", "in_progress"}]
            if dupes:
                return {"ok": False, "created": False, "error": {
                    "code": "POSSIBLE_DUPLICATE",
                    "message": "Similar open tickets exist. Comment on one of them, or retry "
                               "with allow_duplicate=true if the user confirms it is new."},
                    "possible_duplicates": dupes}
        now = self._now()
        with self._connect(write=True) as conn:
            cur = conn.execute(
                "INSERT INTO tickets (title, description, status, priority, component,"
                " reporter, created_at, updated_at) VALUES (?, ?, 'open', ?, ?, ?, ?, ?)",
                (title, description, priority, component, reporter, now, now))
            row = self._row(conn, cur.lastrowid)
        return {"ok": True, "created": True, "ticket": dict(row)}

    def update_status(self, ticket_id: int, status: str, note: str,
                      author: str = "bug-assistant") -> dict[str, Any]:
        status = self._status(status)
        note = _clean(note, "note", 5, 2000)
        with self._connect(write=True) as conn:
            row = self._row(conn, ticket_id)
            if status not in TRANSITIONS[row["status"]]:
                raise TicketError("INVALID_TRANSITION",
                                  f"Cannot move ticket from {row['status']} to {status}.")
            conn.execute("UPDATE tickets SET status = ?, updated_at = ? WHERE id = ?",
                         (status, self._now(), row["id"]))
            self._audit(conn, row["id"], author, f"Status {row['status']} -> {status}: {note}")
            row = self._row(conn, row["id"])
        return {"ok": True, "ticket": dict(row)}

    def update_priority(self, ticket_id: int, priority: str, note: str,
                        author: str = "bug-assistant") -> dict[str, Any]:
        priority = _priority(priority)
        note = _clean(note, "note", 5, 2000)
        with self._connect(write=True) as conn:
            row = self._row(conn, ticket_id)
            conn.execute("UPDATE tickets SET priority = ?, updated_at = ? WHERE id = ?",
                         (priority, self._now(), row["id"]))
            self._audit(conn, row["id"], author,
                        f"Priority {row['priority']} -> {priority}: {note}")
            row = self._row(conn, row["id"])
        return {"ok": True, "ticket": dict(row)}

    def add_comment(self, ticket_id: int, body: str, author: str = "bug-assistant"
                    ) -> dict[str, Any]:
        body = _clean(body, "body", 3, 4000)
        author = _slug(author, "author")
        with self._connect(write=True) as conn:
            row = self._row(conn, ticket_id)
            self._audit(conn, row["id"], author, body)
            conn.execute("UPDATE tickets SET updated_at = ? WHERE id = ?",
                         (self._now(), row["id"]))
        return {"ok": True, "ticket_id": row["id"], "comment": body}

    def mark_duplicate(self, ticket_id: int, duplicate_of: int, note: str,
                       author: str = "bug-assistant") -> dict[str, Any]:
        note = _clean(note, "note", 5, 2000)
        if int(ticket_id) == int(duplicate_of):
            raise TicketError("INVALID_ARGUMENT", "A ticket cannot duplicate itself.")
        with self._connect(write=True) as conn:
            row = self._row(conn, ticket_id)
            original = self._row(conn, duplicate_of)
            if original["status"] == "duplicate":
                raise TicketError("INVALID_ARGUMENT",
                                  f"Ticket {original['id']} is itself a duplicate; link to "
                                  f"ticket {original['duplicate_of']} instead.")
            if "duplicate" not in TRANSITIONS[row["status"]]:
                raise TicketError("INVALID_TRANSITION",
                                  f"Cannot mark a {row['status']} ticket as duplicate.")
            conn.execute("UPDATE tickets SET status = 'duplicate', duplicate_of = ?, "
                         "updated_at = ? WHERE id = ?", (original["id"], self._now(), row["id"]))
            self._audit(conn, row["id"], author, f"Marked duplicate of #{original['id']}: {note}")
            row = self._row(conn, row["id"])
        return {"ok": True, "ticket": dict(row)}

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _status(value: str) -> str:
        value = (value or "").strip().lower()
        if value not in STATUSES:
            raise TicketError("INVALID_ARGUMENT", f"status must be one of {', '.join(STATUSES)}.")
        return value

    @staticmethod
    def _row(conn: sqlite3.Connection, ticket_id: int) -> sqlite3.Row:
        try:
            ticket_id = int(ticket_id)
        except (TypeError, ValueError):
            raise TicketError("INVALID_ARGUMENT", "ticket_id must be an integer.") from None
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            raise TicketError("NOT_FOUND", f"Ticket #{ticket_id} does not exist.")
        return row

    def _audit(self, conn: sqlite3.Connection, ticket_id: int, author: str, body: str) -> None:
        conn.execute("INSERT INTO comments (ticket_id, author, body, created_at) "
                     "VALUES (?, ?, ?, ?)", (ticket_id, author, body, self._now()))

    @staticmethod
    def _summary(row: sqlite3.Row) -> dict[str, Any]:
        return {k: row[k] for k in ("id", "title", "status", "priority", "component",
                                    "assignee", "updated_at")}


def load_seed(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
