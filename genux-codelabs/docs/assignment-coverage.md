# Assignment coverage

| Requirement | Implementation | Files | Run command |
|---|---|---|---|
| A2UI | v0.9.x envelopes validated with Zod; surface store (components + data model, JSON Pointer bindings, `sendDataModel`); native renderer for a Basic Catalog subset; action round-trip; rejected-message tolerance | `apps/a2ui/src/a2ui/store.ts`, `Surface.tsx`, `server/agent.ts`, `packages/schemas/src/a2ui.ts` | `pnpm dev:a2ui` |
| AG-UI | Official `@ag-ui/client` `HttpAgent` + `@ag-ui/encoder` + `@ag-ui/core`; five runs: tool call → component, state delta → spec, CUSTOM → sandbox, frontend-tool approval, harness bridge | `apps/agui/server/agent.ts`, `server/api.ts`, `src/App.tsx`, `packages/harness/src/agui-bridge.ts` | `pnpm dev:agui` |
| MCP Apps | Official `@modelcontextprotocol/sdk` server with `search_items`, `get_item_details`, `compare_items`, `generate_summary`, a `ui://` view resource and `_meta.ui.resourceUri`; host with MCP client, tool/resource allowlist, sandboxed iframe, JSON-RPC bridge; stdio entry | `packages/mcp-server/src/*`, `apps/mcp-apps/server/api.ts`, `src/bridge.ts`, `src/McpFrame.tsx` | `pnpm dev:mcp`, `pnpm mcp:stdio` |
| JSON Render | Zod catalog (Card, Stack, Text, Button, Badge, Metric, Table, Alert, Form), strict props, structural checks, strict + lenient validation, registry renderer, error boundary | `packages/schemas/src/json-render.ts`, `packages/ui/src/JsonRender.tsx`, `apps/json-render/src/App.tsx` | `pnpm dev:json-render` |
| OpenUI | **OpenUI Lang** with `@openuidev/lang-core` / `react-lang`: Zod-defined library, generated system prompt, streamed program, malformed-output handling, `HtmlArtifact` hybrid | `packages/ui/src/openui.tsx`, `apps/openui/src/App.tsx`, `apps/openui/server/api.ts` | `pnpm dev:openui` |
| Harness | Agent loop with allowlisted Zod tools, `render_ui` / `render_openui` / `render_html_artifact`, error-correction loop, step cap, scripted + OpenAI-compatible models, web + terminal + AG-UI surfaces | `packages/harness/src/*`, `apps/harness/server/api.ts`, `apps/harness/src/App.tsx` | `pnpm dev:harness`, `pnpm harness:cli "…"` |
| Static UX | `ItemCard`; A2UI/JSON Render/OpenUI static tabs; AG-UI tool-name → component | `packages/ui/src/ItemCard.tsx`, `apps/*/src/App.tsx` (Static tabs) | any lab |
| Declarative UX | JSON Render, A2UI, OpenUI Lang, AG-UI state spec, harness `render_ui` | see rows above | `pnpm dev:json-render` |
| Open-ended UX | `SandboxedHtml` (iframe sandbox + CSP + document check + message allowlist); OpenUI open-ended tab; AG-UI CUSTOM; MCP malicious-view demo; harness widget. **Not faked** for JSON Render and A2UI (explained in their tabs) | `packages/shared/src/sandbox.ts`, `packages/ui/src/SandboxedHtml.tsx` | `pnpm dev:openui` |
| Mixed UX | OpenUI hybrid (`HtmlArtifact`) and the capstone: harness → MCP → AG-UI → planner choosing static / declarative / open-ended per region with rationale and degrade path | `apps/mixed-mode/server/planner.ts`, `pipeline.ts`, `src/App.tsx` | `pnpm dev:mixed` |
| Docs / diagrams | Root README, concepts, architecture (Mermaid), comparison, per-lab READMEs | `README.md`, `docs/*`, `apps/*/README.md` | — |
| Tests / quality | lint, typecheck, 45 tests, build | `tests/*` | `pnpm lint && pnpm typecheck && pnpm test && pnpm build` |

### Mode applicability per technology

| | Static | Declarative | Open-ended | Mixed |
|---|---|---|---|---|
| A2UI | baseline form | ✅ core | ✗ by design (no code field) | → capstone |
| AG-UI | ✅ (tool→component) | ✅ (state spec) | ✅ (CUSTOM → sandbox) | → capstone |
| MCP Apps | ✅ (fixed view) | ✅ (view renders `structuredContent.kind`) | ✅ (view is HTML; host sandbox) | partial |
| JSON Render | ✅ | ✅ core | ✗ no code field | → capstone |
| OpenUI | ✅ (hand-written program) | ✅ core | ✅ (sandbox tab) | ✅ `HtmlArtifact` |
| Harness | ✅ | ✅ | ✅ | ✅ |
