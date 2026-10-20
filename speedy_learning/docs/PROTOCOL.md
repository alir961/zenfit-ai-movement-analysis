# Speedy Learning Labs Protocol

## Dev Run
1. `cd speedy_learning`
2. `python -m venv .venv`
3. `.venv\\Scripts\\activate`
4. `pip install -r backend/requirements.txt`
5. `python run_dev.py`
6. Open the URL printed by `run_dev.py`.

## Model Paths
- YOLOX expected at:
  - `speedy_learning/models/yolox_s_humanart_fp32.onnx` (preferred), or
  - `yolox_s_humanart_fp32.onnx` (repo root).
- RTMW3D expected at:
  - `speedy_learning/models/rtmw3d_l_fp32.onnx` (preferred), or
  - `rtmw3d_l.onnx` (repo root).

## Endpoint
- `POST /process`
- `multipart/form-data`:
  - `image`: JPEG
  - `timestamp_ms`: optional int
  - `session_id`: optional string
  - `frame_id`: optional int

## Response Contract
- `meta`
- `detector`
- `pose_raw17`
- `pose_mapped_humanoid`
- `pose_normalized`
- `postprocess`
- `gaussian`
- `debug`

All sections are always present.

## Persistence
- `runs/{session_id}/frames.jsonl`
- `runs/{session_id}/stats.json`
