import type { Plugin } from "vite";
import { actionMessageSchema } from "@genux/schemas";
import { readJsonBody, sendJson, sseSend, startSse } from "@genux/shared/node";
import { sleep } from "@genux/shared";
import { handleAction, scenarioMessages } from "./agent";

const SCENARIOS = new Set(["contact", "laptops", "invalid"]);

export function a2uiApi(): Plugin {
  return {
    name: "a2ui-api",
    configureServer(server) {
      // Agent → client: one A2UI envelope per SSE `data:` line, streamed with delays.
      server.middlewares.use("/api/a2ui/stream", async (req, res) => {
        const scenario = new URL(req.url ?? "", "http://x").searchParams.get("scenario") ?? "";
        if (!SCENARIOS.has(scenario)) return sendJson(res, 400, { error: "unknown scenario" });
        startSse(res);
        let closed = false;
        req.on("close", () => (closed = true));
        for (const m of scenarioMessages(scenario)) {
          if (closed) return;
          sseSend(res, m);
          await sleep(450);
        }
        sseSend(res, "done", "done");
        res.end();
      });
      // Client → agent: the A2UI `action` message. Validated; the reply is more envelopes.
      server.middlewares.use("/api/a2ui/action", async (req, res) => {
        try {
          const body = actionMessageSchema.safeParse(await readJsonBody(req));
          if (!body.success) return sendJson(res, 422, { error: "invalid action message" });
          sendJson(res, 200, { messages: handleAction(body.data) });
        } catch {
          sendJson(res, 400, { error: "bad request" });
        }
      });
    },
  };
}
