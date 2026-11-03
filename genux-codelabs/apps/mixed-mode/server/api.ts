import type { Plugin } from "vite";
import type { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { EventEncoder } from "@ag-ui/encoder";
import { RunAgentInputSchema } from "@ag-ui/core/schemas";
import { connectInMemory } from "@genux/mcp-server";
import { readJsonBody, sendJson } from "@genux/shared/node";
import { runCapstone } from "./pipeline";

export function mixedApi(): Plugin {
  let clientP: Promise<Client> | undefined;
  const client = () => (clientP ??= connectInMemory().then((c) => c.client));
  return {
    name: "mixed-api",
    configureServer(server) {
      server.middlewares.use("/api/mixed/agui", async (req, res) => {
        if (req.method !== "POST") return sendJson(res, 405, { error: "POST only" });
        const parsed = RunAgentInputSchema.safeParse(await readJsonBody(req).catch(() => null));
        if (!parsed.success) return sendJson(res, 422, { error: "invalid RunAgentInput" });
        const input = parsed.data;
        const last = [...input.messages].reverse().find((m) => m.role === "user");
        const prompt = typeof last?.content === "string" ? last.content.slice(0, 400) : "";
        if (!prompt) return sendJson(res, 400, { error: "empty prompt" });

        const encoder = new EventEncoder({ accept: req.headers.accept });
        res.writeHead(200, { "Content-Type": encoder.getContentType(), "Cache-Control": "no-cache", Connection: "keep-alive" });
        let closed = false;
        res.on("close", () => (closed = true));
        for await (const ev of runCapstone({ threadId: input.threadId, runId: input.runId, prompt, client: await client() })) {
          if (closed) break;
          res.write(encoder.encodeSSE(ev));
        }
        res.end();
      });
    },
  };
}
