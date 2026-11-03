# Comparison

Facts below come from the reference course (genui, State of Generative UI report June 2026) and the official packages used in this repo. "Here" notes what this repository implements.

| Technology | Purpose | Communication / data | UI role | Streaming | Tools | Best use |
|---|---|---|---|---|---|---|
| **A2UI** | A declarative, framework-agnostic format for agent-generated UI | JSON envelopes `createSurface`, `updateComponents`, `updateDataModel`, `deleteSurface`; flat components by id; data model by JSON Pointer; client → server `action`. Transport-agnostic | Describes UI; the client renders it with its own catalog components | Yes: messages are incremental; structure and data stream separately | Not a tool protocol; actions return events to the agent | Agent-authored forms/dashboards rendered natively, potentially across frameworks |
| **AG-UI** | Agent ⇄ frontend interaction protocol | Typed events over HTTP/SSE: lifecycle, text, tool calls, state snapshot + JSON Patch, custom | Carries UI intent/state; does not define components | Yes: core feature | Tool call events (incl. frontend tools / human-in-the-loop) | Wiring an agent backend to your own product UI |
| **MCP Apps** | Let MCP tools ship an interactive UI to third-party hosts | MCP tool result + `ui://` HTML resource; `_meta.ui.resourceUri`; JSON-RPC over `postMessage` between host and sandboxed iframe | The UI is a finished HTML view run by the host | Per MCP transport; the view receives `ui/notifications/tool-result` | Core: MCP tools/resources; the view can call tools via the host | Shipping one interface into desktop MCP hosts |
| **JSON Render** | Constrain model UI to a typed catalog | JSON element map `{root, elements}` validated by a schema | Declarative spec → component registry → renderer | Spec can stream (RFC 6902 patches in the reference); **here**: validated whole | Out of scope; actions are named events | Safe, predictable generated UI; one spec, several renderers |
| **OpenUI (Lang)** | Compact line-oriented UI language | Text: `id = Component(args)`; positional args; forward references; Zod library also generates the prompt | Declarative, parsed by `lang-core`, rendered by `react-lang` | Yes: re-parse per chunk; shell paints first | Out of scope (library has an action mechanism) | Token-efficient streaming generative UI in React |
| **Harness** | The agent loop that drives everything | Messages + tool calls/results; **here** `render_ui`, `render_openui`, `render_html_artifact` | Produces validated UI output for a surface (web, terminal, AG-UI) | Events stream out as the loop runs | Central: allowlisted tools with Zod arguments | Joining UI generation to a real agent workflow |

## How the six differ from "arbitrary generated frontend code"

| Property | Declarative formats (A2UI, JSON Render, OpenUI Lang) | Arbitrary generated code |
|---|---|---|
| What the model emits | data naming approved components | HTML/JS/JSX |
| Validated by | schema / catalog | at best a lint or CSP |
| Failure mode | element rejected, rest renders | script runs (or breaks) |
| Needs a sandbox | no | yes (iframe sandbox + CSP, here) |
| Flexibility | catalog-bound | unbounded |

MCP Apps is the odd one out: its UI *is* HTML, so containment is the host's job (sandbox, CSP, tool allowlist). OpenUI's `HtmlArtifact` is the explicit hybrid escape hatch.

## OpenUI vs the others

- **vs A2UI**: OpenUI Lang is a language (compact text, positional) with a React renderer and Zod library; A2UI is a JSON message protocol with surfaces, a data model with bindings, and actions.
- **vs AG-UI**: OpenUI Lang is content; AG-UI is a transport that could carry it.
- **vs MCP Apps**: no host/iframe contract; the host app renders catalog components itself.
- **vs JSON Render**: same catalog idea, different encoding (line-oriented with forward references vs JSON element map).
- **vs generated code**: it cannot run code; only `HtmlArtifact` does, inside a sandbox.
