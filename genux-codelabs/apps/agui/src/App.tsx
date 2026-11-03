import { useMemo, useRef, useState } from "react";
import { HttpAgent } from "@ag-ui/client";
import type { AgentSubscriber } from "@ag-ui/client";
import { validateSpec } from "@genux/schemas";
import { ITEMS } from "@genux/shared";
import { CodeBlock, EventLog, ItemCard, JsonRender, Panel, SandboxedHtml, Shell, Status } from "@genux/ui";
import type { LogLine, UxMode } from "@genux/ui";

type Demo = "static" | "declarative" | "open-ended" | "approval" | "harness";
const DEMOS: { id: Demo; label: string; mode: UxMode; blurb: string }[] = [
  { id: "static", label: "Tool call → component", mode: "static", blurb: "A tool name maps to a component compiled into the app." },
  { id: "declarative", label: "State patch → spec", mode: "declarative", blurb: "A STATE_DELTA delivers a validated UI spec." },
  { id: "open-ended", label: "CUSTOM → sandbox", mode: "open-ended", blurb: "A CUSTOM event carries HTML into a sandboxed iframe." },
  { id: "approval", label: "Frontend tool (approval)", mode: "static", blurb: "The run pauses on a tool call the user must answer." },
  { id: "harness", label: "From the harness", mode: "declarative", blurb: "The harness loop's callbacks bridged to AG-UI events." },
];
interface Pending { id: string; args: { plan?: string } }

export function App() {
  const agent = useMemo(() => new HttpAgent({ url: "/api/agui" }), []);
  const [demo, setDemo] = useState<Demo>("static");
  const [status, setStatus] = useState<"idle" | "streaming" | "done" | "error">("idle");
  const [log, setLog] = useState<LogLine[]>([]);
  const [text, setText] = useState("");
  const [state, setState] = useState<Record<string, unknown>>({});
  const [tools, setTools] = useState<{ id: string; name: string; args: string }[]>([]);
  const [artifact, setArtifact] = useState<{ title: string; document: string } | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [error, setError] = useState("");
  const t0 = useRef(0);
  const argBuf = useRef<Record<string, { name: string; args: string }>>({});

  const subscriber: AgentSubscriber = {
    onEvent: ({ event }) => {
      const e = event as unknown as Record<string, unknown>;
      const brief = e.delta ?? e.toolCallName ?? e.name ?? e.stepName ?? e.message ?? "";
      setLog((l) => [...l, { t: `+${((performance.now() - t0.current) / 1000).toFixed(2)}s`, kind: String(e.type), text: String(typeof brief === "string" ? brief : JSON.stringify(brief)).slice(0, 80) }]);
    },
    onTextMessageContentEvent: ({ event }) => setText((t) => t + event.delta),
    onToolCallStartEvent: ({ event }) => { argBuf.current[event.toolCallId] = { name: event.toolCallName, args: "" }; },
    onToolCallArgsEvent: ({ event }) => { const b = argBuf.current[event.toolCallId]; if (b) b.args += event.delta; },
    onToolCallEndEvent: ({ event }) => {
      const b = argBuf.current[event.toolCallId];
      if (b) setTools((t) => [...t, { id: event.toolCallId, ...b }]);
    },
    onStateChanged: ({ state: s }) => setState(structuredClone(s) as Record<string, unknown>),
    onCustomEvent: ({ event }) => {
      if (event.name === "html_artifact") {
        const v = event.value as { title?: unknown; document?: unknown };
        if (typeof v?.title === "string" && typeof v?.document === "string") setArtifact({ title: v.title, document: v.document });
      }
    },
    onRunFinishedEvent: (p) => {
      const id = p.outcome === "success" ? p.pendingToolCallIds[0] : undefined;
      const b = id ? argBuf.current[id] : undefined;
      if (id && b?.name === "confirm_plan") { try { setPending({ id, args: JSON.parse(b.args) as Pending["args"] }); } catch { setPending({ id, args: {} }); } }
    },
    onRunErrorEvent: ({ event }) => setError(event.message),
  };

  const run = async (next: Demo, reset = true) => {
    if (status === "streaming") return;
    if (reset) {
      agent.setMessages([]); agent.setState({});
      setLog([]); setText(""); setState({}); setTools([]); setArtifact(null); setPending(null); argBuf.current = {};
      agent.addMessage({ id: crypto.randomUUID(), role: "user", content: next === "harness" ? "compare laptops under $1500" : `demo ${next}` });
    }
    setDemo(next); setError(""); setStatus("streaming"); t0.current = performance.now();
    try {
      await agent.runAgent({ runId: crypto.randomUUID(), forwardedProps: { demo: next } }, subscriber);
      setStatus("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "run failed"); setStatus("error");
    }
  };

  const answer = async (verdict: "approved" | "declined") => {
    if (!pending) return;
    agent.addMessage({ id: crypto.randomUUID(), role: "tool", toolCallId: pending.id, content: verdict });
    setPending(null);
    await run("approval", false);
  };

  const uiState = (state.ui ?? undefined) as unknown;
  const validated = uiState ? validateSpec(uiState) : undefined;
  const current = DEMOS.find((d) => d.id === demo)!;

  return (
    <Shell lab="agui" title="AG-UI" subtitle="The agent ⇄ frontend event protocol: typed, streamed events for text, tool calls, state and custom payloads. Built on the official @ag-ui/client, @ag-ui/core and @ag-ui/encoder."
      flow={["User", "Frontend (HttpAgent)", "POST RunAgentInput", "Agent", "SSE events", "Frontend state + UI"]}>
      <Panel title="Choose a run" aside={<Status state={status} />}>
        <div className="tabs" role="tablist">{DEMOS.map((d) => <button key={d.id} role="tab" aria-selected={demo === d.id} disabled={status === "streaming"} onClick={() => run(d.id)}>{d.label}</button>)}</div>
        <p className="muted">{current.blurb} <span className={`mode-badge mode-${current.mode}`}>{current.mode}</span></p>
        <p className="note">AG-UI is the <em>transport</em>: it does not decide static vs declarative vs open-ended. Each run here carries a different UI payload over the same event types.</p>
        {error && <div className="alert tone-danger" role="alert"><strong>Run failed</strong><span>{error}</span></div>}
      </Panel>

      <Panel title="Agent output (streamed)" mode={current.mode}>
        {status === "streaming" && !text && <div className="skeleton" aria-busy="true" />}
        <p aria-live="polite" style={{ minHeight: 24 }}>{text}{status === "streaming" && <span className="muted"> ▍</span>}</p>
        {tools.filter((t) => t.name === "show_item_card").map((t) => {
          const id = (JSON.parse(t.args) as { id?: string }).id;
          const item = ITEMS.find((i) => i.id === id);
          return item ? <ItemCard key={t.id} item={item} /> : null;
        })}
        {validated && !validated.ok && <div className="alert tone-danger" role="alert"><strong>Spec in state rejected</strong></div>}
        {validated?.ok && validated.spec && <><Status state="done" label={`state.ui validated · progress ${String(state.progress ?? "")}%`} /><JsonRender spec={validated.spec} /></>}
        {artifact && <SandboxedHtml title={artifact.title} html={artifact.document} />}
        {pending && (
          <div className="alert tone-warning" role="alertdialog" aria-label="Approval needed">
            <strong>Frontend tool: confirm_plan</strong>
            <span>{pending.args.plan ?? "Approve this plan?"}</span>
            <div className="row-gap"><button className="btn primary" onClick={() => answer("approved")}>Approve</button><button className="btn" onClick={() => answer("declined")}>Decline</button></div>
          </div>
        )}
        {Array.isArray(state.shortlist) && <ul>{(state.shortlist as string[]).map((s) => <li key={s}>{s}</li>)}</ul>}
      </Panel>

      <Panel title="Event lifecycle"><EventLog lines={log} empty="Pick a run. RUN_STARTED → … → RUN_FINISHED appears here." /></Panel>
      <Panel title="Shared state (snapshots + JSON Patch)"><CodeBlock label="agent.state, maintained by @ag-ui/client">{JSON.stringify(state, (k, v) => (k === "elements" ? "{…}" : v), 2)}</CodeBlock></Panel>
    </Shell>
  );
}
