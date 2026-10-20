# Speedy Learning Lab

Standalone local lab for:
- 3D viewer and skeleton debug (`speedy_learning/viewer.html`)
- YOLOX + RTMW3D ONNX inference (`speedy_learning/backend`)
- webcam stream + live overlays

This file documents exactly what to do after a fresh `git clone`.

## Scope
- Uses a dedicated virtual environment: `speedy_learning/.venv`
- Uses `just` as the main command runner
- Can run with CUDA or CPU fallback

## Prerequisites
- Windows + PowerShell, or Linux with bash (the recipes pick the `.ps1` or `.sh` scripts)
- Python 3.10–3.12 (torch 2.4.1 has no wheels for newer versions; set `PYTHON=/path/to/python3.12` if it is not on PATH)
- `just` installed and available in PATH
- Optional NVIDIA GPU with CUDA runtime

## Full setup after clone

Run from repository root:

```powershell
just speedy-install
just speedy-dev
```

Equivalent detailed sequence:

```powershell
just speedy-venv-create
just speedy-venv-install
just speedy-third-party-ensure
just speedy-onnx-prepare
just speedy-ort-fix
just speedy-dev
```

What each step does:

1. `speedy-venv-create`
- Creates `speedy_learning/.venv`
- Upgrades pip/setuptools/wheel inside that venv

2. `speedy-venv-install`
- Installs all locked dependencies from:
  - `speedy_learning/backend/requirements.txt`

3. `speedy-third-party-ensure`
- Clones/updates `third_party/mmpose` automatically on `main`
- Validates required mmpose folders are present

4. `speedy-onnx-prepare`
- Ensures required ONNX files exist in:
  - `speedy_learning/models/yolox_s_humanart_fp32.onnx`
  - `speedy_learning/models/rtmw3d_l_fp32.onnx`
- If missing, generates them automatically from mmpose configs/checkpoints
- Validates both models with ONNX Runtime (CPU session)

5. `speedy-ort-fix`
- Installs/checks CUDA-related Python runtime packages
- Adds DLL search dirs for current process
- Prints interpreter path and providers
- Enables CPU fallback (`ZENFIT_ORT_CPU_ONLY=1`) if CUDA DLL chain is not usable

6. `speedy-dev`
- Starts FastAPI + static frontend
- Uses the same `speedy_learning/.venv`
- Typical URL: `http://127.0.0.1:8000`

## Quick validation checklist

1. Verify venv and providers:
```powershell
just speedy-venv-doctor
```

Expected:
- `sys.executable` points to `speedy_learning/.venv/Scripts/python.exe`
- ONNX providers include at least `CPUExecutionProvider`

2. Verify ONNX paths resolved by Speedy:
```powershell
speedy_learning/.venv/Scripts/python.exe -c "from speedy_learning.backend.inference_yolox import YOLOXDetector; from speedy_learning.backend.inference_rtmw3d import RTMW3DEstimator; d=YOLOXDetector(); p=RTMW3DEstimator(); print(d.model_path); print(p.model_path)"
```

Expected paths:
- `speedy_learning/models/yolox_s_humanart_fp32.onnx`
- `speedy_learning/models/rtmw3d_l_fp32.onnx`

3. Verify server health:
- Open `http://127.0.0.1:8000/health`
- Check:
  - `"ok": true`
  - provider list
  - detector and pose model paths

## Main just commands
- `just speedy-venv-create`
- `just speedy-venv-install`
- `just speedy-third-party-ensure`
- `just speedy-venv-doctor`
- `just speedy-venv-freeze`
- `just speedy-onnx-prepare`
- `just speedy-ort-fix`
- `just speedy-install`
- `just speedy-dev`
- `just speedy-test`

## Runtime environment variables
- `ZENFIT_LOG_LEVEL` (default `INFO`)
- `ZENFIT_DEBUG_STAGES` (default `0`)
- `ZENFIT_VERBOSE_CAMERA` (default `0`)
- `ZENFIT_ORT_CPU_ONLY` (set automatically by bootstrap if needed)

Example debug run:
```powershell
$env:ZENFIT_LOG_LEVEL="DEBUG"
$env:ZENFIT_DEBUG_STAGES="1"
$env:ZENFIT_VERBOSE_CAMERA="1"
just speedy-dev
```

## CUDA troubleshooting

If you see `cudnn64_9.dll` or CUDA provider errors:

1. Run:
```powershell
just speedy-ort-fix
```

2. Confirm printed Python path is `speedy_learning/.venv`

3. Check provider output again:
```powershell
just speedy-venv-doctor
```

4. If CUDA still fails, CPU fallback is expected and runtime should still work.

## Lockfile and dependency maintenance
- Official lockfile:
  - `speedy_learning/backend/requirements.txt`

After dependency updates, regenerate lock:
```powershell
just speedy-venv-freeze
```

## Training notes
Training scripts are available, but not required to run the viewer/inference lab.

Data prep example:
```powershell
python speedy_learning/parser_dataset_pytorch.py --datasets-dir datasets --output-dir datasets --stride 1 --sequence-len 120 --sequence-step 30 --val-ratio 0.2
```

Training example:
```powershell
python speedy_learning/train_cuda_live.py
```

Best checkpoint expected path:
- `datasets/training_outputs/best_model.pt`
