import { describe, expect, it } from "vitest";
import { validateSpec } from "@genux/schemas";
import { BROKEN_SPEC, comparisonSpec, compareItems, dashboardSpec, ITEMS } from "@genux/shared";

describe("JSON Render validation", () => {
  it("accepts specs built from every catalog builder", () => {
    expect(validateSpec(comparisonSpec(compareItems(["air-13", "vertex-13"]))).ok).toBe(true);
    expect(validateSpec(dashboardSpec(ITEMS.slice(0, 4))).ok).toBe(true);
  });

  it("fails closed on unknown components, unsafe props, bad actions and missing children", () => {
    const r = validateSpec(BROKEN_SPEC);
    expect(r.ok).toBe(false);
    const msgs = r.issues.map((i) => i.message).join("\n");
    expect(msgs).toMatch(/unknown component "ScriptRunner"/);
    expect(msgs).toMatch(/dangerouslySetInnerHTML|Unrecognized key/);
    expect(msgs).toMatch(/snake_case/);
    expect(msgs).toMatch(/unknown child id\(s\): missing/);
  });

  it("lenient mode keeps valid elements and replaces invalid ones with a visible placeholder", () => {
    const r = validateSpec(BROKEN_SPEC, { lenient: true });
    expect(r.ok).toBe(true);
    expect(r.spec?.elements.evil?.type).toBe("Alert");
    expect(r.spec?.elements.ok?.type).toBe("Text");
    expect(r.issues.length).toBeGreaterThan(0);
  });

  it("rejects cycles, missing root, non-container children and disallowed actions", () => {
    const cyc = { root: "a", elements: { a: { type: "Stack", props: {}, children: ["b"] }, b: { type: "Stack", props: {}, children: ["a"] } } };
    expect(validateSpec(cyc).ok).toBe(false);
    expect(validateSpec({ root: "x", elements: {} }).ok).toBe(false);
    expect(validateSpec({ root: "t", elements: { t: { type: "Text", props: { text: "x" }, children: ["u"] }, u: { type: "Text", props: { text: "y" } } } }).ok).toBe(false);
    const btn = { root: "b", elements: { b: { type: "Button", props: { label: "x", action: "wipe_all" } } } };
    expect(validateSpec(btn).ok).toBe(true);
    expect(validateSpec(btn, { allowedActions: ["select_item"] }).ok).toBe(false);
  });

  it("rejects garbage input without throwing", () => {
    for (const bad of [null, 42, "str", [], { root: 1 }]) expect(validateSpec(bad).ok).toBe(false);
  });
});
