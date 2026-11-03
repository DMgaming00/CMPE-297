import { describe, expect, it } from "vitest";
import { DEFAULT_ALLOWED, ScriptedModel, defaultTools, runHarness, SYSTEM_PROMPT, toAgUi, newBridge, renderSpecText } from "@genux/harness";
import type { HarnessEvent } from "@genux/harness";

async function run(prompt: string, target: "json-render" | "openui" | "openui-hybrid" = "json-render", allowed = DEFAULT_ALLOWED, maxSteps = 6) {
  const events: HarnessEvent[] = [];
  const res = await runHarness({ model: new ScriptedModel(target), tools: defaultTools, config: { maxSteps, allowedTools: allowed, system: SYSTEM_PROMPT }, messages: [{ role: "user", content: prompt }], onEvent: (e) => events.push(e) });
  return { res, events };
}

describe("harness loop", () => {
  it("compare flow: MCP-style tools then a validated render_ui", async () => {
    const { res, events } = await run("compare laptops under $1500");
    expect(res.ok).toBe(true);
    const ui = events.find((e) => e.type === "ui");
    expect(ui?.type === "ui" && ui.payload.kind).toBe("json-render");
    if (ui?.type === "ui" && ui.payload.kind === "json-render") expect(renderSpecText(ui.payload.spec)).toContain("Laptop comparison");
  });

  it("invalid UI is an error tool message and the model self-corrects", async () => {
    const { res, events } = await run("render an invalid broken interface");
    expect(res.ok).toBe(true);
    expect(events.some((e) => e.type === "tool_error" && e.name === "render_ui")).toBe(true);
    expect(events.some((e) => e.type === "ui")).toBe(true);
  });

  it("refuses unauthorized tools and never executes them", async () => {
    const { events } = await run("please delete the database");
    expect(events.find((e) => e.type === "tool_error")).toMatchObject({ name: "delete_database" });
  });

  it("allowlist also hides real tools", async () => {
    const { events } = await run("show me a dashboard", "json-render", DEFAULT_ALLOWED.filter((t) => t !== "render_ui"));
    expect(events.some((e) => e.type === "tool_error" && /not permitted/.test(e.error))).toBe(true);
    expect(events.some((e) => e.type === "ui")).toBe(false);
  });

  it("stops at the step limit with a run_error", async () => {
    const { res, events } = await run("compare laptops", "json-render", DEFAULT_ALLOWED, 2);
    expect(res.ok).toBe(false);
    expect(events.at(-1)).toMatchObject({ type: "run_error" });
  });

  it("OpenUI and hybrid targets produce programs; widget goes through the document check", async () => {
    const o = await run("show me a dashboard", "openui-hybrid");
    expect(o.events.find((e) => e.type === "ui" && e.payload.kind === "openui")).toBeTruthy();
    const w = await run("build an interactive budget calculator");
    expect(w.events.find((e) => e.type === "ui" && e.payload.kind === "html")).toBeTruthy();
  });

  it("UI actions are handled as the next turn", async () => {
    const { events } = await run(`[ui-action] select_item {"id":"air-13"}`);
    expect(events.some((e) => e.type === "tool_result" && e.name === "get_item_details")).toBe(true);
    expect(events.some((e) => e.type === "ui")).toBe(true);
  });

  it("bridges events to AG-UI with a consistent lifecycle", async () => {
    const { events } = await run("show me a dashboard");
    const b = newBridge("t", "r");
    const types = events.flatMap((e) => toAgUi(e, b)).map((e) => e.type as string);
    expect(types[0]).toBe("RUN_STARTED");
    expect(types).toContain("TOOL_CALL_START");
    expect(types).toContain("STATE_SNAPSHOT");
    expect(types.at(-1)).toBe("RUN_FINISHED");
  });
});
