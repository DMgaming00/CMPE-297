import type { Plugin } from "vite";
import { z } from "zod";
import { DEFAULT_ALLOWED, SYSTEM_PROMPT, UI_ACTIONS, createModel, defaultTools, runHarness } from "@genux/harness";
import type { ChatMessage, UiTarget } from "@genux/harness";
import { readJsonBody, sendJson, sseSend, startSse } from "@genux/shared/node";

const body = z.object({
  sessionId: z.string().regex(/^[\w-]{6,64}$/),
  ui: z.enum(["json-render", "openui", "openui-hybrid"]).default("json-render"),
  allowedTools: z.array(z.string()).max(20).optional(),
  maxSteps: z.number().int().min(1).max(10).optional(),
  prompt: z.string().min(1).max(400).optional(),
  action: z.object({ name: z.string(), params: z.record(z.string(), z.union([z.string(), z.number(), z.boolean()])).optional() }).optional(),
});

/** In-memory sessions (bounded). A real deployment would persist and authenticate these. */
const sessions = new Map<string, ChatMessage[]>();

export function harnessApi(env: Record<string, string>): Plugin {
  return {
    name: "harness-api",
    configureServer(server) {
      server.middlewares.use("/api/harness/config", (_req, res) => {
        const { model, config } = createModel("json-render", env);
        sendJson(res, 200, { model: model.name, maxSteps: config.maxSteps, tools: DEFAULT_ALLOWED, actions: UI_ACTIONS, system: SYSTEM_PROMPT, provider: env.LLM_PROVIDER === "openai-compatible" ? "openai-compatible" : "mock" });
      });
      server.middlewares.use("/api/harness/run", async (req, res) => {
        const parsed = body.safeParse(await readJsonBody(req).catch(() => null));
        if (!parsed.success || (!parsed.data.prompt && !parsed.data.action)) return sendJson(res, 422, { error: "invalid request" });
        const { sessionId, ui, prompt, action } = parsed.data;

        let userText: string;
        if (action) {
          // Actions are a closed set. A click can never name an arbitrary tool.
          if (!(UI_ACTIONS as readonly string[]).includes(action.name)) return sendJson(res, 403, { error: `action "${action.name.slice(0, 40)}" is not allowed` });
          userText = `[ui-action] ${action.name} ${JSON.stringify(action.params ?? {})}`;
        } else userText = prompt!;

        if (sessions.size > 200) sessions.clear();
        const history = sessions.get(sessionId) ?? [];
        history.push({ role: "user", content: userText });

        const { model, config } = createModel(ui as UiTarget, env);
        config.maxSteps = parsed.data.maxSteps ?? config.maxSteps;
        config.allowedTools = (parsed.data.allowedTools ?? DEFAULT_ALLOWED).filter((t) => DEFAULT_ALLOWED.includes(t));

        startSse(res);
        let closed = false;
        res.on("close", () => (closed = true));
        const result = await runHarness({ model, tools: defaultTools, config, messages: history.slice(-40), onEvent: (e) => { if (!closed) sseSend(res, e); } });
        sessions.set(sessionId, result.messages.filter((m) => m.role !== "system"));
        sseSend(res, "done", "done");
        res.end();
      });
    },
  };
}
