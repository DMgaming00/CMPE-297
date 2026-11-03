import { useSyncExternalStore } from "react";
import type { ReactNode } from "react";
import type { SurfaceStore } from "./store";

type Send = (action: ReturnType<SurfaceStore["buildAction"]>) => void;

/** Native renderer for the A2UI Basic Catalog subset. Structure comes from components; values come from the data model. */
export function SurfaceView({ store, surfaceId, onAction }: { store: SurfaceStore; surfaceId: string; onAction: Send }) {
  useSyncExternalStore(store.subscribe, () => store.version);
  const surface = store.get(surfaceId);
  if (!surface) return null;
  if (!surface.components.has("root")) return <div className="skeleton" aria-busy="true" aria-label="Waiting for components" />;

  const text = (v: unknown): string => {
    const r = store.resolve(surfaceId, v);
    return r === undefined || r === null ? "" : Array.isArray(r) ? r.join(", ") : String(r);
  };

  const node = (id: string, depth = 0): ReactNode => {
    const c = surface.components.get(id);
    if (!c) return <div key={id} className="skeleton" aria-busy="true" />; // forward reference still streaming
    if (depth > 20) return null;
    const kids = (ids: string[]) => ids.map((k) => <div key={k} className="jr-child" style={{ flex: surface.components.get(k) && "weight" in surface.components.get(k)! ? (surface.components.get(k) as { weight?: number }).weight : undefined }}>{node(k, depth + 1)}</div>);
    switch (c.component) {
      case "Text": {
        const v = c.variant ?? "body";
        const content = text(c.text).replace(/^#+\s*/, ""); // markdown headings only; text is never HTML
        return v.startsWith("h") ? <h3>{content}</h3> : <p className={v === "caption" ? "muted" : ""}>{content}</p>;
      }
      case "Column": return <div className="stack column gap-m">{kids(c.children)}</div>;
      case "Row": return <div className="stack row gap-m" style={{ alignItems: c.align === "center" ? "center" : "stretch" }}>{kids(c.children)}</div>;
      case "Card": return <section className="card">{node(c.child, depth + 1)}</section>;
      case "Divider": return <hr style={{ width: "100%", border: 0, borderTop: "1px solid var(--line)" }} />;
      case "TextField": {
        const path = (c.value as { path?: string }).path;
        const value = text(c.value);
        const problem = (c.checks ?? []).find((chk) => {
          if (chk.call === "required") return value.trim() === "";
          if (chk.call === "email") return value !== "" && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value);
          if (chk.call === "regex") { try { return value !== "" && !new RegExp(String(chk.args?.pattern ?? "")).test(value); } catch { return true; } }
          return false;
        });
        return (
          <label className="field">
            <span>{text(c.label)}</span>
            {c.variant === "longText" ? (
              <textarea value={value} onChange={(e) => path && store.setValue(surfaceId, path, e.target.value)} />
            ) : (
              <input type={c.variant === "number" ? "number" : c.variant === "obscured" ? "password" : "text"} value={value} onChange={(e) => path && store.setValue(surfaceId, path, e.target.value)} aria-invalid={Boolean(problem)} />
            )}
            {problem && <small className="tone-danger">{problem.message}</small>}
          </label>
        );
      }
      case "CheckBox": {
        const path = (c.value as { path?: string }).path;
        return (
          <label className="row-gap"><input type="checkbox" style={{ width: "auto" }} checked={Boolean(store.resolve(surfaceId, c.value))} onChange={(e) => path && store.setValue(surfaceId, path, e.target.checked)} />{text(c.label)}</label>
        );
      }
      case "ChoicePicker": {
        const cur = store.resolve(surfaceId, c.value);
        const selected = Array.isArray(cur) ? (cur as string[]) : cur ? [String(cur)] : [];
        const multi = c.variant === "multipleSelection";
        return (
          <div className="tabs" role="group">
            {c.options.map((o) => (
              <button type="button" key={o.value} aria-selected={selected.includes(o.value)} onClick={() => store.setValue(surfaceId, c.value.path, multi ? (selected.includes(o.value) ? selected.filter((s) => s !== o.value) : [...selected, o.value]) : [o.value])}>{o.label}</button>
            ))}
          </div>
        );
      }
      case "Button": {
        const ev = c.action.event;
        return <button type="button" className={`btn ${c.variant === "primary" ? "primary" : ""}`} onClick={() => onAction(store.buildAction(surfaceId, c.id, ev.name, ev.context))}>{node(c.child, depth + 1)}</button>;
      }
    }
  };
  return <>{node("root")}</>;
}
