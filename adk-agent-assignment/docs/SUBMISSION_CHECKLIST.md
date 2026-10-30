# Submission Checklist

Items marked **[x]** were verified on the development machine on 2026-10-30 (see
[TESTING.md](TESTING.md)). Items marked **[ ]** need your credentials, cloud project or
GitHub, so they are your responsibility before submitting.

## Build and quality
- [x] Clean installation succeeds: fresh venv + `pip install -e ".[dev]"` (adk 2.13.0, mcp 2.3.0)
- [x] `python scripts/preflight.py` reports 0 FAIL (WARNs are optional tooling and credentials)
- [x] `python -m compileall -q agents adk_shared scripts tests` succeeds
- [x] `pytest -q` → 186 passed, 1 skipped (opt-in integration)
- [x] `ruff check .` → all checks passed
- [x] `python scripts/mcp_smoke.py` → both MCP servers list 9 tools and answer calls
- [x] `adk api_server agents` lists all five apps; sessions are created
- [x] `docker build .` succeeds; the container runs as non-root, includes Gemini CLI 0.66.0, and serves all five apps
- [ ] GitHub Actions CI is green. GitHub only runs workflows from a repository's root `.github/workflows/`. While this project lives in the `adk-agent-assignment/` subfolder of CMPE-297, `ci.yml` won't trigger; copy it to the repo root (and add `working-directory: adk-agent-assignment`) or publish this folder as its own repository

## Agents (with your credentials)
- [ ] `.env` filled in (API key or Vertex AI); preflight "model credentials" shows PASS
- [ ] **A**: walkthrough prompt run; report shows patterns, ranked tiers, FACT/INFERENCE evidence with links
- [ ] **B**: `gemini --version` works and the CLI is authenticated; an analysis returns `execution: real_gemini_cli` with verified paths
- [ ] **B**: `make integration` passes (real Gemini CLI + GitHub)
- [x] **C**: actual MCP shown: the agent uses `McpToolset` over stdio, with contract tests and the smoke script
- [ ] **C**: triage prompt run in ADK Web; a write shows the approval dialog
- [x] **D**: detects every planted defect in the vulnerable and buggy fixtures (tests); clean fixture has zero findings
- [ ] **D**: review and `Fix it` loop run in ADK Web
- [x] **E**: local workflow works end to end through ADK's Runner (scripted model): quote, approval, order, isolation
- [ ] **E**: purchase flow run in ADK Web with a real model, approval dialog shown
- [x] **E**: production MCP Toolbox + PostgreSQL/AlloyDB configuration exists and is statically validated
- [ ] **E/C**: `make toolbox-up` and the production verification steps executed
- [ ] `make eval` run; results recorded below

## Repository hygiene
- [x] No secrets committed (pattern scan clean; `.env` ignored; `.env.example` placeholders only)
- [x] No generated junk (`__pycache__`, `.pytest_cache`, `.ruff_cache`, `.local_state`, `*.egg-info` and `.venv` are git-ignored; `.DS_Store` removed)
- [x] Internal Markdown links resolve (checked by script)
- [x] All 18 Mermaid diagrams parse with the Mermaid parser
- [x] References complete ([REFERENCES.md](REFERENCES.md)); originality documented ([ORIGINALITY.md](ORIGINALITY.md))
- [x] Local vs production claims are accurate (SQLite ≠ AlloyDB; fake CLI only in tests; nothing deployed)
- [x] No video, script or recording files exist (enforced by `tests/test_repository.py`)
- [ ] `LICENSE` copyright name is correct (currently "Dev Mulchandani")
- [x] README Quick start points at `https://github.com/DMgaming00/CMPE-297` (`cd CMPE-297/adk-agent-assignment`)

## Results log (fill in)
| Check | Date | Result |
|---|---|---|
| Agent A live run | | |
| Agent B live run / `make integration` | | |
| Agent C live run | | |
| Agent D live run + fix loop | | |
| Agent E live run (purchase + approval) | | |
| `make eval` (per agent) | | |
| Toolbox + PostgreSQL verification | | |
| CI run URL | | |
