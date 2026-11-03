import { useMemo, useRef, useState } from "react";
import { HttpAgent } from "@ag-ui/client";
import type { AgentSubscriber } from "@ag-ui/client";
import { validateSpec } from "@genux/schemas";
import { EventLog, ItemCard, JsonRender, ModeBadge, Panel, SandboxedHtml, Shell, Status } from "@genux/ui";
import type { LogLine, UiAction } from "@genux/ui";
import type { Item } from "@genux/shared";
import type { Spec } from "@genux/schemas";

type Payload = { kind: "item"; item: Item } | { kind: "spec"; spec: unknown } | { kind: "html"; title: string; document: string };
interface Region { id: string; title: string; mode: "static" | "declarative" | "open-ended"; why: string; guardrail: string; payload: Payload }
interface MixedState { phase?: string; regions?: Region[]; skipped?: string[] }

const PROMPTS = [
  "Help me choose a laptop under $1500 and plan my savings with a budget calculator",
  "Compare the best ultraportable laptops",
];
const STAGES = ["Request", "Harness loop", "MCP tools", "AG-UI stream", "UI planner", "Renderers"] as const;

export function App() {
  const agent = useMemo(() => new HttpAgent({ url: "/api/mixed/agui" }), []);
  const [prompt, setPrompt] = useState(PROMPTS[0]!);
  const [status, setStatus] = useState<"idle" | "streaming" | "done" | "error">("idle");
  const [state, setState] = useState<MixedState>({});
  const [log, setLog] = useState<LogLine[]>([]);
  const [stage, setStage] = useState(-1);
  const [error, setError] = useState("");
  const [tools, setTools] = useState<string[]>([]);
  const [widget, setWidget] = useState("");
  const t0 = useRef(0);

  const subscriber: AgentSubscriber = {
    onEvent: ({ event }) => {
      const e = event as unknown as Record<string, unknown>;
      const type = String(e.type);
      setStage((s) => Math.max(s, type.startsWith("TOOL_CALL") ? 2 : type === "STATE_DELTA" ? 4 : type === "RUN_STARTED" ? 1 : type.startsWith("TEXT") ? 3 : s));
      if (type === "TEXT_MESSAGE_CONTENT" || type === "TOOL_CALL_ARGS") return; // keep the log readable
      const text = e.toolCallName ?? e.name ?? e.message ?? (type === "STATE_DELTA" ? (e.delta as { path: string }[])?.map((d) => d.path).join(",") : "") ?? "";
      setLog((l) => [...l, { t: `+${((performance.now() - t0.current) / 1000).toFixed(2)}s`, kind: type, text: String(text).slice(0, 90) }]);
    },
    onToolCallStartEvent: ({ event }) => setTools((t) => [...t, event.toolCallName]),
    onStateChanged: ({ state: s }) => { setState(structuredClone(s) as MixedState); setStage((x) => Math.max(x, 5)); },
    onRunErrorEvent: ({ event }) => setError(event.message),
  };

  const send = async (text: string, fresh: boolean) => {
    if (status === "streaming") return;
    if (fresh) { agent.setMessages([]); agent.setState({}); setState({}); setLog([]); setTools([]); setStage(0); setWidget(""); }
    agent.addMessage({ id: crypto.randomUUID(), role: "user", content: text });
    setStatus("streaming"); setError(""); t0.current = performance.now();
    try { await agent.runAgent({ runId: crypto.randomUUID() }, subscriber); setStatus("done"); setStage(5); }
    catch (e) { setError(e instanceof Error ? e.message : "run failed"); setStatus("error"); }
  };
  const onAction = (a: UiAction) => {
    if (a.name !== "select_item") return; // the page itself also allowlists actions
    void send(`[ui-action] select_item ${JSON.stringify(a.params ?? {})}`, false);
  };

  const regions = state.regions ?? [];
  return (
    <Shell lab="mixed" title="Capstone: AI shopping research assistant"
      subtitle="One request, three UX modes. A harness drives MCP tools, streams over AG-UI, and a planner picks static, declarative or open-ended rendering for each region."
      flow={[...STAGES]}>
      <Panel title="Ask" aside={<Status state={status} label={state.phase ?? status} />}>
        <div className="tabs">{PROMPTS.map((p) => <button key={p} aria-selected={prompt === p} onClick={() => setPrompt(p)}>{p.length > 38 ? `${p.slice(0, 38)}…` : p}</button>)}</div>
        <div className="row-gap"><input aria-label="Prompt" value={prompt} maxLength={400} onChange={(e) => setPrompt(e.target.value)} /><button className="btn primary" disabled={status === "streaming"} onClick={() => send(prompt, true)}>Run</button></div>
        <ol className="flow" aria-label="Pipeline progress">{STAGES.map((s, i) => <li key={s} style={{ opacity: i <= stage ? 1 : 0.4, borderColor: i === stage ? "var(--accent)" : undefined }}>{s}</li>)}</ol>
        {tools.length > 0 && <p className="muted">MCP tools called: {tools.filter((t) => t !== "plan_ui").map((t) => <span key={t + Math.random()} className="badge">{t}</span>)} then <span className="badge">plan_ui</span></p>}
        {error && <div className="alert tone-danger" role="alert"><strong>Error</strong><span>{error}</span></div>}
      </Panel>

      <div className="wide" style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit,minmax(min(100%,420px),1fr))" }}>
        {status === "streaming" && regions.length === 0 && <Panel title="Working…"><div className="skeleton" aria-busy="true" /><div className="skeleton" style={{ width: "60%" }} /></Panel>}
        {regions.map((r) => (
          <Panel key={r.id} title={r.title} aside={<ModeBadge mode={r.mode} note={r.why} />}>
            <RegionView region={r} onAction={onAction} onWidget={(m) => setWidget(`${m.name} ${JSON.stringify(m.payload ?? {})}`)} />
            <p className="muted" style={{ fontSize: ".82rem" }}><strong>Why:</strong> {r.why}<br /><strong>Guardrail:</strong> {r.guardrail}</p>
          </Panel>
        ))}
      </div>
      {widget && <Panel title="Validated message from the sandboxed widget"><code>{widget}</code></Panel>}

      <Panel title="Planner decisions" mode="mixed">
        {regions.length === 0 ? <p className="muted">Run a request to see the decisions.</p> : (
          <div className="table-wrap"><table className="table"><thead><tr><th>Region</th><th>Mode</th><th>Guardrail</th></tr></thead>
            <tbody>{regions.map((r) => <tr key={r.id}><td>{r.title}</td><td>{r.mode}</td><td style={{ whiteSpace: "normal" }}>{r.guardrail}</td></tr>)}</tbody></table></div>
        )}
        {(state.skipped ?? []).map((s) => <p key={s} className="note">{s}</p>)}
      </Panel>
      <Panel title="AG-UI event stream"><EventLog lines={log} empty="Events appear here." /></Panel>
    </Shell>
  );
}

function RegionView({ region, onAction, onWidget }: { region: Region; onAction: (a: UiAction) => void; onWidget: (m: { name: string; payload?: Record<string, unknown> }) => void }) {
  const p = region.payload;
  if (p.kind === "item") return <ItemCard item={p.item} />;
  if (p.kind === "html") return <SandboxedHtml title={p.title} html={p.document} onMessage={onWidget} />;
  // Never trust the wire: re-validate on the client before rendering.
  const v = validateSpec(p.spec, { allowedActions: ["select_item"] });
  return v.ok && v.spec ? <JsonRender spec={v.spec as Spec} onAction={onAction} /> : <div className="alert tone-danger" role="alert">Region rejected by client validation.</div>;
}
