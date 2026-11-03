import type { Plugin } from "vite";
import type { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { connectInMemory, VIEW_URI } from "@genux/mcp-server";
import { readJsonBody, sendJson } from "@genux/shared/node";
import { planToolCall } from "./plan";

/**
 * Node side of the MCP *host*: owns the MCP client, the tool allowlist and the resource policy.
 * The browser never talks to the MCP server directly.
 */
export const HOST_ALLOWED_TOOLS = ["search_items", "get_item_details", "compare_items", "generate_summary"];
const ALLOWED_RESOURCES = new Set([VIEW_URI]);

export function mcpHostApi(): Plugin {
  let clientP: Promise<Client> | undefined;
  const client = () => (clientP ??= connectInMemory().then((c) => c.client));
  return {
    name: "mcp-host-api",
    configureServer(server) {
      server.middlewares.use("/api/mcp/tools", async (_req, res) => {
        const { tools } = await (await client()).listTools();
        const { resources } = await (await client()).listResources();
        sendJson(res, 200, { allowed: HOST_ALLOWED_TOOLS, tools: tools.map((t) => ({ name: t.name, description: t.description, inputSchema: t.inputSchema, _meta: t._meta })), resources });
      });
      server.middlewares.use("/api/mcp/plan", async (req, res) => {
        const body = (await readJsonBody(req).catch(() => ({}))) as { prompt?: unknown };
        if (typeof body.prompt !== "string" || body.prompt.length > 300) return sendJson(res, 400, { error: "prompt required (max 300 chars)" });
        sendJson(res, 200, planToolCall(body.prompt));
      });
      server.middlewares.use("/api/mcp/call", async (req, res) => {
        const body = (await readJsonBody(req).catch(() => ({}))) as { name?: unknown; arguments?: unknown; origin?: unknown };
        if (typeof body.name !== "string" || !HOST_ALLOWED_TOOLS.includes(body.name)) {
          return sendJson(res, 403, { error: `host policy: tool "${String(body.name).slice(0, 40)}" is not allowed` });
        }
        try {
          const result = await (await client()).callTool({ name: body.name, arguments: (body.arguments ?? {}) as Record<string, unknown> });
          sendJson(res, 200, result);
        } catch (e) {
          sendJson(res, 500, { error: e instanceof Error ? e.message : "tool call failed" });
        }
      });
      server.middlewares.use("/api/mcp/resource", async (req, res) => {
        const uri = new URL(req.url ?? "", "http://x").searchParams.get("uri") ?? "";
        if (!ALLOWED_RESOURCES.has(uri)) return sendJson(res, 403, { error: "host policy: resource not allowed" });
        const r = await (await client()).readResource({ uri });
        const c = r.contents[0];
        sendJson(res, 200, { uri, mimeType: c?.mimeType, html: c && "text" in c ? c.text : "", meta: c?._meta });
      });
    },
  };
}
