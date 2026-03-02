#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .[dev]
cp -n .env.example .env || true
mkdir -p data/admin data/timeseries

echo "Bootstrap completed."
echo "Run API: make run-api"
echo "Run frontend: make run-frontend"
