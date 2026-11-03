import { useMemo, useState } from "react";
import { BROKEN_SPEC, ITEMS, comparisonSpec, compareItems, dashboardSpec, itemDetailSpec } from "@genux/shared";
import { formatIssues, validateSpec } from "@genux/schemas";
import { CodeBlock, EventLog, ItemCard, JsonRender, Panel, Shell, Status } from "@genux/ui";
import type { LogLine, UiAction } from "@genux/ui";

const PRESETS: Record<string, unknown> = {
  comparison: comparisonSpec(compareItems(["air-13", "vertex-13", "forge-14"])),
  dashboard: dashboardSpec(ITEMS.slice(0, 5)),
  detail: itemDetailSpec(ITEMS[0]!),
  "broken (unsafe)": BROKEN_SPEC,
};
const TABS = ["Static", "Declarative", "Open-ended", "Mixed"] as const;
type Tab = (typeof TABS)[number];

export function App() {
  const [tab, setTab] = useState<Tab>("Declarative");
  return (
    <Shell
      lab="json-render"
      title="JSON Render"
      subtitle="A typed, validated JSON → UI renderer. The model describes; the app validates and decides what is drawn."
      flow={["JSON spec", "Schema validation", "Component registry", "Renderer", "Interactive UI"]}
    >
      <div className="wide tabs" role="tablist">
        {TABS.map((t) => <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>{t}</button>)}
      </div>
      {tab === "Static" && <StaticTab />}
      {tab === "Declarative" && <DeclarativeTab />}
      {tab === "Open-ended" && <NotApplicable mode="Open-ended" why="A JSON Render spec can only name catalog components with schema-checked props. It has no field that can carry code or markup, so there is nothing open-ended to demonstrate. Free-form output needs a different container: see OpenUI's HtmlArtifact (apps/openui) or the sandbox in the capstone (apps/mixed-mode)." />}
      {tab === "Mixed" && <NotApplicable mode="Mixed" why="Mixing modes needs a second generation strategy next to the catalog. JSON Render is the declarative half of that mix; the combined static + declarative + open-ended application is apps/mixed-mode." />}
    </Shell>
  );
}

function NotApplicable({ mode, why }: { mode: string; why: string }) {
  return (
    <Panel title={`${mode} UX is not part of JSON Render`}>
      <p className="note">{why}</p>
    </Panel>
  );
}

function StaticTab() {
  const [picked, setPicked] = useState<string>();
  return (
    <>
      <Panel title="Pre-built component" mode="static">
        <ItemCard item={ITEMS[0]!} onSelect={setPicked} />
        <p className="muted">{picked ? `Selected ${picked}` : "Click Select."} The layout is fixed in code. Only the data varies.</p>
      </Panel>
      <Panel title="How it works" mode="static">
        <p>User → application → pre-built component → UI. Nothing a model emits can change the layout. Safest and most predictable, but every new screen is a code change.</p>
        <CodeBlock label="packages/ui/src/ItemCard.tsx">{`<ItemCard item={item} onSelect={...} />`}</CodeBlock>
      </Panel>
    </>
  );
}

function DeclarativeTab() {
  const [preset, setPreset] = useState("comparison");
  const [text, setText] = useState(() => JSON.stringify(PRESETS.comparison, null, 2));
  const [lenient, setLenient] = useState(false);
  const [log, setLog] = useState<LogLine[]>([]);

  const parsed = useMemo(() => {
    try {
      return { value: JSON.parse(text) as unknown };
    } catch (e) {
      return { error: (e as Error).message };
    }
  }, [text]);
  const result = useMemo(() => (parsed.error ? undefined : validateSpec(parsed.value, { lenient, allowedActions: ["select_item", "refine_search", "compare_selected"] })), [parsed, lenient]);

  const onAction = (a: UiAction) => setLog((l) => [{ t: new Date().toLocaleTimeString(), kind: "action", text: `${a.name} ${JSON.stringify(a.params ?? {})}` }, ...l]);
  const state = parsed.error ? "error" : result?.ok ? "done" : "error";

  return (
    <>
      <Panel title="1 · Spec (untrusted JSON)" mode="declarative" aside={<Status state={state} label={parsed.error ? "invalid JSON" : result?.ok ? "valid" : "rejected"} />}>
        <div className="row-gap" style={{ flexWrap: "wrap" }}>
          <label className="row-gap">Preset
            <select value={preset} onChange={(e) => { setPreset(e.target.value); setText(JSON.stringify(PRESETS[e.target.value], null, 2)); }}>
              {Object.keys(PRESETS).map((p) => <option key={p}>{p}</option>)}
            </select>
          </label>
          <label className="row-gap"><input type="checkbox" style={{ width: "auto" }} checked={lenient} onChange={(e) => setLenient(e.target.checked)} /> Lenient (drop bad elements, keep the rest)</label>
        </div>
        <textarea aria-label="Spec JSON" value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} />
      </Panel>

      <Panel title="2 · Validation + rendered UI" mode="declarative">
        {parsed.error && <div className="alert tone-danger" role="alert"><strong>Not JSON</strong><span>{parsed.error}</span></div>}
        {result && !result.ok && (
          <div className="alert tone-danger" role="alert">
            <strong>Spec rejected. Nothing was rendered.</strong>
            <pre>{formatIssues(result.issues)}</pre>
          </div>
        )}
        {result?.ok && result.issues.length > 0 && (
          <div className="alert tone-warning" role="alert"><strong>{result.issues.length} issue(s) repaired</strong><pre>{formatIssues(result.issues)}</pre></div>
        )}
        {result?.ok && result.spec && <JsonRender spec={result.spec} onAction={onAction} />}
      </Panel>

      <Panel title="Actions emitted by the UI">
        <EventLog lines={log} empty="Click a button or submit the form. The renderer reports named actions; the app decides what they mean." />
      </Panel>

      <Panel title="Safety rules enforced">
        <ul>
          <li>Unknown component types are rejected (<code>ScriptRunner</code>).</li>
          <li>Every props schema is <code>.strict()</code>: <code>dangerouslySetInnerHTML</code>, <code>style</code>, <code>onClick</code> cannot pass.</li>
          <li>Only <code>Card</code>/<code>Stack</code> take children; ids must exist; cycles and depth &gt; 12 fail.</li>
          <li>Actions must be snake_case and on the app's allowlist.</li>
          <li>All text renders as React text nodes, so HTML in strings is shown literally.</li>
        </ul>
      </Panel>
    </>
  );
}
