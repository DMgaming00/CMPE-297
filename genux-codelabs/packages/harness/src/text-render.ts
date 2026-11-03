import type { Spec } from "@genux/schemas";

/** Terminal surface: the same validated spec drawn as indented text. One spec, two surfaces. */
export function renderSpecText(spec: Spec, id: string = spec.root, indent = 0): string {
  const el = spec.elements[id];
  if (!el) return "";
  const pad = "  ".repeat(indent);
  const kids = () => el.children.map((c) => renderSpecText(spec, c, indent + 1)).join("\n");
  switch (el.type) {
    case "Card": return `${pad}┌ ${el.props.title ?? "Card"}${el.props.description ? ` — ${el.props.description}` : ""}\n${kids()}`;
    case "Stack": return `${pad}${el.props.direction === "row" ? "[row]" : "[col]"}\n${kids()}`;
    case "Text": return `${pad}${el.props.text}`;
    case "Button": return `${pad}( ${el.props.label} ) → ${el.props.action}`;
    case "Badge": return `${pad}<${el.props.label}>`;
    case "Metric": return `${pad}${el.props.label}: ${el.props.value}${el.props.delta ? ` (${el.props.delta})` : ""}`;
    case "Alert": return `${pad}! ${el.props.title ? `${el.props.title}: ` : ""}${el.props.message}`;
    case "Form": return `${pad}[form ${el.props.title ?? ""}] ${el.props.fields.map((f) => f.label).join(", ")} → ${el.props.action}`;
    case "Table": {
      const rows = [el.props.columns, ...el.props.rows.map((r) => r.map(String))];
      const widths = el.props.columns.map((_, c) => Math.max(...rows.map((r) => (r[c] ?? "").length)));
      return rows.map((r) => `${pad}| ${r.map((cell, c) => (cell ?? "").padEnd(widths[c] ?? 0)).join(" | ")} |`).join("\n");
    }
  }
}
