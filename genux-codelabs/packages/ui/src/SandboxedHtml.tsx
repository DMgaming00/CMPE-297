import { useEffect, useMemo, useRef } from "react";
import { buildSandboxDoc, checkDocument, parseWidgetMessage } from "@genux/shared";
import type { WidgetMessage } from "@genux/shared";

/**
 * Open-ended UX container. Model-written HTML runs in `sandbox="allow-scripts"` (opaque origin: no cookies,
 * no parent DOM access), under a CSP that forbids network, nested frames and base/form hijacking.
 * Messages back to the host are accepted only from this iframe and only if they match the allowlist.
 */
export function SandboxedHtml({ title, html, height = 260, onMessage }: { title: string; html: string; height?: number; onMessage?: (m: WidgetMessage) => void }) {
  const ref = useRef<HTMLIFrameElement>(null);
  const problems = useMemo(() => checkDocument(html), [html]);
  const srcDoc = useMemo(() => (problems.length ? "" : buildSandboxDoc(html)), [html, problems]);

  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.source !== ref.current?.contentWindow) return;
      const msg = parseWidgetMessage(e.data);
      if (msg) onMessage?.(msg);
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [onMessage]);

  if (problems.length) {
    return (
      <div className="alert tone-danger" role="alert">
        <strong>Blocked generated HTML</strong>
        <ul>{problems.map((p) => <li key={p}>{p}</li>)}</ul>
      </div>
    );
  }
  return <iframe ref={ref} title={title} className="sandbox-frame" style={{ height }} sandbox="allow-scripts" referrerPolicy="no-referrer" srcDoc={srcDoc} />;
}
