import { classifyIntent, openUiProgram, parseBudget, BROKEN_SPEC, budgetWidgetHtml, comparisonSpec, dashboardSpec, itemDetailSpec, openUiHybridProgram } from "@genux/shared";
import type { Comparison, Item } from "@genux/shared";
import type { ChatMessage, ChatModel, ModelResponse } from "./types";

export type UiTarget = "json-render" | "openui" | "openui-hybrid";

const call = (n: number, name: string, args: unknown) => ({ id: `call_${n}_${name}`, name, args });
const parse = <T,>(m: ChatMessage | undefined): T | undefined => {
  if (!m || m.content.startsWith("Error:")) return undefined;
  try {
    return JSON.parse(m.content) as T;
  } catch {
    return undefined;
  }
};

/**
 * Deterministic stand-in for an LLM so every demo runs offline. It is a small state machine over the transcript:
 * it reads previous tool results, so it exercises the same loop (including error correction) as a real model.
 */
export class ScriptedModel implements ChatModel {
  readonly name: string;
  constructor(private readonly target: UiTarget = "json-render") {
    this.name = `scripted-mock(${target})`;
  }

  async complete(messages: ChatMessage[]): Promise<ModelResponse> {
    const u = messages.map((m) => m.role).lastIndexOf("user");
    const prompt = messages[u]?.content ?? "";
    const tools = messages.slice(u + 1).filter((m) => m.role === "tool");
    const n = tools.length;
    const last = tools[n - 1];
    const lastFailed = last?.content.startsWith("Error:") ?? false;
    const find = (name: string) => tools.filter((t) => t.name === name).at(-1);
    const intent = classifyIntent(prompt);
    const budget = parseBudget(prompt);
    const search = () => call(n, "search_items", { query: intent === "broken" ? "" : prompt.replace(/\$\s?\d[\d,]*/g, ""), ...(budget ? { maxPrice: budget } : {}), limit: 6 });
    const items = () => parse<{ items: Item[] }>(find("search_items"))?.items ?? [];
    const renderOverview = (list: Item[]) =>
      this.target === "json-render"
        ? call(n, "render_ui", { spec: dashboardSpec(list) })
        : call(n, "render_openui", { program: this.target === "openui-hybrid" ? openUiHybridProgram(list) : openUiProgram(list) });
    const done = (text: string): ModelResponse => ({ text, toolCalls: [] });
    const go = (...c: ReturnType<typeof call>[]): ModelResponse => ({ toolCalls: c });

    switch (intent) {
      case "compare": {
        if (n === 0) return go(search());
        if (n === 1) {
          const list = items();
          const pick = (list.length >= 2 ? list : [{ id: "air-13" }, { id: "nimbus-14" }]).slice(0, 3).map((i) => i.id);
          return go(call(n, "compare_items", { ids: pick }));
        }
        if (n === 2) {
          const c = parse<Comparison>(find("compare_items"));
          if (!c) return done("I could not compare those items.");
          return this.target === "json-render" ? go(call(n, "render_ui", { spec: comparisonSpec(c) })) : go(call(n, "render_openui", { program: openUiProgram(c.items) }));
        }
        return done(lastFailed ? `The interface was rejected: ${last?.content.slice(0, 160)}` : "Here is a side-by-side comparison. Click a button to open one laptop's details.");
      }
      case "dashboard": {
        if (n === 0) return go(search());
        if (n === 1) return go(renderOverview(items()));
        return done(lastFailed ? "The interface was rejected." : `Found ${items().length} laptops. The dashboard is above; use the form to refine.`);
      }
      case "widget": {
        if (n === 0) return go(search());
        if (n === 1) return go(call(n, "render_html_artifact", { title: "Budget calculator", document: budgetWidgetHtml(items().length ? items() : []) }));
        return done(lastFailed ? "The widget was rejected by the safety check." : "I built an interactive budget calculator. It runs in a sandbox with no network access.");
      }
      case "broken": {
        if (n === 0) return go(call(n, "render_ui", { spec: BROKEN_SPEC }));
        if (n === 1 && lastFailed) return go(search());
        if (n === 2) return go(call(n, "render_ui", { spec: dashboardSpec(items()) }));
        return done("My first interface was rejected by validation, so I corrected it and rendered a valid one.");
      }
      case "forbidden": {
        if (n === 0) return go(call(n, "delete_database", { confirm: true }));
        return done("That tool is not permitted for this agent, so nothing was changed.");
      }
      case "action": {
        const m = prompt.match(/^\[ui-action\]\s+(\w+)\s*(\{.*\})?/s);
        const name = m?.[1];
        let params: Record<string, unknown> = {};
        try {
          params = m?.[2] ? (JSON.parse(m[2]) as Record<string, unknown>) : {};
        } catch { /* malformed params are treated as empty */ }
        if (name === "select_item") {
          if (n === 0) return go(call(n, "get_item_details", { id: String(params.id ?? "") }));
          if (n === 1 && !lastFailed) return go(call(n, "render_ui", { spec: itemDetailSpec(parse<Item>(last)!) }));
          return done(lastFailed ? `Could not open that item (${last?.content}).` : "Opened the item details.");
        }
        if (name === "refine_search") {
          const max = Number(params.maxPrice) || undefined;
          const category = typeof params.category === "string" && params.category !== "any" ? params.category : undefined;
          if (n === 0) return go(call(n, "search_items", { ...(max ? { maxPrice: max } : {}), ...(category ? { category } : {}), limit: 6 }));
          if (n === 1) return go(renderOverview(items()));
          return done("Refined the shortlist.");
        }
        return done(`I don't know the action "${name ?? "?"}", so I ignored it.`);
      }
      default:
        return done("I can compare laptops, build a shortlist dashboard, or make a budget calculator. Try: \"compare laptops under $1500\".");
    }
  }
}
