#!/usr/bin/env bash
set -euo pipefail

PYTHON_EXE="${PYTHON_EXE:-speedy_learning/.venv/bin/python}"
INSTALL_DEPS="${INSTALL_DEPS:-0}"
DOCTOR_ONLY="${DOCTOR_ONLY:-0}"
RUN_SCRIPT="${RUN_SCRIPT:-speedy_learning/run_dev.py}"

for arg in "$@"; do
  case "$arg" in
    --install-deps) INSTALL_DEPS=1 ;;
    --doctor-only) DOCTOR_ONLY=1 ;;
    --python=*) PYTHON_EXE="${arg#*=}" ;;
    --run-script=*) RUN_SCRIPT="${arg#*=}" ;;
  esac
done

if [[ ! -x "$PYTHON_EXE" ]]; then
  echo "Python introuvable: $PYTHON_EXE" >&2
  exit 1
fi

echo "[speedy] Python executable (venv attendu):"
"$PYTHON_EXE" -c "import sys; print(sys.executable); print('prefix=', sys.prefix)"

if [[ "$INSTALL_DEPS" == "1" ]]; then
  echo "[speedy] Installation dependances CUDA/cuDNN Python..."
  "$PYTHON_EXE" -m pip install --upgrade "onnxruntime-gpu[cuda,cudnn]==1.22.0"
  "$PYTHON_EXE" -m pip install --upgrade nvidia-cuda-runtime-cu12 nvidia-cublas-cu12 nvidia-cudnn-cu12
fi

mapfile -t _dll_dirs < <("$PYTHON_EXE" - <<'PY'
import pathlib, site
roots = []
try: roots += site.getsitepackages()
except Exception: pass
try: roots.append(site.getusersitepackages())
except Exception: pass
out=[]
seen=set()
for root in roots:
    if not root: continue
    r=pathlib.Path(root)
    nvidia=r/"nvidia"
    if nvidia.exists():
        for d in nvidia.glob("*/lib"):
            if d.is_dir() and str(d) not in seen:
                seen.add(str(d)); out.append(str(d))
    for d in (r/"torch"/"lib", r/"onnxruntime"/"capi"):
        if d.is_dir() and str(d) not in seen:
            seen.add(str(d)); out.append(str(d))
for d in out: print(d)
PY
)

if [[ "${#_dll_dirs[@]}" -gt 0 ]]; then
  echo "[speedy] LD_LIBRARY_PATH ajoute:"
  for d in "${_dll_dirs[@]}"; do
    echo "  - $d"
  done
  _lib_path="$(IFS=:; echo "${_dll_dirs[*]}")"
  export LD_LIBRARY_PATH="$_lib_path${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

echo "[speedy] Diagnostic ONNXRuntime/CUDA..."
diag="$("$PYTHON_EXE" - <<'PY'
import ctypes, json
res={"providers": [], "dll_ok": False, "dll_error": None}
try:
    ctypes.CDLL("libcudnn.so.9")
    res["dll_ok"] = True
except Exception as e:
    res["dll_error"] = str(e)
try:
    import onnxruntime as ort
    res["providers"] = ort.get_available_providers()
except Exception as e:
    res["providers_error"] = str(e)
print(json.dumps(res))
PY
)"
echo "$diag"

if echo "$diag" | grep -q '"dll_ok": false'; then
  export ZENFIT_ORT_CPU_ONLY=1
  echo "[speedy] WARNING: libcudnn.so.9 non chargeable. CPU fallback actif (ZENFIT_ORT_CPU_ONLY=1)."
else
  export ZENFIT_ORT_CPU_ONLY=0
fi

if [[ "$DOCTOR_ONLY" == "1" ]]; then
  exit 0
fi

echo "[speedy] Launch: $PYTHON_EXE $RUN_SCRIPT"
exec "$PYTHON_EXE" "$RUN_SCRIPT"
