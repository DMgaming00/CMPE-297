# Testing

## Layers

| Layer | What it proves | Needs credentials? | Command |
|---|---|---|---|
| Unit tests | Deterministic logic: scoring, validators, analyzers, stores, security | No | `pytest -q` |
| MCP contract tests | The local MCP servers speak MCP over real stdio: tools, annotations, schemas, structured errors | No | included in `pytest` |
| ADK flow tests | ADK's real `Runner`, state, transfers, callbacks, structured output, loops and **tool confirmation**, with a scripted model (`adk_shared/testing.py::ScriptedLlm`) | No | included in `pytest` |
| Static config tests | Toolbox YAML parameter parity, auth params, no plaintext credentials, seed SQL in sync | No | included in `pytest` |
| MCP smoke | Interactive proof of both MCP servers | No | `python scripts/mcp_smoke.py` |
| Integration (opt-in) | The real Gemini CLI against a real GitHub repository | Gemini CLI auth + network | `RUN_GEMINI_CLI_INTEGRATION=1 pytest -m integration` |
| ADK eval | Model behaviour: tool trajectories and response quality | Gemini credentials | `make eval` |
| Production verification (manual) | Toolbox + PostgreSQL/AlloyDB execute the SQL | Docker, plus an OAuth client for user-scoped tools | see below |

**Test doubles are labelled:**
* `ScriptedLlm` replaces Gemini in flow tests.
* A **fake `gemini` executable** (in `agents/gemini_cli_agent/tests/conftest.py`)
  replaces the real CLI in tool tests. Its auth-error output reproduces a real
  gemini-cli 0.66.0 run.

Nothing in the unit suite claims real Gemini or real CLI execution.

## Results from the development machine (2026-10-30)

| Command | Result |
|---|---|
| `python -m compileall -q agents adk_shared scripts tests` | success |
| `ruff check .` | All checks passed |
| `pytest -q` | **186 passed, 1 skipped** (the opt-in integration test) |
| `python scripts/mcp_smoke.py` | both servers: 9 tools each, calls succeed |
| `python scripts/preflight.py` | 20 PASS, 5 WARN (no `.env`, no model key, Gemini CLI not on PATH, no gcloud, no Toolbox binary), 0 FAIL |
| `adk api_server agents` + `GET /list-apps` | all 5 apps listed, sessions created (HTTP 200) |
| Real gemini-cli 0.66.0 + real clone of `pallets/markupsafe` (no credentials) | clone, config stripping and CLI invocation worked; CLI returned its structured auth error (exit 41), reported as `CLI_FAILED` |
| Fresh `python3.11 -m venv` + `pip install -e ".[dev]"` + `pytest -q` | install OK (google-adk 2.13.0, mcp 2.3.0); 186 passed, 1 skipped |
| `docker build .` + `docker run` | image built; runs as uid 10001; `gemini --version` 0.66.0; `GET /list-apps` lists all 5 apps |
| Mermaid parse (mermaid npm parser on every ```` ```mermaid ```` block) | 18 ok, 0 failed |

**Not run:** conversations with Gemini, `adk eval`, the real-CLI integration test with
credentials, Toolbox/PostgreSQL/AlloyDB (`docker compose`), and Cloud Run. No credentials,
Toolbox binary or cloud project were used in this environment. CI hasn't run. Note that
GitHub runs workflows only from the repository root, so `.github/workflows/ci.yml` won't
trigger while this project sits in a subfolder of another repository (see the checklist).

## Highlights by agent
* **A (14):** scoring maths, tiers, every disqualification rule, de-duplication,
  grounding bonus, determinism; a full 10-stage pipeline run through the Runner.
* **B (62 + 1 opt-in):**
  * 26 hostile URLs, refs, hardened argv;
  * shell metacharacters staying one argument;
  * environment secret filtering;
  * a timeout killing grandchildren;
  * output caps, missing binary, non-zero exit;
  * cleanup on success, failure and exception;
  * size limits, config stripping, path verification;
  * JSON parsing, plus the real-CLI integration test.
* **C (34):**
  * search, filters and duplicates (paraphrases and non-duplicates);
  * duplicate refusal, validation, the state machine, the audit trail;
  * the severity policy;
  * the MCP stdio contract;
  * approval-gated writes through the Runner;
  * the GitHub read-only filter.
* **D (23):**
  * every planted vulnerability and bug is detected, and the clean fixture is clean;
  * no false positives on safe SQL or subprocess calls;
  * the reviewer never executes code;
  * workspace traversal and symlink blocking;
  * hallucination and dispute rules;
  * review → fix loop through the Runner.
* **E (24):**
  * search, invalid product, inventory;
  * invalid quantities, unavailable stock;
  * prepare vs place, idempotency, expiry;
  * a 4-thread race for the last unit;
  * user isolation, cancellation, DB constraint;
  * the MCP stdio contract;
  * identity spoofing, approval, rejection and fabricated quotes through the Runner.
* **Shared and repository (29):**
  * guardrails, payload extraction, redaction;
  * Toolbox config validation;
  * all agents load the way `adk web` loads them;
  * READMEs present, no video files, `.env.example` placeholders only, `.gitignore`
    coverage.

## ADK evaluation
Eval sets are in `agents/{ecommerce,bug_assistant,code_review}/eval/`, built with ADK's
`EvalSet` model, and a unit test validates them. The criteria are:
```json
{"tool_trajectory_avg_score": {"threshold": 0.8, "match_type": "IN_ORDER", "ignore_args": true},
 "final_response_match_v2": {"threshold": 0.6}}
```
```bash
pip install -e ".[eval]"
adk eval agents/ecommerce agents/ecommerce/eval/ecommerce.evalset.json \
  --config_file_path agents/ecommerce/eval/test_config.json --print_detailed_results
```
No eval scores are reported in this repository because they weren't run. Record your
own results in the checklist.

## Production Toolbox verification
Run these steps to turn "statically validated" into "executed":
```bash
docker compose up -d            # PostgreSQL 16 + 2 Toolbox containers
docker compose logs toolbox-commerce | head   # expect: initialized N tools, listening on 5000
# Toolbox UI / API, read-only tool (no auth needed):
curl -s -X POST http://127.0.0.1:5000/api/tool/search_products/invoke \
  -H 'content-type: application/json' -d '{"query":"waterproof","limit":3}'
curl -s -X POST http://127.0.0.1:5001/api/tool/search_tickets/invoke \
  -H 'content-type: application/json' -d '{"query":"checkout coupon"}'
# Agent against Toolbox:
pip install -e ".[production]"
ECOMMERCE_BACKEND=toolbox BUG_TRACKER_BACKEND=toolbox adk web agents
```
User-scoped commerce tools need a Google ID token whose `aud` matches
`GOOGLE_OAUTH_CLIENT_ID` (see [DEPLOYMENT.md](DEPLOYMENT.md#5-front-end-identity-e-in-production)).
To verify oversell protection in PostgreSQL, prepare two quotes for the last unit of
`OUT-201` at `ST-SJC` and place both: the second must return no row, and stock must
stay at 0.
