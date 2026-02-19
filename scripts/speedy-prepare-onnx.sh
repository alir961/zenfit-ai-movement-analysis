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

echo "[speedy-onnx] Ensuring third_party/mmpose..."
./scripts/speedy-third-party-ensure.sh

echo "[speedy-onnx] Generating required ONNX models..."
"$PYTHON_EXE" scripts/speedy-generate-required-onnx.py

SPEEDY_ONNX_PATHS='["speedy_learning/models/yolox_s_humanart_fp32.onnx","speedy_learning/models/rtmw3d_l_fp32.onnx"]'
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

echo "[speedy-onnx] Ready. Required ONNX models are present in speedy_learning/models"