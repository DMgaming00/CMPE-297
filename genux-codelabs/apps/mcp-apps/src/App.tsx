import { useEffect, useRef, useState } from "react";
import { HOSTILE_VIEW } from "./hostile";
import { CodeBlock, EventLog, Panel, Shell, Status } from "@genux/ui";
import type { LogLine } from "@genux/ui";
import { McpFrame } from "./McpFrame";

const ALLOWED = ["search_items", "get_item_details", "compare_items", "generate_summary"];
const PROMPTS = ["compare laptops under $1500", "search ultraportable laptops", "details of vertex-13", "summarize the best laptops"];
interface ToolInfo { name: string; description?: string; _meta?: { ui?: { resourceUri?: string } } }
interface Call { name: string; arguments: Record<string, unknown>; why: string }
interface ToolResult { content?: { type: string; text?: string }[]; structuredContent?: unknown; isError?: boolean }

async function api<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, body === undefined ? undefined : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(((await res.json().catch(() => ({}))) as { error?: string }).error ?? `HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export function App() {
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [prompt, setPrompt] = useState(PROMPTS[0]!);
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [call, setCall] = useState<Call>();
  const [result, setResult] = useState<ToolResult>();
  const [html, setHtml] = useState<string>();
  const [hostile, setHostile] = useState(false);
  const [error, setError] = useState("");
  const [log, setLog] = useState<LogLine[]>([]);
  const lastResult = useRef<unknown>({});
  const viewHtml = useRef<string | undefined>(undefined);
  const add = (kind: string, text: string) => setLog((l) => [...l, { t: new Date().toLocaleTimeString(), kind, text }]);

  useEffect(() => { api<{ tools: ToolInfo[] }>("/api/mcp/tools").then((r) => setTools(r.tools)).catch((e: Error) => setError(e.message)); }, []);

  const deps = {
    allowedTools: ALLOWED,
    callTool: (name: string, args: Record<string, unknown>) => api<ToolResult>("/api/mcp/call", { name, arguments: args }),
    lastToolResult: () => lastResult.current,
    log: add,
  };

  const run = async () => {
    setState("loading"); setError(""); setHostile(false); setResult(undefined); setHtml(undefined);
    try {
      const planned = await api<Call>("/api/mcp/plan", { prompt });
      setCall(planned); add("model → host", `call ${planned.name} (${planned.why})`);
      const tool = tools.find((t) => t.name === planned.name);
      const res = await api<ToolResult>("/api/mcp/call", { name: planned.name, arguments: planned.arguments });
      setResult(res); lastResult.current = res; add("server → host", `result${res.isError ? " (isError)" : ""}`);
      const uri = tool?._meta?.ui?.resourceUri;
      if (uri) {
        if (!viewHtml.current) viewHtml.current = (await api<{ html: string }>(`/api/mcp/resource?uri=${encodeURIComponent(uri)}`)).html;
        add("host", `mounted ${uri} in a sandboxed iframe`);
        setHtml(viewHtml.current);
      }
      setState("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed"); setState("error"); add("error", e instanceof Error ? e.message : "failed");
    }
  };

  return (
    <Shell lab="mcp" title="MCP Apps" subtitle="Tools return structured results plus a ui:// resource. The host mounts that HTML in a sandbox and relays a JSON-RPC bridge. Server built with the official @modelcontextprotocol/sdk."
      flow={["User", "Host + MCP Client", "MCP Server tool", "Structured result", "ui:// resource", "Sandboxed view"]}>
      <Panel title="Host: ask for something" aside={<Status state={state} />}>
        <div className="row-gap" style={{ flexWrap: "wrap" }}>{PROMPTS.map((p) => <button key={p} className="btn" onClick={() => setPrompt(p)}>{p}</button>)}</div>
        <div className="row-gap"><input aria-label="Prompt" value={prompt} maxLength={300} onChange={(e) => setPrompt(e.target.value)} /><button className="btn primary" disabled={state === "loading"} onClick={run}>Run</button></div>
        {error && <div className="alert tone-danger" role="alert"><strong>Error</strong><span>{error}</span></div>}
        {call && <CodeBlock label="1. the model picks a tool (host validates it against its allowlist)">{JSON.stringify({ name: call.name, arguments: call.arguments }, null, 2)}</CodeBlock>}
        {result && <CodeBlock label="2. what the MODEL sees: text content only">{result.content?.map((c) => c.text).join("\n") ?? ""}</CodeBlock>}
      </Panel>

      <Panel title="View (sandboxed iframe)" mode="declarative" aside={<span className="muted">mode: author-written view + data</span>}>
        {state === "loading" && <div className="skeleton" aria-busy="true" />}
        {html && !hostile && <McpFrame html={html} deps={deps} />}
        {hostile && <McpFrame html={HOSTILE_VIEW} deps={deps} />}
        {!html && !hostile && state !== "loading" && <p className="muted">Run a prompt to see the view.</p>}
        <button className="btn" onClick={() => { setHostile(true); add("host", "mounting an UNTRUSTED view"); }}>Mount a malicious view (tries a forbidden tool + network)</button>
        <p className="muted">Static: the view's layout is fixed HTML. Declarative: it draws whatever <code>structuredContent.kind</code> says. Open-ended: a view is arbitrary HTML, so safety comes from the host: sandbox, CSP and the tool allowlist.</p>
      </Panel>

      <Panel title="Protocol log"><EventLog lines={log} empty="No traffic yet." /></Panel>
      <Panel title="MCP server: tools & resources">
        <ul>{tools.map((t) => <li key={t.name}><code>{t.name}</code> — {t.description} {t._meta?.ui?.resourceUri && <span className="badge">ui</span>}</li>)}</ul>
        <p className="muted">Resource <code>ui://genux/items-view</code> (<code>text/html;profile=mcp-app</code>) and <code>items://catalog</code>. For real hosts run <code>pnpm mcp:stdio</code>.</p>
      </Panel>
    </Shell>
  );
}
