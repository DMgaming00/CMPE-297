import { afterAll, beforeAll, describe, expect, it } from "vitest";
import type { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { VIEW_URI, connectInMemory, MCP_APP_MIME } from "@genux/mcp-server";
import { handleViewMessage } from "../apps/mcp-apps/src/bridge";
import { planToolCall } from "../apps/mcp-apps/server/plan";

let client: Client;
let close: () => Promise<void>;
beforeAll(async () => ({ client, close } = await connectInMemory()));
afterAll(async () => close());

describe("MCP Apps server", () => {
  it("lists the four tools, each linked to the ui:// resource", async () => {
    const { tools } = await client.listTools();
    expect(tools.map((t) => t.name).sort()).toEqual(["compare_items", "generate_summary", "get_item_details", "search_items"]);
    for (const t of tools) expect((t._meta as { ui: { resourceUri: string } }).ui.resourceUri).toBe(VIEW_URI);
  });

  it("serves the view as an MCP App HTML resource without innerHTML", async () => {
    const r = await client.readResource({ uri: VIEW_URI });
    const c = r.contents[0]!;
    expect(c.mimeType).toBe(MCP_APP_MIME);
    expect("text" in c && c.text).toContain("ui/initialize");
    expect("text" in c && c.text).not.toContain("innerHTML");
  });

  it("returns text for the model and structuredContent for the view", async () => {
    const r = await client.callTool({ name: "compare_items", arguments: { ids: ["air-13", "nimbus-14"] } });
    expect(r.isError).toBeFalsy();
    expect((r.structuredContent as { kind: string }).kind).toBe("comparison");
    expect((r.content as { text: string }[])[0]!.text).toMatch(/Compared/);
  });

  it("reports tool errors as isError and rejects invalid arguments", async () => {
    expect((await client.callTool({ name: "get_item_details", arguments: { id: "nope" } })).isError).toBe(true);
    await expect(client.callTool({ name: "compare_items", arguments: { ids: ["only-one"] } })).resolves.toMatchObject({ isError: true });
  });

  it("search_items and generate_summary work", async () => {
    const s = await client.callTool({ name: "search_items", arguments: { query: "ultraportable", maxPrice: 1200 } });
    expect((s.structuredContent as { items: { price: number }[] }).items.every((i) => i.price <= 1200)).toBe(true);
    const g = await client.callTool({ name: "generate_summary", arguments: { ids: ["air-13", "vertex-13"] } });
    expect((g.structuredContent as { text: string }).text).toMatch(/cheapest/);
  });
});

describe("host bridge policy", () => {
  const logs: string[] = [];
  const deps = { allowedTools: ["search_items"], callTool: async () => ({ ok: true }), lastToolResult: () => ({ structuredContent: {} }), log: (k: string, t: string) => logs.push(`${k}:${t}`) };
  it("denies tools/call outside the allowlist and answers allowed ones", async () => {
    const denied = await handleViewMessage({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name: "delete_everything" } }, deps);
    expect(JSON.stringify(denied.out)).toContain("not allowed");
    const allowed = await handleViewMessage({ jsonrpc: "2.0", id: 2, method: "tools/call", params: { name: "search_items", arguments: {} } }, deps);
    expect(allowed.out[0]).toMatchObject({ id: 2, result: { ok: true } });
  });
  it("initialize handshake then delivers the tool result; unknown methods error", async () => {
    expect((await handleViewMessage({ jsonrpc: "2.0", id: 3, method: "ui/initialize" }, deps)).out[0]).toHaveProperty("result.hostInfo");
    expect((await handleViewMessage({ jsonrpc: "2.0", method: "ui/notifications/initialized" }, deps)).out[0]).toMatchObject({ method: "ui/notifications/tool-result" });
    expect(JSON.stringify((await handleViewMessage({ jsonrpc: "2.0", id: 4, method: "fs/read" }, deps)).out)).toContain("-32601");
  });
  it("host planner chooses tools", () => {
    expect(planToolCall("compare laptops").name).toBe("compare_items");
    expect(planToolCall("details of vertex-13").arguments).toEqual({ id: "vertex-13" });
  });
});
