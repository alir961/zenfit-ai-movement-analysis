# Backend (RTMW3D Socket.IO)

## Run

Use Python 3.10–3.12: torch 2.4.1 and the OpenMMLab packages have no wheels for newer versions.

```
just setup-venv     # creates workspace/backend/.venv with the CUDA torch + OpenMMLab stack
just dev-backend    # python -m app.main on port 8001
```

## Test

```
cd workspace/backend
.venv/bin/python -m pytest tests
```

## Config
- `ZENFIT_MODEL_SIZE` = l | m | x (default: l)
- `ZENFIT_DEVICE` = auto | cpu | cuda
- `ZENFIT_DETECTOR` = rtmdet | yolox_tiny | yolox_s | mediapipe | mmdeploy (default: rtmdet)
- `ZENFIT_DET_CONFIG` = optional detector config path override
- `ZENFIT_DET_CHECKPOINT` = optional detector weights path override
- `ZENFIT_DET_SCORE_THR` = detection score threshold (default: 0.5)
- `ZENFIT_DET_INPUT_SIZE` = optional detector input size (e.g. "416,416")
- `ZENFIT_DETECTOR_BACKEND` = auto | mmdet | onnx (default: auto)
- `ZENFIT_DETECTOR_MODEL` = yolox_tiny_humanart | yolox_s_humanart | rtmdet_nano | rtmdet_tiny | person_foot_qualcomm
- `ZENFIT_DETECTOR_VARIANT` = fp32 | fp16 | int8
- `ZENFIT_POSE_VARIANT` = fp32 | fp16 | int8
- `ZENFIT_ORT_PROVIDERS` = provider priority list (default: CUDAExecutionProvider,CPUExecutionProvider)
- `ZENFIT_ONNX_ARTIFACTS_DIR` = ONNX artifact directory (default: workspace/backend/models/onnx)
- `ZENFIT_DETECTOR_MODEL_PATH` = optional explicit ONNX path for detector override
- The frontend connects to `NEXT_PUBLIC_POSE_SERVER_URL` (default `http://localhost:8001`); serve it from another origin? add that origin to `ZENFIT_CORS_ORIGINS`.
- `ZENFIT_CORS_ORIGINS` = comma-separated allowed origins for Socket.IO, or `*` (default: http://localhost:3000,http://127.0.0.1:3000)

## Notes
- RTMW3D requires MMPose + Torch.
- Install CUDA-enabled Torch if you want GPU.
- Default port is 8001.
- YOLOX humanart weights are supported from project root:
  - `yolox_tiny_8xb8-300e_humanart-6f3252f9.pth`
  - `yolox_s_8xb8-300e_humanart-3ef259a7.pth`
- MediaPipe and MMDeploy are optional; if not installed, their detector modes will fail with a clear error.
- Prepare ONNX artifacts and report:
  - `python workspace/backend/scripts/prepare_onnx_artifacts.py`
- Force rebuild detector FP16 artifacts only:
  - `python workspace/backend/scripts/prepare_onnx_artifacts.py --force-rebuild-fp16-detectors`
- MMDeploy starter docs:
  - `workspace/backend/docs/mmdeploy_starter.md`
- Benchmark units:
  - `det_ms`, `pose_ms`, `total_ms`, and `latency_ms` are in milliseconds.
