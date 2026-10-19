#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/workspace/frontend"
bun run typecheck
bun run test

BACKEND_PY="$ROOT/workspace/backend/.venv/bin/python"
if [[ -x "$BACKEND_PY" ]]; then
  (cd "$ROOT/workspace/backend" && "$BACKEND_PY" -m pytest -q tests)
else
  echo "Backend venv missing, skipping backend tests (run: just setup-venv)"
fi
