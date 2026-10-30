"""LOCAL MCP bug-tracker server (stdio transport, SQLite storage).

Run standalone:  python -m agents.bug_assistant.mcp_server
Production equivalent: MCP Toolbox serving configs/toolbox/bug_tracker_tools.yaml over
PostgreSQL / Cloud SQL (same tool names).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from adk_shared.config import DATA_DIR, env_str, state_dir
from adk_shared.logging_utils import get_logger, log_tool_event

from .store import TicketError, TicketStore, load_seed

logger = get_logger("bug_tracker.mcp")

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True,
                       openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False,
                        openWorldHint=False)


def default_db_path() -> Path:
    return Path(env_str("BUG_TRACKER_DB_PATH", str(state_dir() / "bug_tracker.sqlite")))


def build_server(store: TicketStore) -> MCPServer:
    server = MCPServer(
        name="bug-tracker-local",
        instructions="Ticket search, duplicate detection and audited ticket updates. Write "
                     "tools (create/update/comment/mark duplicate) need user approval.",
    )

    def tool(annotations: ToolAnnotations) -> Callable[[Callable[..., dict[str, Any]]], Any]:
        def decorator(fn: Callable[..., dict[str, Any]]) -> Any:
            @wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
                try:
                    result = fn(*args, **kwargs)
                except TicketError as exc:
                    result = exc.as_dict()
                except (TypeError, ValueError) as exc:
                    result = TicketError("INVALID_ARGUMENT", str(exc)).as_dict()
                log_tool_event(logger, "mcp_tool_call", tool=fn.__name__, args=kwargs,
                               ok=result.get("ok"))
                return result

            return server.tool(annotations=annotations)(wrapper)

        return decorator

    @tool(READ)
    def search_tickets(query: str, status: str = "", limit: int = 5) -> dict[str, Any]:
        """Full-text search over ticket titles/descriptions, ranked by TF-IDF similarity.

        Args:
            query: Error message, symptom or keywords.
            status: Optional filter: open, in_progress, resolved, closed, duplicate.
            limit: Maximum results (1-20).
        """
        return store.search(query, status, limit)

    @tool(READ)
    def get_ticket(ticket_id: int) -> dict[str, Any]:
        """Return one ticket with its full description and comment history."""
        return store.get(ticket_id)

    @tool(READ)
    def list_tickets(status: str = "", priority: str = "", component: str = "",
                     limit: int = 10) -> dict[str, Any]:
        """List tickets filtered by status, priority (P0-P3) and/or component."""
        return store.list_tickets(status, priority, component, limit)

    @tool(READ)
    def find_duplicate_candidates(title: str, description: str = "",
                                  limit: int = 5) -> dict[str, Any]:
        """Score existing tickets as possible duplicates of a proposed new ticket.

        Candidates with likely_duplicate=true exceed the similarity threshold.
        """
        return store.find_duplicates(title, description, limit)

    @tool(WRITE)
    def create_ticket(title: str, description: str, priority: str, component: str,
                      reporter: str = "bug-assistant",
                      allow_duplicate: bool = False) -> dict[str, Any]:
        """Create a ticket. Refuses likely duplicates unless allow_duplicate is true.

        Args:
            title: 8-160 characters.
            description: 20-5000 characters: symptoms, environment, reproduction steps.
            priority: P0 (critical) .. P3 (low).
            component: Lowercase slug, e.g. checkout, auth, inventory.
            reporter: Lowercase slug of the reporter.
            allow_duplicate: Only true when the user confirmed the ticket is new.
        """
        return store.create(title, description, priority, component, reporter,
                            allow_duplicate)

    @tool(WRITE)
    def update_ticket_status(ticket_id: int, status: str, note: str) -> dict[str, Any]:
        """Change ticket status (validated state machine) and record an audit note."""
        return store.update_status(ticket_id, status, note)

    @tool(WRITE)
    def update_ticket_priority(ticket_id: int, priority: str, note: str) -> dict[str, Any]:
        """Change ticket priority (P0-P3) and record an audit note."""
        return store.update_priority(ticket_id, priority, note)

    @tool(WRITE)
    def add_comment(ticket_id: int, body: str) -> dict[str, Any]:
        """Append a comment (e.g. new reproduction details) to an existing ticket."""
        return store.add_comment(ticket_id, body)

    @tool(WRITE)
    def mark_duplicate(ticket_id: int, duplicate_of: int, note: str) -> dict[str, Any]:
        """Mark ticket_id as a duplicate of duplicate_of, with an audit note."""
        return store.mark_duplicate(ticket_id, duplicate_of, note)

    return server


def main() -> None:
    store = TicketStore(default_db_path())
    store.initialize(load_seed(DATA_DIR / "bug_tickets.json"))
    build_server(store).run("stdio")


if __name__ == "__main__":
    main()
