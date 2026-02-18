#!/usr/bin/env bash
set -euo pipefail

PYTHON_EXE="${PYTHON_EXE:-speedy_learning/.venv/bin/python}"
if [[ "${1:-}" == --python=* ]]; then
  PYTHON_EXE="${1#*=}"
fi

if [[ ! -x "$PYTHON_EXE" ]]; then
  echo "Python introuvable: $PYTHON_EXE" >&2
  exit 1
fi

SPEEDY_MODELS_DIR="speedy_learning/models"
BACKEND_ONNX_DIR="workspace/backend/models/onnx"
mkdir -p "$SPEEDY_MODELS_DIR"

ensure_model() {
  local name="$1"
  local target="$SPEEDY_MODELS_DIR/$name"
  local backend_src="$BACKEND_ONNX_DIR/$name"
  if [[ -f "$target" ]]; then
    echo "[speedy-onnx] OK (already): $target"
    return
  fi
  if [[ -f "$backend_src" ]]; then
    cp -f "$backend_src" "$target"
    echo "[speedy-onnx] Copied: $backend_src -> $target"
    return
  fi
  echo "[speedy-onnx] Missing $name in backend cache. Trying artifact preparation..."
  "$PYTHON_EXE" workspace/backend/scripts/prepare_onnx_artifacts.py --out-dir workspace/backend/models/onnx
  if [[ -f "$backend_src" ]]; then
    cp -f "$backend_src" "$target"
    echo "[speedy-onnx] Copied after prepare: $backend_src -> $target"
    return
  fi
  echo "Impossible de trouver/generer $name." >&2
  exit 1
}

ensure_model "yolox_s_humanart_fp32.onnx"
ensure_model "rtmw3d_l_fp32.onnx"

SPEEDY_ONNX_PATHS='["'"$SPEEDY_MODELS_DIR"'/yolox_s_humanart_fp32.onnx","'"$SPEEDY_MODELS_DIR"'/rtmw3d_l_fp32.onnx"]'
export SPEEDY_ONNX_PATHS
"$PYTHON_EXE" - <<'PY'
import json
import os
import pathlib
import onnxruntime as ort

paths = json.loads(os.environ["SPEEDY_ONNX_PATHS"])
for p in paths:
    pp = pathlib.Path(p)
    if not pp.exists():
        raise RuntimeError("missing model: " + str(pp))
    sess = ort.InferenceSession(str(pp), providers=["CPUExecutionProvider"])
    print("[speedy-onnx] validated {} inputs={} outputs={}".format(pp.name, len(sess.get_inputs()), len(sess.get_outputs())))
PY

echo "[speedy-onnx] Ready. Required ONNX models are present in $SPEEDY_MODELS_DIR"
