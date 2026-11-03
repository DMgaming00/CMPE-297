/**
 * Host side of the MCP Apps bridge: JSON-RPC 2.0 over postMessage between the host and a sandboxed view.
 * Pure function so it can be unit-tested: it receives one message from the view and returns what to do.
 */
export interface RpcMessage {
  jsonrpc: "2.0";
  id?: number | string;
  method?: string;
  params?: Record<string, unknown>;
}
export interface BridgeDeps {
  allowedTools: readonly string[];
  callTool(name: string, args: Record<string, unknown>): Promise<unknown>;
  lastToolResult(): unknown;
  log(kind: string, text: string): void;
}
export interface BridgeReply {
  /** Message to post back to the view (response and/or notifications). */
  out: RpcMessage[];
  resize?: number;
}

const ok = (id: RpcMessage["id"], result: unknown): RpcMessage => ({ jsonrpc: "2.0", id, result } as RpcMessage);
const err = (id: RpcMessage["id"], code: number, message: string): RpcMessage => ({ jsonrpc: "2.0", id, error: { code, message } } as unknown as RpcMessage);

export function isRpc(data: unknown): data is RpcMessage {
  return typeof data === "object" && data !== null && (data as RpcMessage).jsonrpc === "2.0" && typeof (data as RpcMessage).method === "string";
}

export async function handleViewMessage(msg: RpcMessage, deps: BridgeDeps): Promise<BridgeReply> {
  switch (msg.method) {
    case "ui/initialize":
      deps.log("view → host", "ui/initialize");
      return { out: [ok(msg.id, { protocolVersion: "2026-01-26", hostInfo: { name: "genux-host", version: "1.0.0" }, hostCapabilities: { serverTools: {} }, hostContext: { theme: "light", displayMode: "inline" } })] };
    case "ui/notifications/initialized":
      deps.log("view → host", "ui/notifications/initialized");
      return { out: [{ jsonrpc: "2.0", method: "ui/notifications/tool-result", params: deps.lastToolResult() as Record<string, unknown> }] };
    case "ui/notifications/size-changed": {
      const h = Number(msg.params?.height);
      return { out: [], resize: Number.isFinite(h) ? Math.max(80, Math.min(h + 8, 600)) : undefined };
    }
    case "tools/call": {
      const name = String(msg.params?.name ?? "");
      if (!deps.allowedTools.includes(name)) {
        deps.log("DENIED", `view tried tools/call "${name.slice(0, 40)}" (not on the host allowlist)`);
        return { out: [err(msg.id, -32001, `host policy: tool "${name.slice(0, 40)}" is not allowed`)] };
      }
      deps.log("view → host", `tools/call ${name}`);
      try {
        return { out: [ok(msg.id, await deps.callTool(name, (msg.params?.arguments ?? {}) as Record<string, unknown>))] };
      } catch (e) {
        return { out: [err(msg.id, -32000, e instanceof Error ? e.message : "tool call failed")] };
      }
    }
    default:
      deps.log("ignored", `unsupported method ${String(msg.method).slice(0, 60)}`);
      return { out: msg.id === undefined ? [] : [err(msg.id, -32601, "method not supported by this host")] };
  }
}
