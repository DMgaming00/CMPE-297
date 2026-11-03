import { a2uiMessageSchema } from "@genux/schemas";
import type { A2uiComponent, A2uiMessage } from "@genux/schemas";

export interface Surface {
  id: string;
  catalogId: string;
  sendDataModel: boolean;
  components: Map<string, A2uiComponent>;
  data: Record<string, unknown>;
}
type Listener = () => void;

/** Parse "/a/b/0" JSON Pointer into segments (RFC 6901 escapes). */
const segs = (path: string) => path.split("/").slice(1).map((s) => s.replace(/~1/g, "/").replace(/~0/g, "~"));
const FORBIDDEN = new Set(["__proto__", "constructor", "prototype"]);

export function getAt(data: unknown, path: string): unknown {
  let cur: unknown = data;
  for (const s of segs(path)) {
    if (typeof cur !== "object" || cur === null) return undefined;
    cur = (cur as Record<string, unknown>)[s];
  }
  return cur;
}
export function setAt(data: Record<string, unknown>, path: string, value: unknown): void {
  const parts = segs(path);
  if (parts.length === 0) return;
  if (parts.some((p) => FORBIDDEN.has(p))) throw new Error("forbidden path segment");
  let cur: Record<string, unknown> = data;
  for (const p of parts.slice(0, -1)) {
    const next = cur[p];
    if (typeof next !== "object" || next === null) cur[p] = {};
    cur = cur[p] as Record<string, unknown>;
  }
  cur[parts[parts.length - 1]!] = value;
}

/**
 * Client-side state for A2UI surfaces. This is the "client responsibility" half of the protocol:
 * validate each envelope, keep structure (components) and state (data model) separate, resolve bindings.
 */
export class SurfaceStore {
  private surfaces = new Map<string, Surface>();
  private listeners = new Set<Listener>();
  version = 0;

  subscribe = (l: Listener) => {
    this.listeners.add(l);
    return () => this.listeners.delete(l);
  };
  private emit() {
    this.version++;
    this.listeners.forEach((l) => l());
  }
  list(): Surface[] {
    return [...this.surfaces.values()];
  }
  get(id: string): Surface | undefined {
    return this.surfaces.get(id);
  }

  /** Returns an error string for a rejected message; the stream continues either way. */
  process(raw: unknown): string | undefined {
    const parsed = a2uiMessageSchema.safeParse(raw);
    if (!parsed.success) return parsed.error.issues.slice(0, 3).map((i) => `${i.path.join(".")}: ${i.message}`).join("; ");
    const msg: A2uiMessage = parsed.data;
    try {
      if ("createSurface" in msg) {
        const { surfaceId, catalogId, sendDataModel } = msg.createSurface;
        if (this.surfaces.has(surfaceId)) return `surface "${surfaceId}" already exists`;
        this.surfaces.set(surfaceId, { id: surfaceId, catalogId, sendDataModel: Boolean(sendDataModel), components: new Map(), data: {} });
      } else if ("updateComponents" in msg) {
        const s = this.surfaces.get(msg.updateComponents.surfaceId);
        if (!s) return `unknown surface "${msg.updateComponents.surfaceId}"`;
        for (const c of msg.updateComponents.components) s.components.set(c.id, c);
      } else if ("updateDataModel" in msg) {
        const s = this.surfaces.get(msg.updateDataModel.surfaceId);
        if (!s) return `unknown surface "${msg.updateDataModel.surfaceId}"`;
        const { path = "/", value } = msg.updateDataModel;
        if (path === "/") s.data = (value && typeof value === "object" ? structuredClone(value) : {}) as Record<string, unknown>;
        else setAt(s.data, path, structuredClone(value));
      } else {
        this.surfaces.delete(msg.deleteSurface.surfaceId);
      }
    } catch (e) {
      return e instanceof Error ? e.message : "failed to apply message";
    }
    this.emit();
    return undefined;
  }

  /** Two-way binding: user edits write straight into the local data model. */
  setValue(surfaceId: string, path: string, value: unknown) {
    const s = this.surfaces.get(surfaceId);
    if (!s) return;
    setAt(s.data, path, value);
    this.emit();
  }

  /** Literal or {path} → concrete value, read at the moment it is needed. */
  resolve(surfaceId: string, v: unknown): unknown {
    if (typeof v === "object" && v !== null && "path" in v) return getAt(this.surfaces.get(surfaceId)?.data, String((v as { path: string }).path));
    return v;
  }

  /** Build the client → server `action` message; context bindings resolve at click time. */
  buildAction(surfaceId: string, sourceComponentId: string, name: string, context: Record<string, unknown> = {}) {
    const s = this.surfaces.get(surfaceId);
    const resolved = Object.fromEntries(Object.entries(context).map(([k, v]) => [k, this.resolve(surfaceId, v)]));
    return {
      version: "v0.9.1" as const,
      action: { name, surfaceId, sourceComponentId, timestamp: new Date().toISOString(), context: resolved },
      ...(s?.sendDataModel ? { dataModel: { version: "v0.9.1", surfaces: { [surfaceId]: s.data } } } : {}),
    };
  }
}
