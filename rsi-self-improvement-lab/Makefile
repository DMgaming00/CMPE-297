PY ?= python
.PHONY: setup test lint demo compare ablate visualize reproduce clean

setup:
	$(PY) -m venv .venv && .venv/bin/pip install -r requirements.txt

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check src tests codelabs

demo:
	$(PY) -m src.cli demo

compare:
	$(PY) -m src.cli compare --ablations

ablate:
	$(PY) -m src.cli ablate --config reduced_budget

visualize:
	$(PY) -m src.cli visualize

reproduce: test compare ablate

clean:
	rm -rf .pytest_cache .ruff_cache experiments/results/smoke artifacts/figures/smoke
