# Developer commands. Run `make setup` once, then `make check`.
PY ?= .venv/bin/python
ADK ?= .venv/bin/adk

.PHONY: setup install preflight seed lint test check compile mcp-smoke web api eval \
        integration toolbox-up toolbox-down docker-build clean

setup:            ## create .venv, install, seed demo data, run preflight
	./scripts/setup.sh

install:
	$(PY) -m pip install -e ".[dev]"

preflight:
	$(PY) scripts/preflight.py

seed:             ## reset local SQLite demo stores
	$(PY) scripts/seed_demo_data.py

lint:
	$(PY) -m ruff check .

compile:
	$(PY) -m compileall -q agents adk_shared scripts tests

test:
	$(PY) -m pytest -q

check: compile lint test   ## everything CI runs

mcp-smoke:        ## talk to both local MCP servers over stdio (no credentials)
	$(PY) scripts/mcp_smoke.py

web:              ## ADK dev UI with all five agents (needs Gemini credentials)
	$(ADK) web agents

api:
	$(ADK) api_server agents

eval:             ## ADK evaluation (needs Gemini credentials and `pip install -e ".[eval]"`)
	$(ADK) eval agents/ecommerce agents/ecommerce/eval/ecommerce.evalset.json \
	  --config_file_path agents/ecommerce/eval/test_config.json --print_detailed_results
	$(ADK) eval agents/bug_assistant agents/bug_assistant/eval/bug_assistant.evalset.json \
	  --config_file_path agents/bug_assistant/eval/test_config.json --print_detailed_results
	$(ADK) eval agents/code_review agents/code_review/eval/code_review.evalset.json \
	  --config_file_path agents/code_review/eval/test_config.json --print_detailed_results

integration:      ## real Gemini CLI + GitHub (needs gemini auth + network)
	RUN_GEMINI_CLI_INTEGRATION=1 $(PY) -m pytest -q -m integration

toolbox-up:       ## PostgreSQL + MCP Toolbox containers (production-like path)
	docker compose up -d

toolbox-down:
	docker compose down -v

docker-build:
	docker build -t adk-production-agents .

clean:
	rm -rf .pytest_cache .ruff_cache .local_state
	find . -name __pycache__ -not -path "./.venv/*" -prune -exec rm -rf {} +
