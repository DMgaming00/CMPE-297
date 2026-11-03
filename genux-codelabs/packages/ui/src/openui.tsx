import { createLibrary, defineComponent, useIsStreaming, useTriggerAction } from "@openuidev/react-lang";
import { z } from "zod";
import { SandboxedHtml } from "./SandboxedHtml";

/**
 * One definition, three uses: the Zod schema validates arguments, `library.prompt()` writes the system prompt,
 * and the `component` function renders. Argument ORDER in z.object is the positional order in OpenUI Lang.
 */
const Stack = defineComponent({
  name: "Stack",
  description: "Lays children out in a column or a row",
  props: z.object({
    children: z.array(z.any()).describe("child components"),
    direction: z.enum(["column", "row"]).optional().describe("default column"),
    gap: z.enum(["s", "m", "l"]).optional().describe("default m"),
  }),
  component: ({ props, renderNode }) => <div className={`stack ${props.direction ?? "column"} gap-${props.gap ?? "m"}`}>{renderNode(props.children)}</div>,
});

const Text = defineComponent({
  name: "Text",
  description: "A run of text",
  props: z.object({ text: z.string(), size: z.enum(["body", "heading", "muted"]).optional() }),
  component: ({ props }) => <p className={`text ${props.size ?? "body"}`}>{props.text}</p>,
});

const Metric = defineComponent({
  name: "Metric",
  description: "One number with a label and an optional change",
  props: z.object({ label: z.string(), value: z.union([z.string(), z.number()]), delta: z.string().optional().describe('such as "+12%"') }),
  component: ({ props }) => (
    <div className="metric">
      <div className="metric-label">{props.label}</div>
      <div className="metric-value">{String(props.value)}</div>
      {props.delta && <div className={`metric-delta ${props.delta.startsWith("-") ? "down" : "up"}`}>{props.delta}</div>}
    </div>
  ),
});

const Table = defineComponent({
  name: "Table",
  description: "A table with column headers and rows of cells",
  props: z.object({ columns: z.array(z.string()), rows: z.array(z.array(z.union([z.string(), z.number()]))) }),
  component: ({ props }) => (
    <div className="table-wrap">
      <table className="table">
        <thead><tr>{props.columns.map((c, i) => <th key={i}>{c}</th>)}</tr></thead>
        <tbody>{props.rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{String(c)}</td>)}</tr>)}</tbody>
      </table>
    </div>
  ),
});

const BarChart = defineComponent({
  name: "BarChart",
  description: "A bar chart with one series",
  props: z.object({ title: z.string(), labels: z.array(z.string()), values: z.array(z.number()) }),
  component: ({ props }) => {
    const max = Math.max(1, ...props.values);
    return (
      <figure className="card" style={{ margin: 0 }}>
        <figcaption><strong>{props.title}</strong></figcaption>
        {props.values.map((v, i) => (
          <div key={i} className="row-gap" style={{ gap: 8 }}>
            <span style={{ width: 130, fontSize: 12 }}>{props.labels[i]}</span>
            <div style={{ flex: 1, background: "var(--line)", borderRadius: 4 }}><div style={{ width: `${Math.round((v / max) * 100)}%`, height: 12, background: "var(--accent)", borderRadius: 4 }} /></div>
            <span style={{ fontSize: 12 }}>{v}</span>
          </div>
        ))}
      </figure>
    );
  },
});

const Card = defineComponent({
  name: "Card",
  description: "A bordered box with a title and children",
  props: z.object({ title: z.string(), children: z.array(z.any()) }),
  component: ({ props, renderNode }) => <section className="card"><h3 className="card-title">{props.title}</h3>{renderNode(props.children)}</section>,
});

const Alert = defineComponent({
  name: "Alert",
  description: "A callout message",
  props: z.object({ title: z.string(), message: z.string(), tone: z.enum(["info", "success", "warning", "danger"]).optional() }),
  component: ({ props }) => <div className={`alert tone-${props.tone ?? "info"}`} role="alert"><strong>{props.title}</strong><span>{props.message}</span></div>,
});

const Button = defineComponent({
  name: "Button",
  description: "A button that sends a message back to the agent when clicked",
  props: z.object({ label: z.string(), message: z.string().describe("text sent back to the agent") }),
  component: function ButtonView({ props }) {
    const trigger = useTriggerAction();
    return <button type="button" className="btn" onClick={() => trigger(props.message)}>{props.label}</button>;
  },
});

/** The open-ended escape hatch: ONE component whose argument is a whole HTML document. */
function HtmlArtifactView({ props }: { props: { title: string; document: string } }) {
  const streaming = useIsStreaming();
  return (
    <section className="card" data-state={streaming ? "streaming" : "ready"}>
      <div className="row-between"><strong>{props.title}</strong><span className="mode-badge mode-open-ended">open-ended</span></div>
      {streaming ? (
        <>
          <p className="muted">Generating artifact… {props.document.length} characters. Not executed until the stream ends.</p>
          <pre>{props.document}</pre>
        </>
      ) : (
        <SandboxedHtml title={props.title} html={props.document} height={230} />
      )}
    </section>
  );
}
const HtmlArtifact = defineComponent({
  name: "HtmlArtifact",
  description: "A self-contained interactive HTML/CSS/JS document (inline only), run in a sandboxed iframe after it has fully arrived. Use only when the catalog cannot express the request.",
  props: z.object({ title: z.string(), document: z.string().describe("a complete HTML document with inline CSS and JS") }),
  component: HtmlArtifactView,
});

const base = [Stack, Text, Metric, Table, BarChart, Card, Alert, Button];
export const catalogLibrary = createLibrary({ components: base, root: "Stack" });
export const hybridLibrary = createLibrary({ components: [...base, HtmlArtifact], root: "Stack" });

export const PROMPT_OPTIONS = {
  preamble: "You turn a request into a small dashboard. Answer with OpenUI Lang only, no prose.",
  additionalRules: ["Put numbers in Metric values and BarChart values, not in Text.", "Use HtmlArtifact only if the user asks for something interactive the catalog cannot express."],
};
