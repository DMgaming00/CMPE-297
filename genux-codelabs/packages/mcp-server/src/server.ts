import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { compareItems, generateSummary, getItemById, ITEMS, searchItems } from "@genux/shared";
import { VIEW_HTML, VIEW_URI } from "./view";

export const MCP_APP_MIME = "text/html;profile=mcp-app";
export const TOOL_NAMES = ["search_items", "get_item_details", "compare_items", "generate_summary"] as const;

/** Tools that link to the interactive view via `_meta.ui.resourceUri` (the MCP Apps convention). */
const ui = { ui: { resourceUri: VIEW_URI } };
const text = (t: string) => [{ type: "text" as const, text: t }];

export function createItemsServer(): McpServer {
  const server = new McpServer({ name: "genux-items", version: "1.0.0" });

  server.registerTool(
    "search_items",
    { title: "Search items", description: "Search the laptop catalog by text, max price and category.", inputSchema: { query: z.string().max(200).optional(), maxPrice: z.number().positive().optional(), category: z.enum(["ultraportable", "performance", "budget", "creator"]).optional(), limit: z.number().int().min(1).max(10).optional() }, annotations: { readOnlyHint: true }, _meta: ui },
    async (args) => {
      const items = searchItems(args);
      return { content: text(`Found ${items.length} item(s): ${items.map((i) => i.name).join(", ") || "none"}`), structuredContent: { kind: "items", items } };
    },
  );

  server.registerTool(
    "get_item_details",
    { title: "Get item details", description: "Return one laptop by id.", inputSchema: { id: z.string().max(40) }, annotations: { readOnlyHint: true }, _meta: ui },
    async ({ id }) => {
      const item = getItemById(id);
      if (!item) return { isError: true, content: text(`Unknown item id "${id}"`) };
      return { content: text(`${item.name}: $${item.price}, rated ${item.rating}`), structuredContent: { kind: "details", item } };
    },
  );

  server.registerTool(
    "compare_items",
    { title: "Compare items", description: "Compare 2-5 laptops side by side.", inputSchema: { ids: z.array(z.string().max(40)).min(2).max(5) }, annotations: { readOnlyHint: true }, _meta: ui },
    async ({ ids }) => {
      try {
        const c = compareItems(ids);
        return { content: text(`Compared ${c.items.map((i) => i.name).join(" vs ")}`), structuredContent: { kind: "comparison", ...c } };
      } catch (e) {
        return { isError: true, content: text(e instanceof Error ? e.message : "compare failed") };
      }
    },
  );

  server.registerTool(
    "generate_summary",
    { title: "Generate summary", description: "Write a short buying summary for 2-5 laptops.", inputSchema: { ids: z.array(z.string().max(40)).min(2).max(5), audience: z.string().max(40).optional() }, annotations: { readOnlyHint: true }, _meta: ui },
    async ({ ids, audience }) => {
      try {
        const summary = generateSummary(ids, audience);
        return { content: text(summary), structuredContent: { kind: "summary", ids, text: summary } };
      } catch (e) {
        return { isError: true, content: text(e instanceof Error ? e.message : "summary failed") };
      }
    },
  );

  // The UI resource: HTML the host mounts in a sandboxed iframe. CSP is declared (empty = no external origins).
  server.registerResource("items-view", VIEW_URI, { mimeType: MCP_APP_MIME, description: "Interactive view for item tool results" }, async (uri) => ({
    contents: [{ uri: uri.href, mimeType: MCP_APP_MIME, text: VIEW_HTML, _meta: { ui: { csp: { connectDomains: [], resourceDomains: [] }, prefersBorder: true } } }],
  }));

  // A plain data resource (not UI): agents can read the catalog directly.
  server.registerResource("catalog", "items://catalog", { mimeType: "application/json", description: "The full item catalog" }, async (uri) => ({
    contents: [{ uri: uri.href, mimeType: "application/json", text: JSON.stringify(ITEMS) }],
  }));

  return server;
}
