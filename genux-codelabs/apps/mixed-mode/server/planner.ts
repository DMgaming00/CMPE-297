import { formatIssues, validateSpec } from "@genux/schemas";
import type { Spec } from "@genux/schemas";
import { budgetWidgetHtml, checkDocument, comparisonSpec } from "@genux/shared";
import type { Comparison, Item } from "@genux/shared";

export type RegionMode = "static" | "declarative" | "open-ended";
export type Payload =
  | { kind: "item"; item: Item }
  | { kind: "spec"; spec: Spec }
  | { kind: "html"; title: string; document: string };
export interface Region {
  id: string;
  title: string;
  mode: RegionMode;
  /** Why the planner chose this mode. */
  why: string;
  /** What contains the risk for this mode. */
  guardrail: string;
  payload: Payload;
}
export interface PlanInput {
  prompt: string;
  comparison: Comparison;
  summary: string;
  focusItem?: Item;
}
export interface Plan {
  regions: Region[];
  /** Modes considered and rejected, with the reason. */
  skipped: string[];
}

const NEEDS_CUSTOM_INTERACTION = /budget|plan|calculator|interactive|saving|simulate/i;

/**
 * The UI planning policy. It is ordinary, auditable code — not a model — and it degrades safely:
 * open-ended → declarative → static, never the other way round.
 */
export function planRegions({ prompt, comparison, summary, focusItem }: PlanInput): Plan {
  const regions: Region[] = [];
  const skipped: string[] = [];
  const best = focusItem ?? [...comparison.items].sort((a, b) => b.rating - a.rating)[0]!;

  // 1. Known entity, fixed shape → STATIC. Cheapest, safest, most predictable.
  regions.push({
    id: "top-pick", title: focusItem ? `Selected: ${best.name}` : "Top pick", mode: "static",
    why: "One known entity with a fixed layout: a pre-built ItemCard is enough.",
    guardrail: "Compiled component; the agent supplies data only.",
    payload: { kind: "item", item: best },
  });

  // 2. Variable-size, composed layout → DECLARATIVE, validated against the catalog.
  const validation = validateSpec(comparisonSpec(comparison), { allowedActions: ["select_item"] });
  if (validation.ok && validation.spec) {
    regions.push({
      id: "comparison", title: "Comparison", mode: "declarative",
      why: `${comparison.items.length} items × several attributes: row count and composition vary, so a catalog layout beats fixed code.`,
      guardrail: "Zod catalog + strict props + action allowlist; invalid specs are rejected.",
      payload: { kind: "spec", spec: validation.spec },
    });
  } else {
    skipped.push(`declarative comparison rejected (${formatIssues(validation.issues).slice(0, 120)}); fell back to static top pick only`);
  }

  regions.push({
    id: "summary", title: "Summary", mode: "declarative",
    why: "Generated prose belongs in a catalog Text element, never raw HTML.",
    guardrail: "Rendered as a React text node (auto-escaped).",
    payload: { kind: "spec", spec: textCard("Buying summary", summary) },
  });

  // 3. Needs behaviour the catalog cannot express → OPEN-ENDED, sandboxed. Only when actually requested.
  if (NEEDS_CUSTOM_INTERACTION.test(prompt)) {
    const document = budgetWidgetHtml(comparison.items);
    const problems = checkDocument(document);
    if (problems.length === 0) {
      regions.push({
        id: "planner", title: "Savings planner", mode: "open-ended",
        why: "The request needs live computation (sliders/inputs) with no catalog component: generated HTML is justified.",
        guardrail: "iframe sandbox (no same-origin) + CSP (no network) + document check + message allowlist.",
        payload: { kind: "html", title: "Savings planner", document },
      });
    } else {
      skipped.push(`open-ended planner blocked by document check: ${problems.join("; ")}`);
      regions.push({ id: "planner", title: "Savings planner", mode: "declarative", why: "Open-ended output failed the safety check; degraded to a declarative notice.", guardrail: "Fail closed.", payload: { kind: "spec", spec: textCard("Planner unavailable", "The generated widget was blocked by the safety check.") } });
    }
  } else {
    skipped.push("open-ended skipped: the request needs no custom interaction, so no model-written HTML is generated.");
  }
  return { regions, skipped };
}

function textCard(title: string, text: string): Spec {
  const r = validateSpec({ root: "root", elements: { root: { type: "Card", props: { title }, children: ["t"] }, t: { type: "Text", props: { text } } } });
  return r.spec!;
}
