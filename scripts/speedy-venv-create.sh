#!/usr/bin/env bash
# Create speedy_learning/.venv with a Python supported by torch 2.4.1 (3.10-3.12).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$ROOT/speedy_learning/.venv"

find_python() {
  local candidate
  for candidate in "${PYTHON:-}" python3.12 python3.11 python3.10 python3; do
    [[ -n "$candidate" ]] && command -v "$candidate" >/dev/null 2>&1 || continue
    if "$candidate" -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)'; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

if [[ ! -d "$VENV_DIR" ]]; then
  if ! BASE_PY="$(find_python)"; then
    echo "Python 3.10-3.12 not found. Install one (pyenv, uv, ...) or pass PYTHON=/path/to/python3.12." >&2
    exit 1
  fi
  "$BASE_PY" -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install --upgrade pip wheel setuptools==69.5.1
