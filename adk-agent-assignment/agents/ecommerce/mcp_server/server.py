"""LOCAL MCP server for the e-commerce agent (stdio transport, SQLite storage).

Run standalone:   python -m agents.ecommerce.mcp_server
Inspect:          npx @modelcontextprotocol/inspector python -m agents.ecommerce.mcp_server

The production equivalent is MCP Toolbox for Databases serving
configs/toolbox/ecommerce_tools.yaml against PostgreSQL/AlloyDB.  Tool names and
parameters are intentionally identical so the ADK agent is backend-agnostic.

Identity note: ``user_id`` is a parameter here because stdio has no authentication
channel.  The ADK agent's ``IdentityBinder`` callback overwrites it with the session
identity, so a model-supplied value is never trusted.  In Toolbox mode the identity
comes from a verified Google ID token instead (``authServices``).
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

from .store import CommerceError, CommerceStore, load_seed

logger = get_logger("ecommerce.mcp")

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True,
                            openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False,
                        openWorldHint=False)
CONSEQUENTIAL = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True,
                                openWorldHint=False)


def default_db_path() -> Path:
    return Path(env_str("ECOMMERCE_DB_PATH", str(state_dir() / "ecommerce.sqlite")))


def build_server(store: CommerceStore) -> MCPServer:
    server = MCPServer(
        name="ecommerce-local",
        instructions="Catalog, inventory and user-scoped order tools for a fictional store. "
                     "place_order and cancel_order are consequential and must only be called "
                     "after explicit user confirmation.",
    )

    def tool(annotations: ToolAnnotations) -> Callable[[Callable[..., dict[str, Any]]], Any]:
        def decorator(fn: Callable[..., dict[str, Any]]) -> Any:
            @wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
                try:
                    result = fn(*args, **kwargs)
                except CommerceError as exc:
                    result = exc.as_dict()
                except (TypeError, ValueError) as exc:
                    result = CommerceError("INVALID_ARGUMENT", str(exc)).as_dict()
                log_tool_event(logger, "mcp_tool_call", tool=fn.__name__, args=kwargs,
                               ok=result.get("ok"))
                return result

            return server.tool(annotations=annotations)(wrapper)

        return decorator

    @tool(READ_ONLY)
    def search_products(query: str, category: str = "", max_price: float | None = None,
                        limit: int = 10) -> dict[str, Any]:
        """Search the catalog by natural-language keywords.

        Args:
            query: Keywords such as "waterproof trail shoes".
            category: Optional exact category: footwear, outdoor, fitness, electronics,
                home or apparel.
            max_price: Optional maximum unit price in US dollars.
            limit: Maximum results (1-20).
        """
        return store.search_products(query, category, max_price, limit)

    @tool(READ_ONLY)
    def get_product_details(sku: str) -> dict[str, Any]:
        """Return full details for one product SKU (e.g. FTW-101)."""
        return store.get_product(sku)

    @tool(READ_ONLY)
    def check_inventory(sku: str, store_id: str = "") -> dict[str, Any]:
        """Return stock for a SKU at every store, or at one store_id if given."""
        return store.check_inventory(sku, store_id)

    @tool(READ_ONLY)
    def find_stores(city: str = "") -> dict[str, Any]:
        """List stores, optionally filtered by city. WH-ONLINE ships nationwide."""
        return store.find_stores(city)

    @tool(WRITE)
    def prepare_order(user_id: str, sku: str, quantity: int,
                      store_id: str = "WH-ONLINE") -> dict[str, Any]:
        """Create a non-binding 15-minute quote. Does NOT charge or reserve stock.

        Args:
            user_id: Injected by the platform from the authenticated session.
            sku: Product SKU.
            quantity: Units (1-10).
            store_id: Fulfilling store (default WH-ONLINE).
        """
        return store.prepare_order(user_id, sku, quantity, store_id)

    @tool(CONSEQUENTIAL)
    def place_order(user_id: str, quote_id: str) -> dict[str, Any]:
        """CONSEQUENTIAL: place the order for a prepared quote. Requires user confirmation.

        Idempotent: replaying the same quote_id returns the existing order.
        """
        return store.place_order(user_id, quote_id)

    @tool(READ_ONLY)
    def list_my_orders(user_id: str, limit: int = 10) -> dict[str, Any]:
        """List the authenticated customer's most recent orders."""
        return store.list_orders(user_id, limit)

    @tool(READ_ONLY)
    def get_order_status(user_id: str, order_id: str) -> dict[str, Any]:
        """Return one of the authenticated customer's orders."""
        return store.get_order(user_id, order_id)

    @tool(CONSEQUENTIAL)
    def cancel_order(user_id: str, order_id: str) -> dict[str, Any]:
        """CONSEQUENTIAL: cancel a processing order and restock it. Requires confirmation."""
        return store.cancel_order(user_id, order_id)

    return server


def main() -> None:
    store = CommerceStore(default_db_path())
    store.initialize(load_seed(DATA_DIR / "ecommerce.json"))
    build_server(store).run("stdio")


if __name__ == "__main__":
    main()
