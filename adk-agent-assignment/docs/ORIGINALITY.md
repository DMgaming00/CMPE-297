# Originality Statement

For each part this lists what the reference does, what this repository does, and what
was added. All code in this repository was written for this submission. Ideas taken
from the references are credited here and in [REFERENCES.md](REFERENCES.md).

## A. Deep Research Lead Generation
**REFERENCE APPROACH:** an interactive root agent with an intent extractor; a pattern
discovery orchestrator (company finder → validator → per-company signal searchers via
a custom fan-out agent → synthesizer); a lead generation orchestrator (lead finder →
signal analyzer → report compiler); Pydantic schemas; user confirmation between phases.

**OUR IMPLEMENTATION:** an ADK `SequentialAgent` with a learn phase and a predict phase.
A fixed 5-slot `ParallelAgent` assigns companies at runtime through instruction
providers, and skip guards avoid unused model calls. Six structured stages carry the
data, and the report is generated from deterministic scores.

**OUR ADDITIONS / IMPROVEMENTS**
* **Deterministic qualification and scoring** (`scoring.py`): a documented formula,
  tiers, disqualification reasons and de-duplication. The reference leaves ranking to
  the LLM.
* **Grounding verification:** the source domains Google Search actually returned are
  captured from grounding metadata and used to credit citations.
* FACT and INFERENCE labelling on every signal, reflected in the score.
* A full pipeline test through ADK's Runner, plus scoring unit tests.
* *Credited idea:* the two-phase "learn from past entrants, then predict" structure and
  per-company signal research come from the reference.

## B. Gemini CLI Tool Agent
**REFERENCE APPROACH:** an ADK agent with a `gemini_cli(task, github_url)` tool that runs
`git clone "<url>"` and `gemini -p "<task>"` as **shell strings with `shell=True`**,
clones into a shared `/tmp/<repo>` that is reused and never cleaned, and deploys to
Cloud Run.

**OUR IMPLEMENTATION:** the same orchestration idea (ADK plans and synthesises, Gemini
CLI is the tool), rebuilt around a security boundary: validation → hardened clone →
untrusted-config stripping → headless JSON CLI run → parsing, redaction and citation
verification → cleanup.

**OUR ADDITIONS / IMPROVEMENTS**
* No shell; argv-only async execution. Injection through the URL or task is closed.
* A strict URL and ref allowlist with SSRF and option-injection protection.
* Git hardening, an environment allowlist, process-group timeouts, output caps, repo
  size limits and a concurrency limit.
* Gemini CLI `--output-format json` with stats; `--approval-mode plan`; untrusted-folder
  behaviour checked against gemini-cli 0.66.0.
* Verification of cited paths, commit provenance, and structured error codes.
* 62 tests and an opt-in real-CLI integration test.

## C. MCP Software Bug Assistant
**REFERENCE APPROACH:** an ADK agent using MCP Toolbox for Databases over Cloud SQL
(PostgreSQL + pgvector) for ticket search and updates, a Google Search agent tool, a
StackOverflow tool, and the GitHub MCP server.

**OUR IMPLEMENTATION:** an ADK agent that consumes ticket tools **over MCP in every
mode**. Locally it uses a repository MCP server (MCP SDK 2.x, stdio, SQLite). In
production it uses MCP Toolbox with a PostgreSQL schema. It also has a web-research
`AgentTool` and an optional read-only GitHub MCP server.

**OUR ADDITIONS / IMPROVEMENTS**
* A zero-cost local mode that is **still real MCP**, with MCP tool annotations.
* TF-IDF duplicate detection with calibrated thresholds, and duplicate refusal on
  create.
* A ticket status state machine (in Python and as a PostgreSQL trigger) and audit
  comments.
* A deterministic severity rubric (`assess_severity`) with SLAs.
* Code-enforced approval for all write tools; a read-only GitHub tool filter.
* MCP contract tests over stdio, Runner flow tests and an ADK eval set.
* *Credited idea:* Toolbox-backed tickets, the search sub-agent and the GitHub MCP
  integration come from the official sample.

## D. Code Review Assistant
**REFERENCE APPROACH:** a root agent routing to a review pipeline (code analyzer → style
checker → test runner that **executes generated tests** → feedback synthesizer with
history tools) and a fix pipeline (a `LoopAgent` of fixer → test runner → validator with
an `exit_fix_loop` tool, then a synthesizer).

**OUR IMPLEMENTATION:** a router with review and fix pipelines (same idea). The review
pipeline is a **deterministic AST engine** followed by **four parallel LLM specialists**
with structured output, then deterministic synthesis and a report writer. The fix
pipeline is a `LoopAgent` whose validator is a deterministic re-analysis that exits via
`escalate`.

**OUR ADDITIONS / IMPROVEMENTS**
* 30+ AST rules with intra-function taint tracking: SQL and command injection, eval,
  secrets, deserialization, TLS, crypto, traversal, SSRF, and correctness bugs.
* A P0–P3 model; every finding carries file, line, category, explanation and fix.
* Hallucination filtering (evidence must exist at the cited location).
* Prompt-injection resistance (models can't dismiss high-confidence P0/P1 findings).
* A rule-based verdict and a sandboxed workspace intake.
* Reviewed code is never executed (the reference executes tests). This is a deliberate
  safety trade-off.
* Vulnerable, buggy and clean fixtures, plus 23 tests including the full loop through
  the Runner.
* *Credited idea:* the review and fix dual pipeline with a loop exit comes from the
  reference.

## E. E-Commerce Agent
**REFERENCE APPROACH:** "Finn", a sports shop agent: ADK + `ToolboxToolset` + AlloyDB
(products, variants, stores, inventory, shopping lists, orders, delivery methods) +
AlloyDB AI vector search + Google Sign-In `authServices` for user parameters + a React
front end. Its `tools.yaml` contains plaintext DB credentials and a hard-coded OAuth
client ID. `place-order` runs from the shopping list as soon as the model calls it.

**OUR IMPLEMENTATION:** general merchandise (24 products, 5 stores, per-store inventory)
behind nine narrow MCP tools. Locally a repository MCP server (SQLite) serves them. In
production MCP Toolbox v1 manifests serve them over PostgreSQL or AlloyDB.

**OUR ADDITIONS / IMPROVEMENTS**
* A **quote → place** two-phase order that is atomic, idempotent and oversell-proof
  (DB constraint, tested with concurrent buyers).
* **Platform-enforced confirmation:** ADK tool confirmation via callback, plus a
  "quote must be prepared in this session" precondition and an itemised approval hint.
* **Identity binding:** the model-supplied `user_id` is always replaced. In production
  identity comes only from Toolbox-verified ID tokens.
* Least-privilege DB roles, env-substituted secrets, uniform not-found responses, and
  cancellation with restock.
* Seed SQL generated from the same JSON as local mode, with a sync test.
* *Credited ideas:* Toolbox `authServices` for user-scoped parameters and the AlloyDB
  store/inventory domain come from the reference.

## Shared infrastructure (original)
* `adk_shared.guardrails`: reusable `ConfirmationGate` and `IdentityBinder` callbacks
  for any tool type (function, MCP, Toolbox), plus MCP payload normalisation.
* `adk_shared.testing.ScriptedLlm`: a scripted model for deterministic ADK flow tests.
* Preflight, MCP smoke test, seed tooling, CI, Docker and compose.
