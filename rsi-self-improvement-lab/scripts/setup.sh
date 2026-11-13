#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m venv .venv
.venv/bin/pip install -r requirements.txt
echo "now: source .venv/bin/activate && python -m src.cli demo"
