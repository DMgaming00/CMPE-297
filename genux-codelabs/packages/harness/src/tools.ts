/* eslint-disable @typescript-eslint/no-explicit-any -- heterogeneous tool registry: each tool has its own argument type */
import { z } from "zod";
import { formatIssues, validateSpec } from "@genux/schemas";
import { checkDocument, compareItems, generateSummary, getItemById, searchItems } from "@genux/shared";
import type { Tool } from "./types";

export const UI_ACTIONS = ["select_item", "refine_search", "compare_selected"] as const;

const search = z.object({ query: z.string().max(200).optional(), maxPrice: z.number().positive().optional(), category: z.enum(["ultraportable", "performance", "budget", "creator"]).optional(), limit: z.number().int().min(1).max(10).optional() });
const ids = z.object({ ids: z.array(z.string()).min(2).max(5) });

export const dataTools: Tool<any>[] = [
  { name: "search_items", description: "Search laptops by text, max price and category.", schema: search, run: (a) => { const items = searchItems(a); return { content: JSON.stringify({ items }), data: items }; } },
  {
    name: "get_item_details",
    description: "Get one laptop by id.",
    schema: z.object({ id: z.string() }),
    run: ({ id }) => {
      const item = getItemById(id);
      if (!item) throw new Error(`unknown item id "${id}"`);
      return { content: JSON.stringify(item), data: item };
    },
  },
  { name: "compare_items", description: "Compare 2-5 laptops by id.", schema: ids, run: ({ ids }) => { const c = compareItems(ids); return { content: JSON.stringify(c), data: c }; } },
  { name: "generate_summary", description: "Write a short buying summary for 2-5 laptop ids.", schema: ids, run: ({ ids }) => ({ content: generateSummary(ids) }) },
];

/** render_ui: the model submits a declarative spec; the harness validates before any surface sees it. */
export const renderUiTool: Tool<{ spec: unknown }> = {
  name: "render_ui",
  description: "Show an interface. `spec` is a flat element map {root, elements:{id:{type,props,children}}} using only the catalog components.",
  schema: z.object({ spec: z.unknown() }),
  run: ({ spec }) => {
    const result = validateSpec(spec, { allowedActions: UI_ACTIONS });
    if (!result.ok || !result.spec) throw new Error(`render_ui spec rejected:\n${formatIssues(result.issues)}\nFix these and call render_ui again.`);
    return { content: `Rendered ${Object.keys(result.spec.elements).length} elements.`, ui: { kind: "json-render", spec: result.spec } };
  },
};

/** render_openui: the "hosted harness" shape — the agent answers with an OpenUI Lang program. */
export const renderOpenUiTool: Tool<{ program: string }> = {
  name: "render_openui",
  description: "Show an interface written in OpenUI Lang (one `id = Component(args)` statement per line, root = ...).",
  schema: z.object({ program: z.string().min(8).max(20_000) }),
  run: ({ program }) => {
    if (!/^\s*root\s*=/m.test(program)) throw new Error("program must define `root = ...`");
    return { content: `Rendered OpenUI program (${program.split("\n").length} lines).`, ui: { kind: "openui", program } };
  },
};

/** Open-ended escape hatch, still gated: document check here, sandbox + CSP at the surface. */
export const renderHtmlTool: Tool<{ title: string; document: string }> = {
  name: "render_html_artifact",
  description: "Show a self-contained interactive HTML widget (inline CSS/JS only). It runs in a sandbox with no network.",
  schema: z.object({ title: z.string().max(80), document: z.string().min(1) }),
  run: ({ title, document }) => {
    const problems = checkDocument(document);
    if (problems.length) throw new Error(`document rejected: ${problems.join("; ")}`);
    return { content: `Rendered sandboxed widget "${title}".`, ui: { kind: "html", title, document } };
  },
};

export const defaultTools: Tool<any>[] = [...dataTools, renderUiTool, renderOpenUiTool, renderHtmlTool];
export const DEFAULT_ALLOWED = defaultTools.map((t) => t.name);
