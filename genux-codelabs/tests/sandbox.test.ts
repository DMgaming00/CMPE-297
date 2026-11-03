import { describe, expect, it } from "vitest";
import { HOSTILE_WIDGET_HTML, SANDBOX_CSP, budgetWidgetHtml, buildSandboxDoc, checkDocument, parseWidgetMessage, ITEMS } from "@genux/shared";

describe("open-ended sandbox helpers", () => {
  it("accepts the benign widget and blocks the hostile one", () => {
    expect(checkDocument(budgetWidgetHtml(ITEMS.slice(0, 3)))).toEqual([]);
    expect(checkDocument(HOSTILE_WIDGET_HTML).length).toBeGreaterThan(0);
  });
  it("injects the CSP before any model-written element", () => {
    const doc = buildSandboxDoc("<!doctype html><script>x()</script>");
    expect(doc.indexOf("Content-Security-Policy")).toBeLessThan(doc.indexOf("<script"));
    expect(SANDBOX_CSP).toContain("connect-src 'none'");
  });
  it("only accepts allowlisted, well-typed widget messages", () => {
    expect(parseWidgetMessage({ type: "genux-widget", name: "widget_result", payload: { n: 1, bad: { x: 1 } } })?.payload).toEqual({ n: 1 });
    expect(parseWidgetMessage({ type: "genux-widget", name: "steal_cookies" })).toBeNull();
    expect(parseWidgetMessage("hello")).toBeNull();
  });
});
