# MMDeploy Starter

## Goal
Quickly compare the current native ONNX runtime against MMDeploy conversion/profiling.

## Prerequisites
- `mmdeploy` cloned under `third_party/mmdeploy`
- CUDA/TensorRT correctly installed
- Python env with `mmdeploy` dependencies

## Convert
```powershell
.\workspace\backend\scripts\mmdeploy_starter.ps1
```

## Profile
```powershell
.\workspace\backend\scripts\mmdeploy_profile.ps1
```

## Notes
- This is a starter workflow. It does not replace the native runtime path.
- Compare profiler outputs with `workspace/backend/benchmarks/latest_full_onnx.csv`.
