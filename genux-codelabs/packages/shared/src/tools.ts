import type { Item } from "./data";
import { getItemById, ITEMS } from "./data";

/** Pure capability functions. The MCP server, the harness and the mixed-mode agent all wrap these. */
export interface SearchFilters {
  query?: string;
  maxPrice?: number;
  category?: Item["category"];
  limit?: number;
}

export function searchItems({ query = "", maxPrice, category, limit = 5 }: SearchFilters = {}): Item[] {
  const terms = query.toLowerCase().split(/\W+/).filter((t) => t.length > 2 && !STOP.has(t));
  return ITEMS.map((item) => {
    const hay = `${item.name} ${item.brand} ${item.category} ${item.tags.join(" ")} ${item.summary}`.toLowerCase();
    const score = terms.reduce((s, t) => s + (hay.includes(t) ? 1 : 0), 0);
    return { item, score };
  })
    .filter(({ item, score }) => (terms.length === 0 || score > 0) && (maxPrice === undefined || item.price <= maxPrice) && (!category || item.category === category))
    .sort((a, b) => b.score - a.score || b.item.rating - a.item.rating)
    .slice(0, Math.max(1, Math.min(limit, 10)))
    .map(({ item }) => item);
}
const STOP = new Set(["the", "and", "for", "with", "under", "show", "laptop", "laptops", "compare", "best", "dashboard", "help", "choose", "find"]);

export interface Comparison {
  items: Item[];
  winners: { cheapest: string; bestRated: string; longestBattery: string; lightest: string };
}

export function compareItems(ids: string[]): Comparison {
  const items = ids.map((id) => getItemById(id)).filter((i): i is Item => Boolean(i));
  if (items.length < 2) throw new Error("compare_items needs at least two valid item ids");
  const by = (f: (i: Item) => number, dir: 1 | -1) => [...items].sort((a, b) => dir * (f(a) - f(b)))[0]!.id;
  return { items, winners: { cheapest: by((i) => i.price, 1), bestRated: by((i) => i.rating, -1), longestBattery: by((i) => i.batteryHours, -1), lightest: by((i) => i.weightKg, 1) } };
}

export function generateSummary(ids: string[], audience = "student"): string {
  const c = compareItems(ids);
  const n = (id: string) => getItemById(id)!.name;
  return `For a ${audience}: ${n(c.winners.cheapest)} is the cheapest, ${n(c.winners.bestRated)} is rated highest, ${n(c.winners.longestBattery)} lasts longest on battery and ${n(c.winners.lightest)} is the lightest to carry.`;
}
