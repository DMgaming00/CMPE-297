#!/usr/bin/env bash
# One-shot local setup: virtualenv, dependencies, .env, demo data, preflight.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
if [ ! -d .venv ]; then
  "$PYTHON" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
python -m pip install -e ".[dev]"
[ -f .env ] || cp .env.example .env
python scripts/seed_demo_data.py
python scripts/preflight.py || true
echo
echo "Setup complete. Activate with: source .venv/bin/activate"
