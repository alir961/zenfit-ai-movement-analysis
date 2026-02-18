#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/workspace/backend/.venv/bin/python"

echo "=== [ZenFit Backend Diagnostic] ==="
echo "Python:     $("$PY" --version)"
echo "Pip:        $("$PY" -m pip --version)"
echo "Setuptools: $("$PY" -c 'import setuptools; print(setuptools.__version__)')"
echo "--- Statut Torch / CUDA ---"
"$PY" -c "import torch; print(f'Torch: {torch.__version__} | CUDA: {torch.version.cuda} | GPU: {torch.cuda.is_available()}')"
echo "--- Statut OpenMMLab ---"
"$PY" -c "import mmcv, mmengine; print(f'MMCV: {mmcv.__version__} | MMEngine: {mmengine.__version__}')"
"$PY" -c "import importlib.util as u; print('MMPose: installed' if u.find_spec('mmpose') else 'MMPose: Non installe')"
echo "--- Integrite Pip ---"
"$PY" -m pip check
echo "===================================="
