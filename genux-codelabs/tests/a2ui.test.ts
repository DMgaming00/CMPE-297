import { describe, expect, it } from "vitest";
import { BASIC_CATALOG_ID } from "@genux/schemas";
import { SurfaceStore } from "../apps/a2ui/src/a2ui/store";
import { handleAction, scenarioMessages } from "../apps/a2ui/server/agent";

describe("A2UI surface store", () => {
  it("applies the contact scenario: structure and data stay separate", () => {
    const s = new SurfaceStore();
    for (const m of scenarioMessages("contact")) expect(s.process(m)).toBeUndefined();
    const surf = s.get("contact")!;
    expect(surf.components.has("root")).toBe(true);
    expect(surf.data).toMatchObject({ form: { name: "", topic: ["question"] } });
  });

  it("rejects unknown components but keeps processing the stream", () => {
    const s = new SurfaceStore();
    const [create, bad, good] = scenarioMessages("invalid");
    expect(s.process(create)).toBeUndefined();
    expect(s.process(bad)).toMatch(/./);
    expect(s.process(good)).toBeUndefined();
    expect(s.get("invalid")!.components.get("root")?.component).toBe("Card");
  });

  it("two-way binding + action context resolves at click time; sendDataModel attaches the model", () => {
    const s = new SurfaceStore();
    scenarioMessages("contact").forEach((m) => s.process(m));
    s.setValue("contact", "/form/name", "Ada");
    s.setValue("contact", "/form/email", "ada@example.com");
    const a = s.buildAction("contact", "send", "submit_contact", { name: { path: "/form/name" }, email: { path: "/form/email" } });
    expect(a.action.context).toEqual({ name: "Ada", email: "ada@example.com" });
    expect(a).toHaveProperty("dataModel");
    const reply = handleAction(a as never);
    expect(JSON.stringify(reply)).toContain("Thanks Ada");
  });

  it("blocks prototype-pollution paths and duplicate surfaces", () => {
    const s = new SurfaceStore();
    s.process({ version: "v0.9.1", createSurface: { surfaceId: "x", catalogId: BASIC_CATALOG_ID } });
    expect(s.process({ version: "v0.9.1", updateDataModel: { surfaceId: "x", path: "/__proto__/polluted", value: 1 } })).toMatch(/forbidden/);
    expect(({} as Record<string, unknown>).polluted).toBeUndefined();
    expect(s.process({ version: "v0.9.1", createSurface: { surfaceId: "x", catalogId: BASIC_CATALOG_ID } })).toMatch(/already exists/);
  });

  it("agent searches the catalog on search_laptops", () => {
    const reply = handleAction({ version: "v0.9.1", action: { name: "search_laptops", surfaceId: "laptops", sourceComponentId: "go", timestamp: "t", context: { maxPrice: "800", category: ["any"] } } });
    expect(JSON.stringify(reply)).toContain("Nimbus");
  });
});
