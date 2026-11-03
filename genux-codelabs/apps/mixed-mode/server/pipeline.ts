/* eslint-disable @typescript-eslint/no-explicit-any -- heterogeneous tool registry: each tool has its own argument type */
import { EventType } from "@ag-ui/core";
import type { BaseEvent } from "@ag-ui/core";
import type { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { z } from "zod";
import { newBridge, runHarness, toAgUi } from "@genux/harness";
import type { ChatMessage, ChatModel, HarnessConfig, ModelResponse, Tool } from "@genux/harness";
import { getItemById, parseBudget, sleep } from "@genux/shared";
import type { Comparison, Item } from "@genux/shared";
import { planRegions } from "./planner";

/** Read-only MCP tools this agent may use. The harness config enforces the same list. */
export const MCP_TOOLS = ["search_items", "get_item_details", "compare_items", "generate_summary"] as const;

interface Ctx {
  prompt: string;
  items: Item[];
  comparison?: Comparison;
  summary?: string;
  focus?: Item;
}

const anyArgs = z.record(z.string(), z.unknown());
const mcpTool = (client: Client, name: string, ctx: Ctx, push: (e: BaseEvent[]) => void): Tool<Record<string, unknown>> => ({
  name,
  description: `MCP tool ${name}`,
  schema: anyArgs,
  run: async (args) => {
    const r = await client.callTool({ name, arguments: args });
    if (r.isError) throw new Error((r.content as { text?: string }[])[0]?.text ?? "MCP tool error");
    const sc = r.structuredContent as { kind: string; items?: Item[]; item?: Item; text?: string } & Partial<Comparison>;
    if (sc.kind === "items") ctx.items = sc.items ?? [];
    if (sc.kind === "comparison") ctx.comparison = { items: sc.items!, winners: sc.winners! };
    if (sc.kind === "summary") ctx.summary = sc.text;
    if (sc.kind === "details") ctx.focus = sc.item;
    push([{ type: EventType.CUSTOM, name: "tool_source", value: { tool: name, source: "mcp" } } as BaseEvent]);
    return { content: JSON.stringify(sc), data: sc };
  },
});

/** The scripted "LLM" for the capstone: the same loop a real model would drive. */
class CapstoneModel implements ChatModel {
  readonly name = "scripted-capstone";
  async complete(messages: ChatMessage[]): Promise<ModelResponse> {
    const u = messages.map((m) => m.role).lastIndexOf("user");
    const prompt = messages[u]?.content ?? "";
    const tools = messages.slice(u + 1).filter((m) => m.role === "tool");
    const n = tools.length;
    const call = (name: string, args: unknown) => ({ toolCalls: [{ id: `call_${n}_${name}`, name, args }] });
    const parse = (name: string) => { try { return JSON.parse(tools.find((t) => t.name === name)?.content ?? "null"); } catch { return null; } };
    if (tools.at(-1)?.content.startsWith("Error:")) return { text: `A step failed: ${tools.at(-1)!.content.slice(0, 120)}`, toolCalls: [] };

    const act = prompt.match(/^\[ui-action\]\s+select_item\s+(\{.*\})/s);
    if (act) {
      const id = (JSON.parse(act[1]!) as { id?: string }).id ?? "";
      if (n === 0) return call("get_item_details", { id });
      if (n === 1) return call("plan_ui", { focus: id });
      return { text: "Updated the top-pick region.", toolCalls: [] };
    }
    if (n === 0) { const max = parseBudget(prompt); return call("search_items", { query: prompt.replace(/\$\s?\d[\d,]*/g, ""), ...(max ? { maxPrice: max } : {}), limit: 4 }); }
    if (n === 1) {
      const items = (parse("search_items")?.items ?? []) as Item[];
      const ids = (items.length >= 2 ? items : [{ id: "air-13" }, { id: "nimbus-14" }, { id: "vertex-13" }]).slice(0, 3).map((i) => i.id);
      return call("compare_items", { ids });
    }
    if (n === 2) return call("generate_summary", { ids: (parse("compare_items")?.items as Item[]).map((i) => i.id) });
    if (n === 3) return call("plan_ui", {});
    return { text: "Done. Each region picked its own UX mode; see the decisions panel.", toolCalls: [] };
  }
}

export interface PipelineInput {
  threadId: string;
  runId: string;
  prompt: string;
  client: Client;
}

/** Request → harness → MCP tools → AG-UI events → UI planning → regions in shared state. */
export async function* runCapstone({ threadId, runId, prompt, client }: PipelineInput): AsyncGenerator<BaseEvent> {
  yield { type: EventType.RUN_STARTED, threadId, runId } as BaseEvent;
  yield { type: EventType.STATE_SNAPSHOT, snapshot: { phase: "gathering data", regions: [], skipped: [] } } as BaseEvent;

  const queue: BaseEvent[] = [];
  const push = (e: BaseEvent[]) => queue.push(...e);
  const ctx: Ctx = { prompt, items: [] };
  const bridge = newBridge(threadId, runId);

  const planUi: Tool<{ focus?: string }> = {
    name: "plan_ui",
    description: "Choose static / declarative / open-ended rendering per region.",
    schema: z.object({ focus: z.string().optional() }),
    run: ({ focus }) => {
      const actionRun = Boolean(focus);
      const focusItem = focus ? ctx.focus ?? getItemById(focus) : undefined;
      if (!actionRun && (!ctx.comparison || !ctx.summary)) throw new Error("plan_ui needs comparison and summary first");
      const plan = planRegions({ prompt: ctx.prompt, comparison: ctx.comparison ?? { items: focusItem ? [focusItem] : [], winners: { cheapest: "", bestRated: "", longestBattery: "", lightest: "" } }, summary: ctx.summary ?? "", focusItem });
      if (actionRun) {
        push([{ type: EventType.STATE_DELTA, delta: [{ op: "replace", path: "/regions/0", value: plan.regions[0] }] } as BaseEvent]);
      } else {
        push([{ type: EventType.STATE_DELTA, delta: [{ op: "replace", path: "/phase", value: "planning UI" }, { op: "replace", path: "/skipped", value: plan.skipped }] } as BaseEvent]);
        for (const r of plan.regions) push([{ type: EventType.STATE_DELTA, delta: [{ op: "add", path: "/regions/-", value: r }] } as BaseEvent]);
        push([{ type: EventType.STATE_DELTA, delta: [{ op: "replace", path: "/phase", value: "done" }] } as BaseEvent]);
      }
      return { content: `Planned ${plan.regions.length} region(s): ${plan.regions.map((r) => `${r.id}=${r.mode}`).join(", ")}` };
    },
  };

  const tools: Tool<any>[] = [...MCP_TOOLS.map((n) => mcpTool(client, n, ctx, push)), planUi];
  const config: HarnessConfig = { maxSteps: 8, allowedTools: [...MCP_TOOLS, "plan_ui"] };
  let done = false;
  const run = runHarness({
    model: new CapstoneModel(), tools, config, messages: [{ role: "user", content: prompt }],
    onEvent: (e) => { if (e.type !== "run_started" && e.type !== "run_finished") push(toAgUi(e, bridge)); },
  }).finally(() => (done = true));

  while (!done || queue.length) {
    const ev = queue.shift();
    if (ev) { yield ev; await sleep(ev.type === EventType.STATE_DELTA ? 280 : 70); } else await sleep(15);
  }
  const result = await run;
  yield (result.ok ? { type: EventType.RUN_FINISHED, threadId, runId } : { type: EventType.RUN_ERROR, message: "harness stopped before finishing" }) as BaseEvent;
}
