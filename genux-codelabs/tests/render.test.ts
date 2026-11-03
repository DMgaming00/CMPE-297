import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Renderer } from "@openuidev/react-lang";
import { validateSpec } from "@genux/schemas";
import { BROKEN_SPEC, ITEMS, comparisonSpec, compareItems, openUiHybridProgram, openUiProgram } from "@genux/shared";
import { ItemCard, JsonRender, SandboxedHtml } from "@genux/ui";
import { catalogLibrary, hybridLibrary } from "@genux/ui/openui";

describe("rendering (server-side smoke test of the real components)", () => {
  it("JsonRender draws a validated comparison and escapes HTML in text", () => {
    const spec = validateSpec(comparisonSpec(compareItems(["air-13", "vertex-13"]))).spec!;
    const html = renderToStaticMarkup(h(JsonRender, { spec }));
    expect(html).toContain("Laptop comparison");
    expect(html).toContain("<table");

    const evil = validateSpec({ root: "t", elements: { t: { type: "Text", props: { text: "<img src=x onerror=alert(1)>" } } } }).spec!;
    const out = renderToStaticMarkup(h(JsonRender, { spec: evil }));
    expect(out).not.toContain("<img");
    expect(out).toContain("&lt;img");
  });

  it("lenient repair renders a placeholder instead of the unsafe element", () => {
    const spec = validateSpec(BROKEN_SPEC, { lenient: true }).spec!;
    const html = renderToStaticMarkup(h(JsonRender, { spec }));
    expect(html).toContain("Invalid element removed");
    expect(html).not.toContain("data-component=\"ScriptRunner\"");
    expect(html).not.toContain("alert(1)");
    expect(html).not.toContain("dangerouslySetInnerHTML=");
  });

  it("OpenUI Renderer draws the program with the real library", () => {
    const html = renderToStaticMarkup(h(Renderer, { response: openUiProgram(ITEMS.slice(0, 4)), library: catalogLibrary, isStreaming: false }));
    expect(html).toContain("Laptop shortlist");
    expect(html).toContain("<table");
  });

  it("OpenUI drops unknown components instead of rendering them", () => {
    const bad = `root = Stack([ok, evil])\nok = Text("fine")\nevil = ScriptRunner("alert(1)")`;
    const html = renderToStaticMarkup(h(Renderer, { response: bad, library: catalogLibrary, isStreaming: false }));
    expect(html).toContain("fine");
    expect(html).not.toContain("alert(1)");
  });

  it("hybrid program mounts the artifact in a sandboxed iframe with a CSP-prefixed srcdoc", () => {
    const html = renderToStaticMarkup(h(Renderer, { response: openUiHybridProgram(ITEMS.slice(0, 3)), library: hybridLibrary, isStreaming: false }));
    expect(html).toContain('sandbox="allow-scripts"');
    expect(html).not.toContain("allow-same-origin");
    expect(html).toContain("Content-Security-Policy");
  });

  it("SandboxedHtml refuses a hostile document and ItemCard renders", () => {
    const blocked = renderToStaticMarkup(h(SandboxedHtml, { title: "x", html: '<iframe src="https://evil.example"></iframe>' }));
    expect(blocked).toContain("Blocked generated HTML");
    expect(blocked).not.toContain("<iframe");
    expect(renderToStaticMarkup(h(ItemCard, { item: ITEMS[0]! }))).toContain("Aurora Air 13");
  });
});
