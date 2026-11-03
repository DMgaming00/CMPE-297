import { classifyIntent, searchItems } from "@genux/shared";

export interface PlannedCall {
  name: string;
  arguments: Record<string, unknown>;
  why: string;
}

/** Stand-in for the model's tool choice. A real host would pass the tool list to an LLM. */
export function planToolCall(prompt: string): PlannedCall {
  const intent = classifyIntent(prompt);
  const hits = searchItems({ query: prompt, limit: 3 });
  const ids = (hits.length >= 2 ? hits : searchItems({ limit: 3 })).map((i) => i.id);
  if (/summar/i.test(prompt)) return { name: "generate_summary", arguments: { ids }, why: "prompt asks for a summary" };
  if (intent === "compare") return { name: "compare_items", arguments: { ids }, why: "prompt asks to compare" };
  const detail = /details?\s+(?:of|for|on)?\s*([a-z]+-\d+)/i.exec(prompt);
  if (detail) return { name: "get_item_details", arguments: { id: detail[1] }, why: "prompt names one item id" };
  const max = /\$\s?(\d[\d,]*)/.exec(prompt)?.[1];
  return { name: "search_items", arguments: { query: prompt.replace(/\$\s?\d[\d,]*/g, ""), ...(max ? { maxPrice: Number(max.replace(/,/g, "")) } : {}), limit: 5 }, why: "default: search" };
}
