import { Component, useState } from "react";
import type { ErrorInfo, FormEvent, ReactNode } from "react";
import type { Spec, ValidElement } from "@genux/schemas";

export interface UiAction {
  name: string;
  params?: Record<string, string | number | boolean>;
}
export interface JsonRenderProps {
  /** MUST already be validated with `validateSpec`; the type only admits validated specs. */
  spec: Spec;
  onAction?: (action: UiAction) => void;
}

const gapClass = { s: "gap-s", m: "gap-m", l: "gap-l" } as const;

/**
 * The component registry: type → React renderer. Anything not in this table cannot be rendered.
 * All text goes through React children (auto-escaped); there is no raw-HTML path.
 */
function renderElement(spec: Spec, id: string, onAction: (a: UiAction) => void, depth: number): ReactNode {
  const el: ValidElement | undefined = spec.elements[id];
  if (!el || depth > 12) return null;
  const kids = () => el.children.map((c) => <div key={c} className="jr-child">{renderElement(spec, c, onAction, depth + 1)}</div>);
  switch (el.type) {
    case "Card":
      return (
        <section className="card" data-component="Card">
          {el.props.title && <h3 className="card-title">{el.props.title}</h3>}
          {el.props.description && <p className="muted">{el.props.description}</p>}
          <div className="stack column gap-m">{kids()}</div>
        </section>
      );
    case "Stack":
      return <div className={`stack ${el.props.direction ?? "column"} ${gapClass[el.props.gap ?? "m"]}`} data-component="Stack">{kids()}</div>;
    case "Text":
      return <p className={`text ${el.props.variant ?? "body"}`} data-component="Text">{el.props.text}</p>;
    case "Button":
      return (
        <button type="button" className={`btn ${el.props.variant ?? "secondary"}`} data-component="Button" onClick={() => onAction({ name: el.props.action, params: el.props.params })}>
          {el.props.label}
        </button>
      );
    case "Badge":
      return <span className={`badge tone-${el.props.tone ?? "neutral"}`} data-component="Badge">{el.props.label}</span>;
    case "Metric":
      return (
        <div className={`metric tone-${el.props.tone ?? "neutral"}`} data-component="Metric">
          <div className="metric-label">{el.props.label}</div>
          <div className="metric-value">{String(el.props.value)}</div>
          {el.props.delta && <div className={`metric-delta ${el.props.delta.startsWith("-") ? "down" : "up"}`}>{el.props.delta}</div>}
        </div>
      );
    case "Table":
      return (
        <div className="table-wrap" data-component="Table">
          <table className="table">
            <thead><tr>{el.props.columns.map((c, i) => <th key={i}>{c}</th>)}</tr></thead>
            <tbody>{el.props.rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{String(c)}</td>)}</tr>)}</tbody>
          </table>
        </div>
      );
    case "Alert":
      return (
        <div className={`alert tone-${el.props.tone ?? "info"}`} role="alert" data-component="Alert">
          {el.props.title && <strong>{el.props.title}</strong>}
          <span>{el.props.message}</span>
        </div>
      );
    case "Form":
      return <FormView key={id} element={el} onAction={onAction} />;
  }
}

function FormView({ element, onAction }: { element: Extract<ValidElement, { type: "Form" }>; onAction: (a: UiAction) => void }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const submit = (e: FormEvent) => {
    e.preventDefault();
    onAction({ name: element.props.action, params: Object.fromEntries(Object.entries(values).map(([k, v]) => [k, v.slice(0, 200)])) });
  };
  return (
    <form className="form" data-component="Form" onSubmit={submit}>
      {element.props.title && <h4>{element.props.title}</h4>}
      {element.props.fields.map((f) => (
        <label key={f.name} className="field">
          <span>{f.label}</span>
          {f.type === "select" ? (
            <select required={f.required} value={values[f.name] ?? ""} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}>
              <option value="">Select…</option>
              {(f.options ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          ) : (
            <input type={f.type} required={f.required} placeholder={f.placeholder} value={values[f.name] ?? ""} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} />
          )}
        </label>
      ))}
      <button type="submit" className="btn primary">{element.props.submitLabel ?? "Submit"}</button>
    </form>
  );
}

class Boundary extends Component<{ children: ReactNode }, { error?: string }> {
  override state: { error?: string } = {};
  static getDerivedStateFromError(e: Error) {
    return { error: e.message };
  }
  override componentDidCatch(_e: Error, _i: ErrorInfo) {}
  override render() {
    return this.state.error ? <div className="alert tone-danger" role="alert">Renderer error: {this.state.error}</div> : this.props.children;
  }
}

export function JsonRender({ spec, onAction = () => {} }: JsonRenderProps) {
  return <Boundary>{renderElement(spec, spec.root, onAction, 0)}</Boundary>;
}
