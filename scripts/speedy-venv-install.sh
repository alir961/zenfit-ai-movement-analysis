#!/usr/bin/env bash
# Install the speedy lab dependencies (CUDA 12.1 torch wheels), retrying flaky downloads.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/speedy_learning/.venv/bin/python"

for attempt in 1 2 3; do
  echo "[speedy] pip install attempt $attempt/3"
  if "$PY" -m pip install --extra-index-url https://download.pytorch.org/whl/cu121 \
      -r "$ROOT/speedy_learning/backend/requirements.txt"; then
    exit 0
  fi
  [[ $attempt -lt 3 ]] && { echo "[speedy] pip install failed, retry in 5s..." >&2; sleep 5; }
done
echo "speedy-venv-install failed after 3 attempts" >&2
exit 1
