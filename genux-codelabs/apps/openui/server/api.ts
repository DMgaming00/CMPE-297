import type { Plugin } from "vite";
import { HOSTILE_WIDGET_HTML, budgetWidgetHtml, classifyIntent, openUiHybridProgram, openUiProgram, parseBudget, searchItems, sleep, chunkText, ITEMS } from "@genux/shared";
import { readJsonBody, sendJson, sseSend, startSse } from "@genux/shared/node";

/** The mock "model": emits OpenUI Lang text. The first statement is `root = ...` so the shell can paint early. */
export function generateProgram(prompt: string, mode: string): string {
  const items = searchItems({ query: prompt, maxPrice: parseBudget(prompt), limit: 6 });
  const list = items.length >= 2 ? items : ITEMS.slice(0, 5);
  if (mode === "bad") {
    // Unknown component + a wrong-typed argument: the library must drop them instead of crashing.
    return `root = Stack([ok, evil, wrong])\nok = Text("This statement is valid.")\nevil = ScriptRunner("alert(1)")\nwrong = Metric("Price", {"nested": "object"})`;
  }
  if (mode === "hybrid" || classifyIntent(prompt) === "widget") return openUiHybridProgram(list);
  return openUiProgram(list);
}

export function openuiApi(): Plugin {
  return {
    name: "openui-api",
    configureServer(server) {
      server.middlewares.use("/api/openui/generate", async (req, res) => {
        const body = (await readJsonBody(req).catch(() => ({}))) as { prompt?: unknown; mode?: unknown };
        const prompt = typeof body.prompt === "string" ? body.prompt.slice(0, 300) : "";
        const mode = typeof body.mode === "string" ? body.mode : "declarative";
        if (!prompt) return sendJson(res, 400, { error: "prompt required" });
        startSse(res);
        let closed = false;
        req.on("close", () => (closed = true));
        const text = mode === "open-ended" ? (/hostile|escape/i.test(prompt) ? HOSTILE_WIDGET_HTML : budgetWidgetHtml(ITEMS.slice(0, 5))) : generateProgram(prompt, mode);
        for (const chunk of chunkText(text, mode === "open-ended" ? 120 : 32)) {
          if (closed) return;
          sseSend(res, chunk);
          await sleep(55);
        }
        sseSend(res, "done", "done");
        res.end();
      });
    },
  };
}
