# Labs V3

## Run

Runs with the main app's backend environment (`just setup-venv`, then `just fetch-models`), from the repository root, with a webcam. Windows and Linux.

```powershell
.\workspace\backend\.venv\Scripts\python.exe labs.py --preset yolox_s_fp32_fp32_cuda_skip3
```

```bash
# Linux: same commands with the venv's bin/python
workspace/backend/.venv/bin/python labs.py --preset yolox_s_fp32_fp32_cuda_skip3
```

The examples below use the Windows path; on Linux replace `.\workspace\backend\.venv\Scripts\python.exe` with `workspace/backend/.venv/bin/python`.

Tests: `workspace/backend/.venv/bin/python -m pytest labs/tests`.

## Key Flags

- `--preset yolox_s_fp32_fp32_cuda_skip3`
- `--preset rtmdet_m_fp32_fp32_cuda_skip3` (auto: ONNX if available, fallback MMDet)
- `--skip-mode fixed|adaptive`
- `--skip-fixed 3`
- `--rig-profile body17|coco133` (default `coco133`)
- `--plot-space raw|canonical|both` (default `canonical`)
- `--draw-min-conf 0.18`
- `--stale-policy strict|graceful` (default `graceful`)
- `--max-stale-frames 45`
- `--canonical-lock on|off` (default `on`)
- `--camera-links body17|coco133` (default `body17`)
- `--noncore-mode hold|predict|drop` (default `hold`)
- `--pyplot-rig body17|coco133` (default `body17`)
- `--show-noncore-points on|off` (default `on`)
- `--runtime-size 640,480` (default)
- `--loop` (replay video continuously with monotonic timeline)
- `--mandatory` (camera + detector/pose + skip only, no fusion/math/pyplot)
- `--pyplot on|off`
- `--ipc shm_queue`
- `--scale-mode calibrated|uncalibrated`
- `--calib-file <json>`
- `--benchmark-labs`

Calibration file format:

```json
{
  "cm_per_unit": 92.3
}
```

## Benchmark

```powershell
.\workspace\backend\.venv\Scripts\python.exe labs.py --benchmark-labs --pyplot off

# Optional: run full speed (no GUI) with explicit runtime size
.\workspace\backend\.venv\Scripts\python.exe labs.py --pyplot off --show-ui off --runtime-size 640,480

# Optional: strict minimal pipeline debug mode
.\workspace\backend\.venv\Scripts\python.exe labs.py --mandatory --show-ui on

# Compare detector preset in mandatory mode
.\workspace\backend\.venv\Scripts\python.exe labs.py --mandatory --preset rtmdet_m_fp32_fp32_cuda_skip3 --show-ui on

# Full rig + canonical 3D
.\workspace\backend\.venv\Scripts\python.exe labs.py --pyplot on --rig-profile coco133 --plot-space canonical

# V3.1 stable readable mode (recommended)
.\workspace\backend\.venv\Scripts\python.exe labs.py --pyplot on --camera-links body17 --noncore-mode hold --pyplot-rig body17

# Loop mode with camera + pyplot
.\workspace\backend\.venv\Scripts\python.exe labs.py --loop --pyplot on --show-ui on
```

Outputs:

- `workspace/backend/benchmarks/labs_runtime_latest.csv`
- `workspace/backend/benchmarks/labs_runtime_latest.json`

## Notes

- The default preset keeps `yolox_s_humanart/fp32/fp32/cuda_cpu/skip=3`.
- If detector bbox is degenerate, labs auto-falls back to `person_foot_detection.onnx` for robust bbox recovery.
- `normalized_joints` is explicit canonical pelvis-frame output for ML features.
