# Final Audit (strict self-assessment)

This audit grades the repository against the assignment the way a demanding reviewer
would. Scores reflect **what has been verified**, not what is designed. Evidence
refers to files and commands in this repository. Audit date: 2026-10-30.

| Area | Score | Evidence | Remaining risk |
|---|---:|---|---|
| Assignment coverage | 96 | All five parts implemented with their required workflows (A–E sections of README; [GAP_ANALYSIS](GAP_ANALYSIS.md) items all resolved). The video is produced separately by the author. | None structural |
| Actual functionality | 84 | Deterministic paths run: 186 tests including full ADK Runner flows for A, C, D and E; real MCP over stdio; real `adk api_server` loads all 5 apps, locally and in the Docker image; real Gemini CLI + real GitHub clone exercised up to authentication. | **No live Gemini conversation was run** in this environment (no credentials). Prompt quality and model behaviour are unverified until the author runs the walkthrough and `adk eval`. |
| Google ADK usage | 95 | ADK 2.13 APIs checked from the installed source: Sequential, Parallel and Loop agents with `escalate`; custom `BaseAgent`s; `output_schema`; instruction providers; agent and model callbacks; tool callbacks; tool confirmation; `AgentTool`; `McpToolset` (stdio/HTTP); `ToolboxToolset`; transfer; `adk eval` sets ([ARCHITECTURE](ARCHITECTURE.md#adk-feature-map)) | The workflow agents are deprecated in ADK 2.x in favour of `Workflow` (documented decision) |
| Multi-agent sophistication | 93 | A: 10-stage two-phase pipeline with parallel fan-out and deterministic scorer. D: router → review pipeline (parallel specialists) / fix loop with deterministic validator | A's fan-out is capped at 5 fixed slots |
| Gemini CLI integration | 89 | Real CLI invoked headless with JSON output; flags checked against gemini-cli 0.66.0; hardened clone; 62 tests; observed exit-41 auth behaviour handled; CLI baked into the image | A successful authenticated analysis wasn't run here. Run `make integration` with credentials. |
| MCP correctness | 93 | Two MCP SDK 2.x servers with annotated tools; agents consume them through `McpToolset` stdio; contract tests over the real transport; `mcp_smoke.py`; Toolbox v1 manifests with tool parity tests; no local function is called MCP | Toolbox servers and the GitHub MCP server were not started here |
| Code review quality | 93 | 30+ AST rules with taint; every planted fixture defect found; zero findings on the clean fixture; hallucination and anti-injection validation; rule-based verdict; verified fix loop | Python only; heuristics (no inter-procedural analysis) |
| Commerce architecture | 89 | Quote → place two-phase design, idempotent, oversell-proof (concurrency test); identity binding; code-enforced ADK confirmation; Toolbox `authServices`; least-privilege schema; compose stack | The PostgreSQL/Toolbox SQL is statically validated only: **not executed against a live database** |
| Code quality | 91 | Typed, modular packages; shared guardrails; ruff clean (E, F, W, I, B, UP, S, SIM, RUF); structured errors; safe logging | Some long prompt modules; no mypy gate |
| Tests | 93 | 186 passing (+1 opt-in): unit, MCP contract, ADK flow, config, hygiene; clean-venv install reproduced; test doubles labelled | No coverage measurement; no eval results recorded |
| Security | 92 | [docs/SECURITY.md](SECURITY.md) maps 20 threats to controls and tests; no `shell=True`; env allowlists; parameterised SQL; no-execute reviewer; IDOR and purchase gates | Residual risks listed (dev UI unauthenticated, no rate limiting, prompt injection can still degrade answers) |
| Reproducibility | 93 | `pip install -e ".[dev]"` from a fresh venv → 186 passed; `scripts/setup.sh`, `preflight.py` (PASS/WARN/FAIL), seed tooling; Docker image built and smoke-tested | CI workflow has not run yet (not pushed); cloud steps require the author's project |
| Documentation | 94 | Root README with 6 diagrams; 5 agent READMEs with 14 sections each; architecture, walkthrough, deployment, security, testing, references, originality, checklist; 18/18 Mermaid blocks parse with the Mermaid parser; internal links checked | Screenshots of real runs would strengthen it |
| Originality | 92 | [ORIGINALITY.md](ORIGINALITY.md): per-part reference vs implementation vs additions; no reference code copied; credited ideas named | — |

## Overall: **91 / 100**

### What keeps this below 95
1. **Unverified model behaviour.** Nobody has run a real Gemini conversation, an `adk
   eval`, or an authenticated Gemini CLI analysis against this code yet. This is the
   largest risk.
2. **The production data plane hasn't been executed.** The Toolbox YAML and PostgreSQL
   SQL follow the official docs and pass static checks, but `docker compose up` was not
   run during development.
3. **CI status is unknown** until the workflow runs on GitHub.

### Fastest path to 95+ (author actions, about 1–2 hours)
1. Add credentials to `.env`, run every prompt in [EXECUTION_WALKTHROUGH.md](EXECUTION_WALKTHROUGH.md),
   and fix any prompt-level issues you see.
2. Run `make integration` and `make eval`, then record the real results in
   [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md).
3. Run `make toolbox-up` and the [production verification](TESTING.md#production-toolbox-verification)
   steps. Fix any SQL errors Toolbox reports.
4. Push, confirm the CI run is green, and then (only then) add a CI status badge.

### Issues found and fixed during this audit
* `cancel_order` raised `KeyError: 'store_id'`. This was caught by a test and fixed.
* `$999` inside SQL money formats looked like a placeholder. Rewritten to avoid the
  ambiguity.
* The skip callback returned non-JSON for structured-output agents, so ADK schema
  validation would fail. Now it returns a schema-valid empty review.
* Gemini CLI writes its JSON error to stderr, not stdout. Parsing now falls back to
  stderr (observed with the real 0.66.0 binary).
* The duplicate-detection threshold was mis-calibrated (0.45). It was recalibrated to
  0.28 from measured score distributions.
* A Mermaid label with a comma failed to parse. Fixed and re-validated.
