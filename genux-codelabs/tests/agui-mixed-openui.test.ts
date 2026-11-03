import { describe, expect, it } from "vitest";
import type { BaseEvent } from "@ag-ui/core";
import { connectInMemory } from "@genux/mcp-server";
import { runAgent } from "../apps/agui/server/agent";
import type { Demo } from "../apps/agui/server/agent";
import { runCapstone } from "../apps/mixed-mode/server/pipeline";
import { planRegions } from "../apps/mixed-mode/server/planner";
import { compareItems } from "@genux/shared";
import { generateProgram } from "../apps/openui/server/api";
import { catalogLibrary, hybridLibrary, PROMPT_OPTIONS } from "@genux/ui/openui";

async function collect(gen: AsyncGenerator<BaseEvent>): Promise<string[]> {
  const out: string[] = [];
  for await (const e of gen) out.push(e.type as string);
  return out;
}

describe("AG-UI agent", () => {
  const base = { threadId: "t", runId: "r", prompt: "", toolResults: {}, env: {} };
  it.each<Demo>(["static", "declarative", "open-ended", "harness"])("%s run has a valid lifecycle", async (demo) => {
    const types = await collect(runAgent({ ...base, demo }));
    expect(types[0]).toBe("RUN_STARTED");
    expect(types.at(-1)).toBe("RUN_FINISHED");
    expect(types.filter((t) => t === "TEXT_MESSAGE_START").length).toBe(types.filter((t) => t === "TEXT_MESSAGE_END").length);
  });
  it("declarative uses a state snapshot then deltas", async () => {
    const types = await collect(runAgent({ ...base, demo: "declarative" }));
    expect(types).toContain("STATE_SNAPSHOT");
    expect(types).toContain("STATE_DELTA");
  });
  it("approval pauses on a frontend tool call, then continues once answered", async () => {
    const first = await collect(runAgent({ ...base, demo: "approval" }));
    expect(first).toContain("TOOL_CALL_END");
    expect(first).not.toContain("STATE_SNAPSHOT");
    const second = await collect(runAgent({ ...base, demo: "approval", toolResults: { tc_confirm: "approved" } }));
    expect(second).toContain("STATE_SNAPSHOT");
  });
});

describe("capstone", () => {
  it("planner picks all three modes only when justified", () => {
    const comparison = compareItems(["air-13", "vertex-13", "nimbus-14"]);
    const full = planRegions({ prompt: "plan my savings with a budget calculator", comparison, summary: "s" });
    expect(full.regions.map((r) => r.mode)).toEqual(["static", "declarative", "declarative", "open-ended"]);
    const plain = planRegions({ prompt: "compare laptops", comparison, summary: "s" });
    expect(plain.regions.some((r) => r.mode === "open-ended")).toBe(false);
    expect(plain.skipped.join()).toMatch(/open-ended skipped/);
  });

  it("end-to-end: harness → MCP → AG-UI events → regions in state", async () => {
    const { client, close } = await connectInMemory();
    const types: string[] = [];
    const deltas: unknown[] = [];
    for await (const e of runCapstone({ threadId: "t", runId: "r", prompt: "Help me choose a laptop under $1500 and plan savings with a budget calculator", client })) {
      types.push(e.type as string);
      if (e.type === "STATE_DELTA") deltas.push(e);
    }
    await close();
    expect(types[0]).toBe("RUN_STARTED");
    expect(types.at(-1)).toBe("RUN_FINISHED");
    expect(types.filter((t) => t === "TOOL_CALL_START").length).toBe(4);
    expect(JSON.stringify(deltas)).toContain('"open-ended"');
  });
});

describe("OpenUI", () => {
  it("catalog prompt excludes HtmlArtifact; hybrid prompt includes it", () => {
    expect(catalogLibrary.prompt(PROMPT_OPTIONS)).not.toContain("HtmlArtifact(");
    expect(hybridLibrary.prompt(PROMPT_OPTIONS)).toContain("HtmlArtifact(");
    expect(catalogLibrary.prompt(PROMPT_OPTIONS)).toContain("Metric(label: string");
  });
  it("generated programs define root first (streams the shell early)", () => {
    expect(generateProgram("dashboard", "declarative").startsWith("root =")).toBe(true);
    expect(generateProgram("budget calculator", "hybrid")).toContain("HtmlArtifact(");
  });
});
