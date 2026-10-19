#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$ROOT/workspace/backend/.venv"
PY="$VENV_DIR/bin/python"

# torch 2.4.1 and the OpenMMLab wheels only exist for Python 3.10-3.12.
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

echo "--- [1/6] Initialisation du venv dans $VENV_DIR ---"
if [[ ! -d "$VENV_DIR" ]]; then
  if ! BASE_PY="$(find_python)"; then
    echo "Python 3.10-3.12 introuvable. Installez-en un (ex: pyenv, uv) ou passez PYTHON=/chemin/python3.12." >&2
    exit 1
  fi
  "$BASE_PY" -m venv "$VENV_DIR"
fi

echo "--- [2/6] Mise a jour des outils de packaging (pin setuptools 69.5.1) ---"
"$PY" -m pip install --upgrade pip wheel "setuptools==69.5.1" packaging

echo "--- [3/6] Verification/Installation de la stack Torch/CUDA ---"
"$PY" -m pip install torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cu121
"$PY" -c "import torch; print(f'Torch {torch.__version__} valide (CUDA: {torch.version.cuda})')"

echo "--- [4/6] Installation de OpenMMLab (MIM, MMEngine, MMCV) ---"
"$PY" -m pip install openmim mmengine
"$PY" -m pip install "mmcv>=2.0.1" --no-build-isolation -f https://download.openmmlab.com/mmcv/dist/cu121/torch2.4/index.html

echo "--- [5/6] Installation des requirements projet ---"
if [[ -f "$ROOT/workspace/backend/requirements.txt" ]]; then
  "$PY" -m pip install -r "$ROOT/workspace/backend/requirements.txt"
fi

echo "--- [6/6] Verifications finales ---"
"$ROOT/scripts/doctor-venv.sh"
