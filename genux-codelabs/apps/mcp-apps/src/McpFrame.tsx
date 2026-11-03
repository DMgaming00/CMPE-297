import { useEffect, useRef, useState } from "react";
import { SANDBOX_CSP } from "@genux/shared";
import { handleViewMessage, isRpc } from "./bridge";
import type { BridgeDeps } from "./bridge";

/** Mounts an MCP App view in a sandboxed iframe and relays the bridge. Host CSP is injected before the view's markup. */
export function McpFrame({ html, deps }: { html: string; deps: BridgeDeps }) {
  const ref = useRef<HTMLIFrameElement>(null);
  const depsRef = useRef(deps);
  depsRef.current = deps;
  const [height, setHeight] = useState(180);
  const srcDoc = `<!doctype html><meta http-equiv="Content-Security-Policy" content="${SANDBOX_CSP}">${html.replace(/^\s*<!doctype[^>]*>/i, "")}`;

  useEffect(() => {
    const onMessage = async (e: MessageEvent) => {
      if (e.source !== ref.current?.contentWindow || !isRpc(e.data)) return; // only our iframe, only JSON-RPC
      const reply = await handleViewMessage(e.data, depsRef.current);
      if (reply.resize) setHeight(reply.resize);
      for (const m of reply.out) ref.current?.contentWindow?.postMessage(m, "*"); // opaque origin → "*" is required; source check above is the guard
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [html]);

  return <iframe ref={ref} title="MCP App view" className="sandbox-frame" style={{ height }} sandbox="allow-scripts" referrerPolicy="no-referrer" srcDoc={srcDoc} />;
}
