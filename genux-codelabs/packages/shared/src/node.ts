import type { IncomingMessage, ServerResponse } from "node:http";

/** Node-only helpers used by the Vite dev-server API plugins. */
export async function readJsonBody(req: IncomingMessage, limit = 100_000): Promise<unknown> {
  let size = 0;
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    size += (chunk as Buffer).length;
    if (size > limit) throw new Error("request body too large");
    chunks.push(chunk as Buffer);
  }
  const text = Buffer.concat(chunks).toString("utf8");
  return text ? JSON.parse(text) : {};
}

export function startSse(res: ServerResponse): void {
  res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache, no-transform", Connection: "keep-alive" });
}
export const sseSend = (res: ServerResponse, data: unknown, event?: string): void => {
  res.write(`${event ? `event: ${event}\n` : ""}data: ${typeof data === "string" ? data : JSON.stringify(data)}\n\n`);
};
export function sendJson(res: ServerResponse, status: number, body: unknown): void {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}
