import type { Plugin } from "vite";
import { EventEncoder } from "@ag-ui/encoder";
import { RunAgentInputSchema } from "@ag-ui/core/schemas";
import { readJsonBody, sendJson } from "@genux/shared/node";
import { runAgent } from "./agent";
import type { Demo } from "./agent";

const DEMOS = new Set<Demo>(["static", "declarative", "open-ended", "approval", "harness"]);

export function aguiApi(env: Record<string, string>): Plugin {
  return {
    name: "agui-api",
    configureServer(server) {
      server.middlewares.use("/api/agui", async (req, res) => {
        if (req.method !== "POST") return sendJson(res, 405, { error: "POST only" });
        const parsed = RunAgentInputSchema.safeParse(await readJsonBody(req).catch(() => null));
        if (!parsed.success) return sendJson(res, 422, { error: "invalid RunAgentInput" });
        const input = parsed.data;
        const demo = (input.forwardedProps as { demo?: string } | undefined)?.demo as Demo;
        if (!DEMOS.has(demo)) return sendJson(res, 400, { error: "unknown demo" });
        const toolResults: Record<string, string> = {};
        for (const m of input.messages) if (m.role === "tool" && typeof m.content === "string") toolResults[m.toolCallId] = m.content;
        const lastUser = [...input.messages].reverse().find((m) => m.role === "user");

        const encoder = new EventEncoder({ accept: req.headers.accept });
        res.writeHead(200, { "Content-Type": encoder.getContentType(), "Cache-Control": "no-cache", Connection: "keep-alive" });
        let closed = false;
        res.on("close", () => (closed = true));
        for await (const event of runAgent({ threadId: input.threadId, runId: input.runId, demo, prompt: typeof lastUser?.content === "string" ? lastUser.content : "", toolResults, env })) {
          if (closed) break;
          res.write(encoder.encodeSSE(event));
        }
        res.end();
      });
    },
  };
}
