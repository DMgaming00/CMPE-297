import type { ReactNode } from "react";

export type UxMode = "static" | "declarative" | "open-ended" | "mixed";
export const MODE_LABEL: Record<UxMode, string> = { static: "Static", declarative: "Declarative", "open-ended": "Open-ended", mixed: "Mixed" };

export const LABS = [
  { id: "a2ui", label: "A2UI", port: 5171 },
  { id: "agui", label: "AG-UI", port: 5172 },
  { id: "mcp", label: "MCP Apps", port: 5173 },
  { id: "json-render", label: "JSON Render", port: 5174 },
  { id: "openui", label: "OpenUI", port: 5175 },
  { id: "harness", label: "Harness", port: 5176 },
  { id: "mixed", label: "Capstone", port: 5177 },
] as const;

export function ModeBadge({ mode, note }: { mode: UxMode; note?: string }) {
  return <span className={`mode-badge mode-${mode}`} title={note}>{MODE_LABEL[mode]}</span>;
}

export function Shell({ lab, title, subtitle, children, flow }: { lab: (typeof LABS)[number]["id"]; title: string; subtitle: string; children: ReactNode; flow?: string[] }) {
  return (
    <div className="shell">
      <nav className="topnav" aria-label="Labs">
        <strong className="brand">GenUX</strong>
        {LABS.map((l) => (
          <a key={l.id} href={`http://localhost:${l.port}`} className={l.id === lab ? "active" : ""} aria-current={l.id === lab ? "page" : undefined}>{l.label}</a>
        ))}
      </nav>
      <header className="hero">
        <h1>{title}</h1>
        <p className="muted">{subtitle}</p>
        {flow && <Flow steps={flow} />}
      </header>
      <main className="content">{children}</main>
    </div>
  );
}

export function Flow({ steps }: { steps: string[] }) {
  return (
    <ol className="flow" aria-label="Data flow">
      {steps.map((s, i) => <li key={i}>{s}</li>)}
    </ol>
  );
}

export function Panel({ title, mode, aside, children }: { title: string; mode?: UxMode; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>{title}</h2>
        <div className="row-gap">{aside}{mode && <ModeBadge mode={mode} />}</div>
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}

export function Status({ state, label }: { state: "idle" | "loading" | "streaming" | "done" | "error"; label?: string }) {
  return <span className={`status status-${state}`} role="status"><i />{label ?? state}</span>;
}

export function CodeBlock({ children, label }: { children: string; label?: string }) {
  return (
    <figure className="code">
      {label && <figcaption>{label}</figcaption>}
      <pre><code>{children}</code></pre>
    </figure>
  );
}

export interface LogLine { t: string; kind: string; text: string }
export function EventLog({ lines, empty = "No events yet." }: { lines: LogLine[]; empty?: string }) {
  return (
    <ol className="event-log" aria-live="polite">
      {lines.length === 0 && <li className="muted">{empty}</li>}
      {lines.map((l, i) => <li key={i}><time>{l.t}</time> <b className={`k-${l.kind}`}>{l.kind}</b> <span>{l.text}</span></li>)}
    </ol>
  );
}
