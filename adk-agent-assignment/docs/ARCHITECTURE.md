# Architecture

## Design principles
1. **Each agent shows a different ADK pattern.** Agents A–E aren't five copies of one
   chatbot.
2. **Models reason, code decides.** Anything that must be correct is deterministic
   Python, implemented as tools, custom agents or callbacks:
   * rankings (A);
   * process isolation (B);
   * ticket integrity (C);
   * verdicts (D);
   * purchases (E).
3. **Guardrails live outside the prompt.** Confirmation and identity are ADK callbacks
   that a prompt-injected model can't skip.
4. **Every protocol claim is literal.** "MCP" always means the MCP protocol. Local
   functions are labelled as local.

## ADK feature map

| ADK capability | Where it is used |
|---|---|
| `LlmAgent` with tools | B, C, E (root agents); D intake/fixer |
| `SequentialAgent` | A (root, both phases), D (review and fix pipelines) |
| `ParallelAgent` | A (signal research panel), D (specialist panel) |
| `LoopAgent` + `escalate` | D fix loop (exits when the deterministic validator passes) |
| Custom `BaseAgent` (no LLM) | A `LeadScoringAgent`; D `StaticAnalysisAgent`, `FindingsSynthesisAgent`, `FixValidationAgent` |
| `output_schema` (Pydantic structured output) + `output_key` | A (6 stages), D (4 specialists) |
| Instruction providers (callables) | A (inject research state as JSON) |
| `include_contents="none"` | A/D downstream stages: state-driven, no chat-history leakage |
| `before_agent_callback` | A slot guards, D skip-if-no-code and review reset |
| `after_model_callback` | A Google Search grounding capture |
| `before_tool_callback` / `after_tool_callback` | C/E confirmation gate, E identity binder, E quote tracking |
| Tool confirmation (`request_confirmation`, `adk_request_confirmation`) | C writes, E `place_order` / `cancel_order` |
| `AgentTool` | C web research sub-agent |
| Built-in `google_search` | A researchers, C web research |
| `McpToolset` + `StdioConnectionParams` | C, E local MCP mode |
| `McpToolset` + `StreamableHTTPConnectionParams` + `tool_filter` | C optional GitHub MCP (read-only) |
| `ToolboxToolset` (`auth_token_getters`) | C, E production mode |
| Agent transfer (`sub_agents`) | D router to the review or fix pipeline |
| Session state | All agents; D/A pipelines are fully state-driven |
| `adk eval` eval sets | C, D, E (`agents/*/eval/`) |

> ADK 2.x marks `SequentialAgent`, `ParallelAgent` and `LoopAgent` as deprecated in
> favour of the graph-based `Workflow` API. They remain fully supported in 2.13.
> `Workflow` can't yet be used as an `LlmAgent` sub-agent, which agent D's router
> requires. These agents were therefore kept for consistency. Migrating A to `Workflow`
> is a self-contained follow-up.

## Shared guardrail sequence (agents C and E)

```mermaid
sequenceDiagram
    autonumber
    participant M as Gemini (LlmAgent)
    participant CB as before_tool_callback<br/>(IdentityBinder → ConfirmationGate)
    participant H as Human (ADK Web / client)
    participant MCP as MCP server / Toolbox
    M->>CB: place_order(user_id="cust-bob", quote_id=Q)
    CB->>CB: overwrite user_id with session identity
    CB->>CB: precondition: Q prepared in this session?
    CB-->>M: {"status": "awaiting_user_confirmation"}
    CB-->>H: adk_request_confirmation(hint: "1 x Bottle … total $27.99")
    H->>CB: FunctionResponse {confirmed: true}
    CB->>MCP: place_order(user_id="cust-alice", quote_id=Q)
    MCP-->>M: {"ok": true, "order": {...}}
```

The same sequence is executed by `agents/ecommerce/tests/test_agent_flow.py` through
ADK's real Runner and the real MCP stdio server.

## A. Lead research: state flow

```mermaid
flowchart LR
    rb[research_brief] --> he[historical_entrants]
    he --> sn["signal_notes_0..4"]
    sn --> hs[historical_signals]
    hs --> ep[expansion_patterns]
    ep --> lrn[lead_research_notes] --> cl[candidate_leads]
    cl --> sl[scored_leads + scored_leads_md]
    g["grounding_* (per search agent)"] --> sl
    sl --> report((final report))
```

## B. Gemini CLI: process isolation

```mermaid
flowchart TB
    subgraph ADK_PROCESS [ADK process]
        T[run_gemini_cli_analysis] -->|validate| V{{URL, ref, task_type}}
        V -->|asyncio semaphore| W
    end
    subgraph W [Per-run temp dir: adk-gemini-XXXX]
        G1["git (argv) · env: no user gitconfig, no prompts, no LFS<br/>-c protocol.allow=never -c core.symlinks=false -c core.hooksPath=/dev/null"]
        G1 --> STRIP[remove .gemini/, GEMINI.md]
        STRIP --> CLI["gemini --prompt P --output-format json --approval-mode plan<br/>env allowlist · new process group · timeout · capped pipes"]
    end
    CLI --> PARSE[parse JSON · redact · verify paths]
    PARSE --> CLEAN[rm -rf temp dir · always]
```

## C. Bug assistant: MCP boundary

```mermaid
flowchart LR
    subgraph ADK [ADK process]
        AG[LlmAgent] --> GATE{{ConfirmationGate}}
        GATE --> MCPC[McpToolset · MCP client]
        AG --> SEV[assess_severity · local]
        AG --> WR[web_research_agent · AgentTool]
    end
    MCPC <== "JSON-RPC over stdio<br/>initialize · tools/list · tools/call" ==> SRV
    subgraph SRV [MCP server process]
        TOOLS[9 annotated tools] --> STORE[TicketStore<br/>validation · state machine · audit]
        STORE --> SQL[(SQLite WAL)]
    end
```

## D. Code review: finding lifecycle

```mermaid
flowchart LR
    SRC[source files] --> AST[AST rules + taint] & STY[pycodestyle] & TST[test-gap analysis]
    AST & STY & TST --> SF[static findings<br/>id = RULE:file:line]
    SF --> SP[4 specialists<br/>structured SpecialistReview]
    SP --> VAL{validate}
    VAL -->|file/line exists and evidence quoted| KEEP[accepted LLM findings]
    VAL -->|otherwise| DROP[dropped as hallucination]
    SP -->|reject static id| DISP{high-confidence P0/P1?}
    DISP -->|yes| KEPT[kept, marked disputed]
    DISP -->|no| REM[removed]
    KEEP & SF --> MERGE[dedupe ±2 lines · sort by severity] --> VERD[verdict rule]
```

## E. E-commerce: data model

```mermaid
erDiagram
    users ||--o{ quotes : prepares
    users ||--o{ orders : owns
    products ||--o{ inventory : stocked
    stores ||--o{ inventory : holds
    quotes ||--o| orders : "consumed by (UNIQUE)"
    products {
        text sku PK
        int price_cents
    }
    inventory {
        text store_id PK
        text sku PK
        int quantity "CHECK >= 0"
    }
    quotes {
        text quote_id PK
        text status "open or consumed"
        timestamptz expires_at
    }
    orders {
        text order_id PK
        text quote_id UK
        text status
    }
```

## Concurrency and scale ("what breaks with 100 users?")

| Concern | Mitigation in this repo | Remaining limit |
|---|---|---|
| Oversell under concurrent purchase (E) | `BEGIN IMMEDIATE` + conditional decrement (SQLite); single-statement CTE + `CHECK (quantity >= 0)` (PostgreSQL); tested with 4 threads | SQLite serialises writers. Production uses PostgreSQL. |
| Duplicate submission / retries (E) | Idempotent `place_order` per quote (`UNIQUE(quote_id)`) | — |
| Cross-user access (E) | Identity forced by callback; every query scoped by user; Toolbox auth params | Local identity mapping is a demo convenience |
| Many Gemini CLI runs (B) | Per-loop semaphore (`GEMINI_CLI_MAX_CONCURRENCY`), per-run temp dirs, process-group kill, capped output, repo size limits | Clones use disk and network. Use a Cloud Run job for scale. |
| Model returning malformed JSON (A, D) | Pydantic `output_schema`; deterministic stages validate state and degrade with warnings | A malformed specialist output is ignored, so coverage drops |
| Tool / MCP failures | Structured `{ok:false,error:{code,message}}` results; MCP `isError` mapped; stdio timeout configurable | No automatic retries with backoff |
| Session state growth | Listings capped (60 KB), findings capped (25), grounding sources capped | In-memory sessions by default. Use a DB session service. |
| Rate limits / quotas | Model names configurable; fewer calls via skip guards and deterministic stages | No client-side rate limiter |
