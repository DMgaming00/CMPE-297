# Architecture

## Layers

```mermaid
flowchart TB
  subgraph packages
    S[schemas: Zod catalog + A2UI messages]
    SH[shared: data, tools, builders, sandbox]
    UI[ui: JsonRender, SandboxedHtml, OpenUI catalog]
    HR[harness: loop, tools, models, AG-UI bridge]
    MS[mcp-server: 4 tools + ui:// view]
  end
  subgraph apps
    A1[json-render] & A2[openui] & A3[a2ui] & A4[agui] & A5[mcp-apps] & A6[harness] & A7[mixed-mode]
  end
  S --> SH --> UI
  SH --> HR
  SH --> MS
  UI --> A1 & A2 & A3 & A4 & A5 & A6 & A7
  HR --> A4 & A6 & A7
  MS --> A5 & A7
```

Each app is a Vite + React page. Its server half is a Vite dev-server middleware plugin (`apps/*/server/api.ts`), so `pnpm dev:<lab>` is one process. In production you would lift those handlers into a real server.

## Harness execution flow

```mermaid
sequenceDiagram
  participant U as User
  participant W as Web surface
  participant H as Harness loop
  participant M as Model
  participant T as Tools
  U->>W: prompt
  W->>H: POST /api/harness/run
  loop until no tool calls or maxSteps
    H->>M: messages + allowed tool specs
    M-->>H: text and/or tool calls
    H->>H: allowlist check, Zod args check
    H->>T: run tool
    T-->>H: result, or validation error (Error: ...)
  end
  H-->>W: SSE HarnessEvents (tool_call, tool_result, tool_error, ui, text)
  W->>W: render validated UiPayload
  U->>W: click button (named action)
  W->>H: action (closed set) → next turn
```

Errors: unauthorized tool, bad arguments, rejected spec, thrown tool → `tool_error` + `Error:` tool message; the loop continues. Model failure or step cap → `run_error`.

State: the transcript (`ChatMessage[]`) per session, held in memory (bounded). UI state is derived from the latest `ui` event.

Config: `HarnessConfig { maxSteps, allowedTools, system }`; provider via `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `HARNESS_MAX_STEPS`.

## Capstone flow

```mermaid
sequenceDiagram
  participant B as Browser (HttpAgent)
  participant A as /api/mixed/agui
  participant H as Harness
  participant C as MCP Client
  participant S as MCP Server
  B->>A: RunAgentInput
  A-->>B: RUN_STARTED, STATE_SNAPSHOT
  H->>C: search_items / compare_items / generate_summary
  C->>S: tools/call
  S-->>C: structuredContent
  A-->>B: TOOL_CALL_* (+ CUSTOM tool_source=mcp)
  H->>H: plan_ui → planRegions()
  A-->>B: STATE_DELTA add /regions/-  (static | declarative | open-ended)
  B->>B: re-validate, render per mode
  A-->>B: RUN_FINISHED
```

The planner (`apps/mixed-mode/server/planner.ts`) is ordinary code. Why: it is auditable and testable, and the *model* never gets to pick the riskiest mode on its own.

## MCP Apps flow

`Host` = the MCP client + policy + iframe + bridge. `Server` = tools + resources. The model sees only `content` (text). The view sees `structuredContent` through `ui/notifications/tool-result`. A `tools/call` from the view passes through the same host allowlist.

## Agent/server vs client responsibilities (A2UI)

| Agent / server | Client |
|---|---|
| decides structure and data; emits envelopes | validates every envelope against the catalog |
| answers `action` messages | owns the component implementations and styling |
| never sends code | owns local input state (two-way binding into the data model) |
