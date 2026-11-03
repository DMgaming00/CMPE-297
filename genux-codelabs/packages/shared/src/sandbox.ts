/**
 * Open-ended UX safety helpers: model-written HTML never touches the host DOM.
 * It runs in an iframe with `sandbox="allow-scripts"` (no same-origin), under a CSP injected FIRST.
 */
export const SANDBOX_CSP = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'";
export const MAX_DOCUMENT_CHARS = 20_000;

const CHECKS: [RegExp, string][] = [
  [/<iframe|<object|<embed|<frame/i, "nested frames/objects are not allowed"],
  [/<base[\s>]/i, "<base> is not allowed"],
  [/<meta[^>]+http-equiv/i, "meta http-equiv is not allowed"],
  [/<link[^>]+href/i, "external stylesheets are not allowed"],
  [/<script[^>]+src\s*=/i, "external scripts are not allowed"],
  [/(?:src|href)\s*=\s*["']?\s*(?:https?:)?\/\//i, "external URLs are not allowed"],
  [/javascript:/i, "javascript: URLs are not allowed"],
];

/** Pre-flight document check. A failed check blocks rendering; the CSP is the real enforcement. */
export function checkDocument(html: string): string[] {
  const problems: string[] = [];
  if (html.length > MAX_DOCUMENT_CHARS) problems.push(`document too large (${html.length} > ${MAX_DOCUMENT_CHARS} chars)`);
  for (const [re, msg] of CHECKS) if (re.test(html)) problems.push(msg);
  return problems;
}

/** Wrap a document so the CSP precedes any element the model wrote. */
export function buildSandboxDoc(html: string): string {
  const csp = `<meta http-equiv="Content-Security-Policy" content="${SANDBOX_CSP}">`;
  const cleaned = html.replace(/^\s*<!doctype[^>]*>/i, "");
  return `<!doctype html>${csp}${cleaned}`;
}

/** The only messages a sandboxed widget may send to the host. */
export const WIDGET_EVENTS = ["widget_ready", "widget_result", "widget_resize"] as const;
export type WidgetEventName = (typeof WIDGET_EVENTS)[number];
export interface WidgetMessage {
  type: "genux-widget";
  name: WidgetEventName;
  payload?: Record<string, string | number | boolean>;
}
export function parseWidgetMessage(data: unknown): WidgetMessage | null {
  if (typeof data !== "object" || data === null) return null;
  const d = data as Record<string, unknown>;
  if (d.type !== "genux-widget" || typeof d.name !== "string" || !(WIDGET_EVENTS as readonly string[]).includes(d.name)) return null;
  const payload: Record<string, string | number | boolean> = {};
  if (typeof d.payload === "object" && d.payload !== null) {
    for (const [k, v] of Object.entries(d.payload).slice(0, 10)) if (["string", "number", "boolean"].includes(typeof v)) payload[k.slice(0, 40)] = typeof v === "string" ? v.slice(0, 200) : (v as number | boolean);
  }
  return { type: "genux-widget", name: d.name as WidgetEventName, payload };
}
