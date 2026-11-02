.PHONY: install test test-unit test-torch lint demo smoke small robust tiny mac report clean

install:
	pip install -e ".[all]"

test: test-unit test-torch

test-unit:
	pytest tests/unit -q

test-torch:
	pytest tests/torch -q

lint:
	ruff check src tests

demo:
	ltdmini synthetic-demo --out results/synthetic-demo --train-steps 20000

smoke:
	ltdmini all --config configs/smoke.yaml

small:   # main run: gpt2-medium / distilgpt2 (fits 8 GB laptops)
	ltdmini all --config configs/small.yaml --n-prompts 8

robust:  # PPO seeds + ablations + policy behaviour (CPU, resumable), then rebuild the report
	ltdmini robust --config configs/small.yaml --seeds 3
	ltdmini behaviour --config configs/small.yaml
	ltdmini report --config configs/small.yaml

tiny:
	ltdmini all --config configs/tiny.yaml

mac:
	ltdmini all --config configs/mac.yaml

clean:
	rm -rf results/smoke results/synthetic-demo .pytest_cache **/__pycache__
