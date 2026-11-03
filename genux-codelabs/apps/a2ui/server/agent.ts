import { BASIC_CATALOG_ID } from "@genux/schemas";
import type { ActionMessage } from "@genux/schemas";
import { searchItems } from "@genux/shared";
import type { Item } from "@genux/shared";

/** The mock A2UI "agent". It owns structure and data; the client owns rendering and local input state. */
const V = "v0.9.1" as const;
type Msg = Record<string, unknown>;
const text = (id: string, t: string, variant?: string) => ({ id, component: "Text", text: t, ...(variant ? { variant } : {}) });

export function scenarioMessages(scenario: string): Msg[] {
  const sid = scenario;
  if (scenario === "invalid") {
    return [
      { version: V, createSurface: { surfaceId: sid, catalogId: BASIC_CATALOG_ID } },
      // Not in the catalog: a script-running component. The client must reject it and keep going.
      { version: V, updateComponents: { surfaceId: sid, components: [{ id: "root", component: "ScriptRunner", code: "alert(1)" }] } },
      { version: V, updateComponents: { surfaceId: sid, components: [{ id: "root", component: "Card", child: "msg" }, text("msg", "The stream survived a rejected message. Only valid components rendered.")] } },
    ];
  }
  if (scenario === "contact") {
    return [
      { version: V, createSurface: { surfaceId: sid, catalogId: BASIC_CATALOG_ID, sendDataModel: true } },
      { version: V, updateComponents: { surfaceId: sid, components: [
        { id: "root", component: "Card", child: "col" },
        { id: "col", component: "Column", children: ["title", "name", "email", "topic", "news", "div", "send", "status"] },
        text("title", "# Contact the course team", "h2"),
        { id: "name", component: "TextField", label: "Your name", value: { path: "/form/name" }, checks: [{ call: "required", message: "Name is required." }] },
        { id: "email", component: "TextField", label: "Email", value: { path: "/form/email" }, checks: [{ call: "required", message: "Email is required." }, { call: "email", message: "Enter a valid email." }] },
        { id: "topic", component: "ChoicePicker", variant: "mutuallyExclusive", options: [{ label: "Question", value: "question" }, { label: "Feedback", value: "feedback" }], value: { path: "/form/topic" } },
        { id: "news", component: "CheckBox", label: "Send me updates", value: { path: "/form/news" } },
        { id: "div", component: "Divider" },
        text("send_label", "Send"),
        { id: "send", component: "Button", child: "send_label", variant: "primary", action: { event: { name: "submit_contact", context: { name: { path: "/form/name" }, email: { path: "/form/email" }, topic: { path: "/form/topic" }, news: { path: "/form/news" } } } } },
        text("status", "Not submitted yet.", "caption"),
      ] } },
      { version: V, updateDataModel: { surfaceId: sid, path: "/form", value: { name: "", email: "", topic: ["question"], news: false } } },
    ];
  }
  // "laptops": a search form whose results are produced by the agent after an action.
  return [
    { version: V, createSurface: { surfaceId: sid, catalogId: BASIC_CATALOG_ID, sendDataModel: true } },
    { version: V, updateComponents: { surfaceId: sid, components: [
      { id: "root", component: "Card", child: "col" },
      { id: "col", component: "Column", children: ["title", "budget", "cat", "go", "results"] },
      text("title", "# Find a laptop", "h2"),
      { id: "budget", component: "TextField", label: "Max price (USD)", variant: "number", value: { path: "/q/maxPrice" } },
      { id: "cat", component: "ChoicePicker", variant: "mutuallyExclusive", options: [{ label: "Any", value: "any" }, { label: "Budget", value: "budget" }, { label: "Ultraportable", value: "ultraportable" }, { label: "Performance", value: "performance" }], value: { path: "/q/category" } },
      text("go_label", "Search"),
      { id: "go", component: "Button", child: "go_label", variant: "primary", action: { event: { name: "search_laptops", context: { maxPrice: { path: "/q/maxPrice" }, category: { path: "/q/category" } } } } },
      { id: "results", component: "Column", children: ["hint"] },
      text("hint", "Pick a budget and press Search.", "caption"),
    ] } },
    { version: V, updateDataModel: { surfaceId: sid, path: "/q", value: { maxPrice: "1500", category: ["any"] } } },
  ];
}

/** Agent reaction to a client action: new structure (result rows) and new data, as incremental messages. */
export function handleAction(msg: ActionMessage): Msg[] {
  const { name, surfaceId, context } = msg.action;
  if (name === "submit_contact") {
    const ok = typeof context.email === "string" && /@/.test(context.email) && String(context.name ?? "").trim() !== "";
    return [
      { version: V, updateComponents: { surfaceId, components: [text("status", ok ? `Thanks ${String(context.name).slice(0, 40)}! (agent received: ${JSON.stringify(context)})` : "Please fix the highlighted fields.", "caption")] } },
    ];
  }
  if (name === "search_laptops") {
    const cat = Array.isArray(context.category) ? String(context.category[0]) : String(context.category ?? "any");
    const max = Number(context.maxPrice) || undefined;
    const items: Item[] = searchItems({ maxPrice: max, category: cat === "any" ? undefined : (cat as Item["category"]), limit: 6 });
    const rows = items.flatMap((i) => [text(`r_${i.id}`, `${i.name} · $${i.price} · ${i.rating}★`)]);
    return [
      { version: V, updateComponents: { surfaceId, components: [{ id: "results", component: "Column", children: items.length ? items.map((i) => `r_${i.id}`) : ["none"] }, ...(items.length ? rows : [text("none", "No laptops match.", "caption")])] } },
    ];
  }
  return [{ version: V, updateComponents: { surfaceId, components: [text("status", `Unknown action "${name}" ignored.`, "caption")] } }];
}
