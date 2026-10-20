#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/workspace/backend/.venv"
PY="$VENV/bin/python"

cd "$ROOT/workspace/backend"

if [[ ! -x "$PY" ]]; then
  echo "Virtual environment not found. Running setup-venv..."
  cd "$ROOT"
  just setup-venv
  cd "$ROOT/workspace/backend"
fi

echo "Starting Backend (RTMW3D) at http://localhost:8001 (auto-reload on app/ changes) ..."
ZENFIT_RELOAD="${ZENFIT_RELOAD:-1}" "$PY" -m app.main
