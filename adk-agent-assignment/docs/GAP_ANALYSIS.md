# Gap Analysis

This is a strict audit of the repository **as it was before the upgrade** (snapshot of
2026-10-29), compared with the assignment and the reference implementations. Every gap
listed was fixed in the current version. The **Resolution** column points to the fix.

Priority: **P0** assignment-breaking · **P1** major grade impact · **P2** worthwhile ·
**P3** polish.

## Cross-cutting findings

| # | Finding (original state) | Priority | Resolution |
|---|---|---|---|
| X1 | The test suite didn't pass: pytest's cache recorded **all five test files as failed**, and `google-adk` wasn't installable from the project. `pyproject.toml` had no package configuration in a flat layout with several top-level folders (`agents`, `mcp`, `scripts`, `sample_data`). | P0 | Proper `[tool.setuptools.packages.find]`; 186 tests now pass |
| X2 | `mcp/bug_server.py` used `mcp.server.fastmcp.FastMCP`, **which was removed in MCP SDK 2.x** (the version current ADK installs), so the MCP server couldn't start. The top-level `mcp/` folder also shadowed the `mcp` package name. | P0 | Servers rewritten on `mcp.server.mcpserver.MCPServer`; folder removed |
| X3 | Default models `gemini-2.5-flash` / `gemini-2.5-pro` are "access limited to past users" according to the Gemini models page (checked 2026-10-29), so a fresh account would fail. | P1 | Current defaults (`gemini-3.8-flash`), configurable |
| X4 | ADK version not verified: `google-adk>=1.14` with no upper bound. ADK 2.x changed module layout and MCP integration. | P1 | Pinned `google-adk[mcp]>=2.13,<3`, `mcp>=2,<3`, with the reason documented |
| X5 | `docs/YOUTUBE_SCRIPT.md`, a stale `MANIFEST.txt` that listed `.pytest_cache`, committed `.DS_Store` files, `.pytest_cache/`, and a minimal `.gitignore`. | P2 | Removed; `.gitignore` and `.dockerignore` hardened |
| X6 | Dockerfile piped `curl … \| bash` (NodeSource), ran as root, used `pip install .` without a working package config, and served the `adk web` dev UI as the production command. | P2 | Multi-stage build, pinned Gemini CLI, non-root user, `api_server` default |
| X7 | No preflight beyond 6 checks, no seed or smoke tooling, no eval assets, no security, testing or deployment docs. | P2 | `scripts/`, `agents/*/eval/`, `docs/` |
| X8 | `.env.example` contained `DATABASE_URL=postgresql://postgres:postgres@…`, a real-looking default credential. | P3 | Placeholders only, grouped by area |

## A. Deep Research Lead Generation

| Aspect | Assessment |
|---|---|
| Requirement | Genuine multi-stage research: historical entrants → expansion evidence → signals → patterns → new companies → qualification/scoring → structured report with evidence |
| Original implementation | `SequentialAgent` of 5 `Agent`s with `google_search`, passing free text through `output_key` |
| Correct | Learn-then-predict ordering; prompts asked for sources and labelled inferences |
| Weak | No structured outputs: each stage passed unvalidated prose. No per-company research, unlike the reference's fan-out. Qualification and ranking were left entirely to the LLM. |
| Missing | Scoring, disqualification rules, de-duplication, source validation, grounding capture, tests beyond "agent name exists" |
| Misleading | README claimed the final stage "rejects contradictory/weak candidates", but nothing enforced it |
| vs reference | The reference has intent extraction, structured schemas, a per-company parallel signal search and a pattern synthesizer |
| Required upgrade (done) | Pydantic schemas per stage; 5-slot parallel signal research with skip guards; deterministic `LeadScoringAgent`; grounding-metadata capture; FACT/INFERENCE labels; full-pipeline scripted test |
| Priority | **P1** |

## B. Gemini CLI Tool Agent

| Aspect | Assessment |
|---|---|
| Requirement | ADK → tool → **real Gemini CLI** → repo task → result → ADK synthesis, secured against injection, malicious URLs, timeouts, cleanup and leaks |
| Original implementation | `gemini_cli(task, github_url)` with a regex URL check, `git clone --depth 1`, then `gemini -p task` via `subprocess.run` argv lists |
| Correct | argv lists (no `shell=True`); a temp dir via `TemporaryDirectory`; HTTPS + github.com check; output tail-truncated |
| Weak | The URL regex accepted `..`, names starting with `-` and dotted traversal. There was no `--` before the URL. The subprocess timeout killed only the direct child (Gemini CLI is Node and can leave grandchildren). Output was buffered unbounded in memory before truncation. Blocking sync calls ran in the event loop. |
| Missing | Environment allowlist (the CLI received every secret in the environment); git hardening (hooks, symlinks, protocols, user gitconfig `insteadOf`); untrusted `.gemini/` and `GEMINI.md` handling; JSON output parsing; read-only approval mode; ref support; repo size limits; concurrency limit; provenance (commit); verification of cited paths; tests for subprocess failure, timeout and cleanup |
| Misleading | None significant |
| vs reference | The reference used `shell=True` with string interpolation (command injection) and a shared, never-cleaned `/tmp/<repo>` |
| Required upgrade (done) | `security.py`, `runner.py`, `workspace.py` (see the agent README); 62 tests; checked against the real gemini-cli 0.66.0 |
| Priority | **P1** |

## C. MCP Bug Assistant

| Aspect | Assessment |
|---|---|
| Requirement | Must meaningfully demonstrate MCP: search, details, triage, duplicates, severity, debugging, create/update. Local fallback must be clearly distinguished from production MCP |
| Original implementation | Agent used **plain Python functions** (`search_tickets`, `create_ticket`) over an in-memory list. A separate `mcp/bug_server.py` was never connected to the agent. |
| Correct | Intent to separate a local adapter from an MCP server; web search sub-agent |
| Weak | Keyword set intersection for search; no duplicate scoring |
| Missing | **Any MCP usage by the agent** (P0); get, update, status, priority, comment and mark-duplicate tools; severity model; write confirmation; Toolbox config for tickets; MCP contract tests |
| Misleading | The README called it an "MCP bug assistant" and the docs said the agent used "Ticket tools / MCP Toolbox", but the running agent used no MCP at all. The MCP server didn't start on current SDKs (X2). |
| vs reference | The official sample wires MCP Toolbox (Cloud SQL tickets) and a GitHub MCP server into the agent |
| Required upgrade (done) | Agent consumes MCP via `McpToolset` (stdio) or `ToolboxToolset`; 9 annotated MCP tools; TF-IDF duplicates; state machine; audit trail; severity rubric; approval-gated writes; Toolbox YAML + schema; contract and flow tests |
| Priority | **P0** |

## D. Code Review Assistant

| Aspect | Assessment |
|---|---|
| Requirement | Serious specialist review: correctness, AST, security, style, tests, severity, synthesis, fixes, optional fix/re-review loop; findings with file, line, severity, category, explanation and recommendation; P0–P3 model |
| Original implementation | `SequentialAgent` of 6 LLM agents; tools for AST metrics, pycodestyle (via a temp file) and a **substring search** for `eval(`, `shell=True` and similar |
| Correct | Code is never executed; deterministic tools for metrics; P0–P3 mentioned in the synthesis prompt |
| Weak | The substring scan flagged comments and strings and missed `eval (`, SQL injection, path traversal and SSRF. The temp-file style check breaks on Windows. LLM synthesis alone decided severity. |
| Missing | Structured findings model; file/line anchoring; correctness rules; test-gap analysis; parallel specialists; hallucination or prompt-injection defences; deterministic verdict; fix loop; vulnerable fixtures; meaningful tests |
| Misleading | None |
| vs reference | The reference has a review pipeline plus a `LoopAgent` fix pipeline with a validator and an exit tool |
| Required upgrade (done) | AST engine (30+ rules, taint), 4 parallel structured specialists, deterministic synthesis and verdict, fix loop with deterministic validator, sandboxed intake, fixtures, 23 tests |
| Priority | **P1** |

## E. E-Commerce Agent

| Aspect | Assessment |
|---|---|
| Requirement | ADK → MCP / MCP Toolbox → AlloyDB/PostgreSQL; search, details, inventory, stores, order prep/creation/lookup/status, safe updates, user scoping, confirmation before consequential operations |
| Original implementation | 3 hard-coded products in a Python list; `create_order(user_id, sku, quantity, confirmed=False)` |
| Correct | Rejected unconfirmed orders; owner check on `get_order`; tests for both |
| Weak | **`confirmed` was a parameter the LLM sets itself**, so a confused or injected model could call `create_order(..., confirmed=True)` directly. The confirmation was only a prompt convention (P0 safety gap). **`user_id` was chosen by the LLM**, so any user's orders were reachable by asking. Floats for money. No concurrency safety. |
| Missing | MCP in the agent; store lookup; per-store inventory; order status list; cancellation; idempotency; quote expiry; Toolbox tools for orders and inventory (the YAML had only 2 read tools in an older format); production auth for identity |
| Misleading | Docs and README described an "MCP Toolbox + AlloyDB" agent, but the agent never used MCP. `ARCHITECTURE_OVERVIEW.md` said "SQLite demo store" while the code was in-memory. |
| vs reference | The reference uses Toolbox with `authServices` (Google Sign-In) to bind identity, plus AlloyDB with stores, inventory, variants and orders |
| Required upgrade (done) | Local MCP server (SQLite, transactional); Toolbox v1 YAML with 9 tools and ID-token identity; PostgreSQL schema with least-privilege role; `IdentityBinder`; ADK tool-confirmation gate; quote precondition; 24 tests including concurrency and spoofing |
| Priority | **P0** |

## Summary
Two parts (C and E) were assignment-breaking because they claimed MCP or Toolbox
behaviour the running agents didn't have. Two (B and D) were functional but fell short
of a production standard. A needed structure and verifiable ranking. All gaps above
have been implemented. The remaining limits are listed honestly in
[FINAL_AUDIT.md](FINAL_AUDIT.md) and [SECURITY.md](SECURITY.md).
