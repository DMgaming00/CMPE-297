import { z } from "zod";

/**
 * The JSON Render catalog: the ONLY components a model may use, and the exact props each accepts.
 * Every schema is `.strict()` so unknown props (style, onClick, dangerouslySetInnerHTML, ...) are rejected.
 */
export const TONES = ["neutral", "success", "warning", "danger", "info"] as const;
export type Tone = (typeof TONES)[number];

const tone = z.enum(TONES);
const cell = z.union([z.string().max(500), z.number()]);
const actionName = z.string().regex(/^[a-z][a-z0-9_]{0,40}$/, "action must be snake_case");
const actionParams = z.record(z.string().max(40), z.union([z.string().max(200), z.number(), z.boolean()]));

export const fieldSchema = z
  .object({
    name: z.string().regex(/^[a-zA-Z][a-zA-Z0-9_]{0,30}$/),
    label: z.string().max(80),
    type: z.enum(["text", "email", "number", "select"]),
    options: z.array(z.string().max(80)).max(20).optional(),
    required: z.boolean().optional(),
    placeholder: z.string().max(80).optional(),
  })
  .strict();

export const propSchemas = {
  Card: z.object({ title: z.string().max(120).optional(), description: z.string().max(300).optional() }).strict(),
  Stack: z.object({ direction: z.enum(["row", "column"]).optional(), gap: z.enum(["s", "m", "l"]).optional() }).strict(),
  Text: z.object({ text: z.string().max(2000), variant: z.enum(["body", "heading", "muted"]).optional() }).strict(),
  Button: z
    .object({ label: z.string().max(80), action: actionName, params: actionParams.optional(), variant: z.enum(["primary", "secondary"]).optional() })
    .strict(),
  Badge: z.object({ label: z.string().max(60), tone: tone.optional() }).strict(),
  Metric: z.object({ label: z.string().max(80), value: z.union([z.string().max(80), z.number()]), delta: z.string().max(40).optional(), tone: tone.optional() }).strict(),
  Table: z.object({ columns: z.array(z.string().max(80)).min(1).max(12), rows: z.array(z.array(cell).max(12)).max(100) }).strict(),
  Alert: z.object({ title: z.string().max(120).optional(), message: z.string().max(1000), tone: tone.optional() }).strict(),
  Form: z
    .object({ title: z.string().max(120).optional(), fields: z.array(fieldSchema).min(1).max(12), submitLabel: z.string().max(40).optional(), action: actionName })
    .strict(),
} as const;

export type ComponentType = keyof typeof propSchemas;
export const COMPONENT_TYPES = Object.keys(propSchemas) as ComponentType[];
/** Only these catalog components may have children. */
export const CONTAINER_TYPES: ReadonlySet<string> = new Set(["Card", "Stack"]);

export type Props<K extends ComponentType> = z.infer<(typeof propSchemas)[K]>;
export type ValidElement = { [K in ComponentType]: { type: K; props: Props<K>; children: string[] } }[ComponentType];
export interface Spec {
  root: string;
  elements: Record<string, ValidElement>;
}

/** Loose wire shape the model emits: a flat element map joined by ids (the json-render / A2UI shape). */
export const rawSpecSchema = z.object({
  root: z.string().min(1).max(64),
  elements: z.record(
    z.string().max(64),
    z.object({ type: z.string(), props: z.record(z.string(), z.unknown()).optional(), children: z.array(z.string()).optional() }),
  ),
});

export interface ValidationIssue {
  elementId?: string;
  path: string;
  message: string;
}
export interface ValidationResult {
  ok: boolean;
  spec?: Spec;
  issues: ValidationIssue[];
}
export interface ValidateOptions {
  /** Drop invalid elements and replace them with a warning Alert instead of rejecting the whole spec. */
  lenient?: boolean;
  /** If set, Button/Form actions must be in this list. */
  allowedActions?: readonly string[];
  maxElements?: number;
  maxDepth?: number;
}

const placeholder = (id: string, reason: string): ValidElement => ({
  type: "Alert",
  props: { tone: "warning", title: "Invalid element removed", message: `${id}: ${reason}`.slice(0, 300) },
  children: [],
});

/**
 * Validate untrusted model output against the catalog.
 * Strict mode (default) fails closed: any issue → `ok: false`, no spec.
 * Lenient mode keeps the valid parts and swaps each invalid element for a visible placeholder.
 */
export function validateSpec(input: unknown, options: ValidateOptions = {}): ValidationResult {
  const { lenient = false, allowedActions, maxElements = 200, maxDepth = 12 } = options;
  const issues: ValidationIssue[] = [];
  const raw = rawSpecSchema.safeParse(input);
  if (!raw.success) {
    return { ok: false, issues: raw.error.issues.map((i) => ({ path: i.path.join("."), message: i.message })) };
  }
  const { root, elements } = raw.data;
  const ids = Object.keys(elements);
  if (ids.length > maxElements) return { ok: false, issues: [{ path: "elements", message: `too many elements (${ids.length} > ${maxElements})` }] };
  if (!(root in elements)) return { ok: false, issues: [{ path: "root", message: `root element "${root}" does not exist` }] };

  const out: Record<string, ValidElement> = {};
  for (const id of ids) {
    const el = elements[id];
    if (!el) continue;
    const fail = (message: string, path = `elements.${id}`) => {
      issues.push({ elementId: id, path, message });
      out[id] = placeholder(id, message);
    };
    if (!(el.type in propSchemas)) {
      fail(`unknown component "${el.type}" (allowed: ${COMPONENT_TYPES.join(", ")})`, `elements.${id}.type`);
      continue;
    }
    const type = el.type as ComponentType;
    const parsed = propSchemas[type].safeParse(el.props ?? {});
    if (!parsed.success) {
      fail(parsed.error.issues.map((i) => `${i.path.join(".") || "props"}: ${i.message}`).join("; "), `elements.${id}.props`);
      continue;
    }
    const children = el.children ?? [];
    if (children.length && !CONTAINER_TYPES.has(type)) {
      fail(`${type} cannot have children`, `elements.${id}.children`);
      continue;
    }
    const missing = children.filter((c) => !(c in elements));
    if (missing.length) {
      issues.push({ elementId: id, path: `elements.${id}.children`, message: `unknown child id(s): ${missing.join(", ")}` });
    }
    const action = (parsed.data as { action?: string }).action;
    if (action && allowedActions && !allowedActions.includes(action)) {
      fail(`action "${action}" is not allowed`, `elements.${id}.props.action`);
      continue;
    }
    out[id] = { type, props: parsed.data, children: children.filter((c) => c in elements) } as ValidElement;
  }

  // Structural pass: cycles and depth, from the root only.
  const visiting = new Set<string>();
  const walk = (id: string, depth: number): void => {
    if (depth > maxDepth) {
      issues.push({ elementId: id, path: "tree", message: `nesting deeper than ${maxDepth}` });
      return;
    }
    if (visiting.has(id)) {
      issues.push({ elementId: id, path: "tree", message: "cycle detected" });
      return;
    }
    visiting.add(id);
    const el = out[id];
    if (el) {
      const safe: string[] = [];
      for (const c of el.children) {
        if (visiting.has(c)) {
          issues.push({ elementId: id, path: `elements.${id}.children`, message: `cycle through "${c}" removed` });
        } else safe.push(c);
      }
      el.children = safe;
      safe.forEach((c) => walk(c, depth + 1));
    }
    visiting.delete(id);
  };
  walk(root, 0);

  if (issues.length && !lenient) return { ok: false, issues };
  return { ok: true, spec: { root, elements: out }, issues };
}

/** Format issues for a model-facing tool error (the correction loop). */
export const formatIssues = (issues: ValidationIssue[]): string => issues.map((i) => `- ${i.path}: ${i.message}`).join("\n");
