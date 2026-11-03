import { useRef, useState } from "react";
import { Renderer } from "@openuidev/react-lang";
import { ITEMS, estimateTokens, openUiProgram, dashboardSpec } from "@genux/shared";
import { CodeBlock, EventLog, Panel, SandboxedHtml, Shell, Status } from "@genux/ui";
import type { LogLine, UxMode } from "@genux/ui";
import { catalogLibrary, hybridLibrary, PROMPT_OPTIONS } from "@genux/ui/openui";

const TABS = ["Static", "Declarative", "Open-ended", "Hybrid"] as const;
type Tab = (typeof TABS)[number];
const MODE: Record<Tab, UxMode> = { Static: "static", Declarative: "declarative", "Open-ended": "open-ended", Hybrid: "mixed" };
const STATIC_PROGRAM = openUiProgram(ITEMS.slice(0, 5));

async function generate(prompt: string, mode: string, onDelta: (t: string) => void): Promise<void> {
  const res = await fetch("/api/openui/generate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt, mode }) });
  if (!res.ok || !res.body) throw new Error(`server answered ${res.status}`);
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) throw new Error("stream ended without a done event"); // never treat a truncated program as complete
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const ev = buf.slice(0, i); buf = buf.slice(i + 2);
      if (ev.startsWith("event: done")) return;
      const data = ev.split("\n").filter((l) => l.startsWith("data: ")).map((l) => l.slice(6)).join("\n");
      if (data) onDelta(JSON.parse(data) as string);
    }
  }
}

export function App() {
  const [tab, setTab] = useState<Tab>("Declarative");
  return (
    <Shell lab="openui" title="OpenUI Lang" subtitle="A compact, line-oriented language for model-generated UI (@openuidev/lang-core + @openuidev/react-lang). Statements are `id = Component(args)`; references may point forward so the UI can paint while the stream is still arriving."
      flow={["Model streams OpenUI Lang", "Streaming parser", "Resolve + validate (Zod)", "React Renderer", "Components"]}>
      <div className="wide tabs" role="tablist">{TABS.map((t) => <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>{t}</button>)}</div>
      {tab === "Static" && <StaticTab />}
      {tab === "Declarative" && <StreamTab key="d" mode="declarative" start="show me a dashboard of laptops under $1500" hybrid={false} />}
      {tab === "Hybrid" && <StreamTab key="h" mode="hybrid" start="build an interactive budget calculator" hybrid />}
      {tab === "Open-ended" && <OpenEndedTab />}
      <Panel title={`UX mode: ${tab}`} mode={MODE[tab]}><Compare /></Panel>
    </Shell>
  );
}

function StaticTab() {
  return (
    <>
      <Panel title="A hand-written OpenUI program" mode="static"><Renderer response={STATIC_PROGRAM} library={catalogLibrary} isStreaming={false} /></Panel>
      <Panel title="The program (no model involved)"><CodeBlock label="program.oui">{STATIC_PROGRAM}</CodeBlock><p className="muted">Static usage: a developer authors the program, the library renders it. Useful for fixtures and tests of the catalog.</p></Panel>
    </>
  );
}

function StreamTab({ mode, start, hybrid }: { mode: string; start: string; hybrid: boolean }) {
  const [prompt, setPrompt] = useState(start);
  const [program, setProgram] = useState("");
  const [state, setState] = useState<"idle" | "streaming" | "done" | "error">("idle");
  const [error, setError] = useState("");
  const [log, setLog] = useState<LogLine[]>([]);
  const t0 = useRef(0);
  const lib = hybrid ? hybridLibrary : catalogLibrary;

  const run = async (m = mode, p = prompt) => {
    setProgram(""); setError(""); setState("streaming"); setLog([]); t0.current = performance.now();
    let acc = "";
    try {
      await generate(p, m, (d) => { acc += d; setProgram(acc); });
      setState("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed"); setState("error");
    }
  };
  const specTokens = estimateTokens(JSON.stringify(dashboardSpec(ITEMS.slice(0, 6))));

  return (
    <>
      <Panel title="Prompt" mode={hybrid ? "mixed" : "declarative"} aside={<Status state={state} />}>
        <div className="row-gap"><input aria-label="Prompt" value={prompt} onChange={(e) => setPrompt(e.target.value)} /><button className="btn primary" disabled={state === "streaming"} onClick={() => run()}>Generate</button></div>
        <div className="row-gap" style={{ flexWrap: "wrap" }}>
          <button className="btn" disabled={state === "streaming"} onClick={() => { setPrompt("dashboard of laptops"); run(hybrid ? "hybrid" : "declarative", "dashboard of laptops"); }}>Catalog-only request</button>
          <button className="btn" disabled={state === "streaming"} onClick={() => run("bad", "broken output")}>Malformed model output</button>
        </div>
        {error && <div className="alert tone-danger" role="alert"><strong>Stream failed</strong><span>{error}</span></div>}
        <p className="muted">≈{estimateTokens(program)} tokens (chars/4 estimate) for this OpenUI program; a comparable json-render element map for a similar dashboard is ≈{specTokens}. Illustrative only: different generators, not a benchmark.</p>
      </Panel>
      <Panel title="Rendered (re-parsed on every chunk)">
        {state === "streaming" && !program && <div className="skeleton" aria-busy="true" />}
        {program && <Renderer response={program} library={lib} isStreaming={state === "streaming"} onAction={(e) => setLog((l) => [...l, { t: `+${((performance.now() - t0.current) / 1000).toFixed(1)}s`, kind: "action", text: JSON.stringify(e).slice(0, 120) }])} />}
      </Panel>
      <Panel title="Raw OpenUI Lang stream"><CodeBlock>{program || "…"}</CodeBlock></Panel>
      <Panel title="Actions back to the app"><EventLog lines={log} empty="Click a Button in the rendered UI." /></Panel>
      <Panel title="System prompt generated from the catalog"><CodeBlock label="library.prompt(options)">{lib.prompt(PROMPT_OPTIONS)}</CodeBlock></Panel>
    </>
  );
}

function OpenEndedTab() {
  const [html, setHtml] = useState("");
  const [state, setState] = useState<"idle" | "streaming" | "done" | "error">("idle");
  const [error, setError] = useState("");
  const run = async (prompt: string) => {
    setHtml(""); setError(""); setState("streaming");
    let acc = "";
    try { await generate(prompt, "open-ended", (d) => { acc += d; setHtml(acc); }); setState("done"); } catch (e) { setError(e instanceof Error ? e.message : "failed"); setState("error"); }
  };
  return (
    <>
      <Panel title="Model-written HTML, no catalog" mode="open-ended" aside={<Status state={state} />}>
        <div className="row-gap"><button className="btn primary" disabled={state === "streaming"} onClick={() => run("budget calculator")}>Generate widget</button><button className="btn" disabled={state === "streaming"} onClick={() => run("hostile escape attempt")}>Generate hostile widget</button></div>
        {error && <div className="alert tone-danger" role="alert"><strong>Failed</strong><span>{error}</span></div>}
        {state === "streaming" && <pre>{html}</pre>}
        {state === "done" && <SandboxedHtml title="generated" html={html} />}
        <p className="note">Maximum flexibility, minimum guarantees. The document check blocks nested frames and external URLs before rendering; the iframe sandbox + CSP stop everything else (network, parent DOM, cookies). Try the hostile widget.</p>
      </Panel>
      <Panel title="Raw HTML"><CodeBlock>{html || "…"}</CodeBlock></Panel>
    </>
  );
}

function Compare() {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead><tr><th>Versus</th><th>OpenUI Lang is…</th></tr></thead>
        <tbody>
          <tr><td>A2UI</td><td>A UI <em>language</em> with its own compact syntax and Zod catalog; A2UI is a JSON message protocol (surface / components / data model) with actions and a spec-defined catalog.</td></tr>
          <tr><td>AG-UI</td><td>Content, not transport. OpenUI Lang text can ride on AG-UI text or custom events.</td></tr>
          <tr><td>MCP Apps</td><td>No host or iframe contract. MCP Apps ships a finished HTML view; OpenUI describes UI the host app renders itself.</td></tr>
          <tr><td>JSON Render</td><td>Same idea (catalog-constrained), different representation: line-oriented, positional, forward references vs a JSON element map.</td></tr>
          <tr><td>Arbitrary generated code</td><td>Cannot run code. Anything outside the catalog is dropped; HtmlArtifact is an explicit, sandboxed exception.</td></tr>
        </tbody>
      </table>
    </div>
  );
}
