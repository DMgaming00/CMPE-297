#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pytest
python -m src.cli compare --ablations
python -m src.cli ablate --config reduced_budget
