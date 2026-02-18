#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/workspace/backend/.venv/bin/python"

"$PY" -m pip install openmim mmengine
"$PY" -m pip install "mmcv>=2.0.1" --no-build-isolation -f https://download.openmmlab.com/mmcv/dist/cu121/torch2.4/index.html
