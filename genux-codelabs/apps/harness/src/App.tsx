import { useEffect, useRef, useState } from "react";
import { Renderer } from "@openuidev/react-lang";
import type { HarnessEvent, UiPayload } from "@genux/harness";
import { CodeBlock, EventLog, JsonRender, Panel, SandboxedHtml, Shell, Status } from "@genux/ui";
import type { LogLine, UiAction } from "@genux/ui";
import { catalogLibrary, hybridLibrary } from "@genux/ui/openui";

type Target = "json-render" | "openui" | "openui-hybrid";
interface Cfg { model: string; maxSteps: number; tools: string[]; actions: string[]; system: string; provider: string }
const PROMPTS = [
  ["Compare", "compare laptops under $1500"],
  ["Dashboard", "show me a dashboard of the best laptops"],
  ["Widget (open-ended)", "build an interactive budget calculator"],
  ["Invalid UI → self-correct", "render an invalid broken interface"],
  ["Unauthorized tool", "please delete the database"],
] as const;

export function App() {
  const [cfg, setCfg] = useState<Cfg>();
  const [target, setTarget] = useState<Target>("json-render");
  const [allowed, setAllowed] = useState<string[]>([]);
  const [prompt, setPrompt] = useState<string>(PROMPTS[0][1]);
  const [state, setState] = useState<"idle" | "streaming" | "done" | "error">("idle");
  const [log, setLog] = useState<LogLine[]>([]);
  const [ui, setUi] = useState<UiPayload>();
  const [reply, setReply] = useState("");
  const [error, setError] = useState("");
  const [actionLog, setActionLog] = useState<string[]>([]);
  const session = useRef(crypto.randomUUID());
  const t0 = useRef(0);

  useEffect(() => {
    fetch("/api/harness/config").then((r) => r.json()).then((c: Cfg) => { setCfg(c); setAllowed(c.tools); }).catch((e: Error) => setError(e.message));
  }, []);

  const stream = async (payload: Record<string, unknown>) => {
    setState("streaming"); setError(""); t0.current = performance.now();
    const res = await fetch("/api/harness/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sessionId: session.current, ui: target, allowedTools: allowed, ...payload }) });
    if (!res.ok || !res.body) throw new Error(((await res.json().catch(() => ({}))) as { error?: string }).error ?? `HTTP ${res.status}`);
    const reader = res.body.getReader(); const dec = new TextDecoder(); let buf = ""; let finished = false;
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i: number;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const ev = buf.slice(0, i); buf = buf.slice(i + 2);
        if (ev.startsWith("event: done")) { finished = true; continue; }
        const data = ev.split("\n").filter((l) => l.startsWith("data: ")).map((l) => l.slice(6)).join("");
        if (data) onEvent(JSON.parse(data) as HarnessEvent);
      }
    }
    if (!finished) throw new Error("stream ended early");
  };

  const onEvent = (e: HarnessEvent) => {
    const t = `+${((performance.now() - t0.current) / 1000).toFixed(2)}s`;
    const line = (kind: string, text: string) => setLog((l) => [...l, { t, kind, text: text.slice(0, 140) }]);
    switch (e.type) {
      case "run_started": line("run_started", `${e.model} · tools: ${e.tools.length}`); break;
      case "tool_call": line("tool_call", `${e.name} ${JSON.stringify(e.args)}`); break;
      case "tool_result": line("tool_result", `${e.name}: ${e.content}`); break;
      case "tool_error": line("tool_error", `${e.name}: ${e.error.replace(/\n/g, " ")}`); break;
      case "ui": setUi(e.payload); line("ui", e.payload.kind); break;
      case "text": setReply(e.text); line("text", e.text); break;
      case "run_finished": line("run_finished", `${e.steps} step(s)`); break;
      case "run_error": line("run_error", e.message); setError(e.message); break;
    }
  };

  const run = async (payload: Record<string, unknown>, fresh = false) => {
    if (fresh) { setLog([]); setUi(undefined); setReply(""); setActionLog([]); }
    try { await stream(payload); setState("done"); } catch (e) { setError(e instanceof Error ? e.message : "failed"); setState("error"); }
  };
  const onAction = (a: UiAction) => {
    setActionLog((l) => [`${a.name} ${JSON.stringify(a.params ?? {})}`, ...l]);
    void run({ action: a }); // the app validates the action server-side, then starts the next turn
  };

  return (
    <Shell lab="harness" title="Harness integration" subtitle="A coding-agent harness gains a UI output: tools that render validated interfaces. Same loop, three surfaces (web, terminal, AG-UI)."
      flow={["Prompt", "Harness loop", "Model", "Tools (allowlisted)", "render_* output", "Renderer", "User action → next turn"]}>
      <Panel title="Run" aside={<Status state={state} />}>
        <div className="tabs">{PROMPTS.map(([l, p]) => <button key={l} aria-selected={prompt === p} onClick={() => setPrompt(p)}>{l}</button>)}</div>
        <div className="row-gap"><input aria-label="Prompt" value={prompt} maxLength={400} onChange={(e) => setPrompt(e.target.value)} /><button className="btn primary" disabled={state === "streaming" || !cfg} onClick={() => run({ prompt }, true)}>Run</button></div>
        {error && <div className="alert tone-danger" role="alert"><strong>Error</strong><span>{error}</span></div>}
        {reply && <p><strong>agent:</strong> {reply}</p>}
      </Panel>

      <Panel title="Configuration">
        {cfg ? (
          <>
            <p className="muted">model <code>{cfg.model}</code> · provider <code>{cfg.provider}</code> · maxSteps {cfg.maxSteps} (set <code>LLM_PROVIDER</code>, <code>LLM_API_KEY</code> in .env for a real model)</p>
            <label className="field"><span>UI output format the agent uses</span>
              <select value={target} onChange={(e) => setTarget(e.target.value as Target)}>
                <option value="json-render">render_ui · json-render spec (declarative)</option>
                <option value="openui">render_openui · OpenUI Lang (declarative, hosted-harness style)</option>
                <option value="openui-hybrid">render_openui + HtmlArtifact (hybrid)</option>
              </select></label>
            <div><strong>Allowed tools</strong> <span className="muted">(untick one to see the harness refuse it)</span>
              <div className="grid-2">{cfg.tools.map((t) => <label key={t} className="row-gap"><input type="checkbox" style={{ width: "auto" }} checked={allowed.includes(t)} onChange={(e) => setAllowed(e.target.checked ? [...allowed, t] : allowed.filter((x) => x !== t))} /><code>{t}</code></label>)}</div></div>
          </>
        ) : <div className="skeleton" aria-busy="true" />}
      </Panel>

      <Panel title="UI surface (web)" mode={ui?.kind === "html" ? "open-ended" : "declarative"}>
        {state === "streaming" && !ui && <div className="skeleton" aria-busy="true" />}
        {!ui && state !== "streaming" && <p className="muted">The agent's render tool output appears here.</p>}
        {ui?.kind === "json-render" && <JsonRender spec={ui.spec} onAction={onAction} />}
        {ui?.kind === "openui" && <Renderer response={ui.program} library={target === "openui-hybrid" ? hybridLibrary : catalogLibrary} isStreaming={false} onAction={(e) => setActionLog((l) => [`openui action ${JSON.stringify(e).slice(0, 100)}`, ...l])} />}
        {ui?.kind === "html" && <SandboxedHtml title={ui.title} html={ui.document} />}
        {actionLog.length > 0 && <CodeBlock label="actions sent back (closed set, validated server-side)">{actionLog.join("\n")}</CodeBlock>}
      </Panel>

      <Panel title="Harness timeline (events)"><EventLog lines={log} empty="Run a prompt to see tool calls, results and errors." /></Panel>
      <Panel title="Where this runs"><ul>
        <li><strong>Web</strong>: this page (SSE of <code>HarnessEvent</code>s).</li>
        <li><strong>Terminal</strong>: <code>pnpm harness:cli "compare laptops under $1500"</code> draws the same validated spec as text.</li>
        <li><strong>AG-UI</strong>: <code>packages/harness/src/agui-bridge.ts</code> maps each event to AG-UI events (see the AG-UI lab, “From the harness”).</li>
      </ul></Panel>
    </Shell>
  );
}
