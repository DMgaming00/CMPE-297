import { useEffect, useMemo, useRef, useState } from "react";
import { CodeBlock, EventLog, Panel, Shell, Status } from "@genux/ui";
import type { LogLine } from "@genux/ui";
import { SurfaceStore } from "./a2ui/store";
import { SurfaceView } from "./a2ui/Surface";

type Scenario = "contact" | "laptops" | "invalid";
const TABS = ["Static", "Declarative", "Open-ended", "Mixed"] as const;
type Tab = (typeof TABS)[number];

export function App() {
  const [tab, setTab] = useState<Tab>("Declarative");
  return (
    <Shell lab="a2ui" title="A2UI" subtitle="Agent-to-UI: an agent streams a declarative description of a UI (components + data model); the client renders it with its own native components."
      flow={["Agent", "createSurface", "updateComponents", "updateDataModel", "Client renders", "action → Agent"]}>
      <div className="wide tabs" role="tablist">{TABS.map((t) => <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>{t}</button>)}</div>
      {tab === "Static" && <StaticTab />}
      {tab === "Declarative" && <DeclarativeTab />}
      {tab === "Open-ended" && <Panel title="Open-ended UX is deliberately not part of A2UI"><p className="note">A2UI is a safe-by-construction format: agents may only reference components in a catalog the client already trusts, and there is no field for code or markup. That is the point of the protocol, so we do not fake an open-ended mode here. A client could register a custom catalog entry that wraps a sandboxed iframe; that hybrid is shown in apps/openui (HtmlArtifact) and apps/mixed-mode.</p></Panel>}
      {tab === "Mixed" && <Panel title="Mixed UX lives in the capstone"><p className="note">A2UI is the declarative layer. The combined static + declarative + open-ended app is apps/mixed-mode.</p></Panel>}
    </Shell>
  );
}

function StaticTab() {
  const [form, setForm] = useState({ name: "", email: "" });
  const [sent, setSent] = useState(false);
  return (
    <>
      <Panel title="Hand-written contact form" mode="static">
        <label className="field"><span>Your name</span><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label className="field"><span>Email</span><input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
        <button className="btn primary" onClick={() => setSent(true)}>Send</button>
        {sent && <p className="muted">Submitted {JSON.stringify(form)}</p>}
      </Panel>
      <Panel title="Baseline for comparison" mode="static">
        <p>This is the same form as the A2UI <em>contact</em> scenario, but compiled into the app. Changing a field means a code change and a deploy. In A2UI the agent sends the form as data.</p>
      </Panel>
    </>
  );
}

function DeclarativeTab() {
  const store = useMemo(() => new SurfaceStore(), []);
  const [scenario, setScenario] = useState<Scenario>("contact");
  const [state, setState] = useState<"idle" | "streaming" | "done" | "error">("idle");
  const [log, setLog] = useState<LogLine[]>([]);
  const [raw, setRaw] = useState<string[]>([]);
  const [, bump] = useState(0);
  const src = useRef<EventSource | null>(null);
  const note = (kind: string, text: string) => setLog((l) => [...l, { t: new Date().toLocaleTimeString(), kind, text }]);

  const start = (s: Scenario) => {
    src.current?.close();
    store.process({ version: "v0.9.1", deleteSurface: { surfaceId: s } }); // fresh run: delete first (a repeated createSurface is an error)
    setScenario(s); setLog([]); setRaw([]); setState("streaming");
    const es = new EventSource(`/api/a2ui/stream?scenario=${s}`);
    src.current = es;
    es.onmessage = (e) => {
      if (e.data === "done") { es.close(); setState("done"); return; }
      setRaw((r) => [...r, e.data]);
      let parsed: unknown;
      try { parsed = JSON.parse(e.data); } catch { note("rejected", "not JSON"); return; }
      const err = store.process(parsed);
      const kind = Object.keys(parsed as object).find((k) => k !== "version") ?? "?";
      if (err) note("rejected", `${kind}: ${err}`);
      else note(kind, "applied");
      bump((n) => n + 1);
    };
    es.onerror = () => { es.close(); setState((cur) => (cur === "done" ? cur : "error")); };
  };
  useEffect(() => { start("contact"); return () => src.current?.close(); }, []);

  const onAction = async (action: ReturnType<SurfaceStore["buildAction"]>) => {
    note("action →", `${action.action.name} ${JSON.stringify(action.action.context)}`);
    try {
      const res = await fetch("/api/a2ui/action", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(action) });
      if (!res.ok) throw new Error(`server answered ${res.status}`);
      const { messages } = (await res.json()) as { messages: unknown[] };
      for (const m of messages) {
        const err = store.process(m);
        if (err) note("rejected", err);
        else note("← update", "applied");
      }
      bump((n) => n + 1);
    } catch (e) { note("error", e instanceof Error ? e.message : "action failed"); }
  };

  const surface = store.get(scenario);
  return (
    <>
      <Panel title="Rendered surface" mode="declarative" aside={<Status state={state === "idle" ? "idle" : state} />}>
        <div className="tabs" role="group" aria-label="Scenario">
          {(["contact", "laptops", "invalid"] as const).map((s) => <button key={s} aria-selected={scenario === s} onClick={() => start(s)}>{s === "invalid" ? "invalid message" : s}</button>)}
        </div>
        {state === "streaming" && !surface && <div className="skeleton" aria-busy="true" />}
        {surface && <SurfaceView store={store} surfaceId={scenario} onAction={onAction} />}
      </Panel>
      <Panel title="Protocol log (agent ⇄ client)"><EventLog lines={log} empty="Waiting for the stream…" /></Panel>
      <Panel title="Raw server → client messages"><CodeBlock label="one JSON envelope per SSE event">{raw.join("\n") || "…"}</CodeBlock></Panel>
      <Panel title="Client data model (state)"><CodeBlock label="separate from structure; edits write here, bindings read from here">{JSON.stringify(surface?.data ?? {}, null, 2)}</CodeBlock></Panel>
    </>
  );
}
