# ZenFit — Real-Time 3D Pose Estimation for Exercise Analysis

ZenFit estimates a person's **3D body pose in real time from a regular camera** and uses it to analyse exercises. A web viewer mirrors the motion on a rigged 3D avatar.

The repository holds two pipelines built on the same detection + pose models, plus the training code for a learned movement classifier:

| Part | What it does |
|---|---|
| `workspace/` | Main app. Python Socket.IO backend runs RTMW3D on camera frames and classifies **squats, push-ups and jumping jacks with joint-angle rules** (rep phases, metrics). Next.js + React Three Fiber client drives a rigged GLB avatar and lets the user pick the exercise |
| `speedy_learning/` | Standalone lab. FastAPI server with a WebSocket camera stream, YOLOX person detection + RTMW3D 3D pose on ONNX Runtime, COCO-17 skeleton mapping and post-processing, and a plain Three.js viewer with live overlays |
| `speedy_learning/models`, `train_cuda_live.py` | Learned movement classifier, trained offline: a spatio-temporal Transformer whose attention is biased by the skeleton graph. It is **not yet wired into either live pipeline** |
| `labs/` | Signal-processing experiments for pose stability: One-Euro and Kalman filters, bone-length constraints, scale solving, kinematics, with unit tests |

## Pipeline

```
camera ──► person detection ──► 3D pose estimation ──► 17-joint skeleton
           (YOLOX, ONNX Runtime)  (RTMW3D, ONNX Runtime,        │
                                   CUDA or CPU)                 │
                 ┌──────────────────────────────────────────────┤
                 ▼                                              ▼
   workspace: rule-based exercise          speedy_learning: post-processed
   classifier + metrics ─► Socket.IO ─►    skeleton ─► WebSocket ─► Three.js
   Next.js / R3F avatar                    viewer with overlays

   offline: videos ─► pose sequences (.npz) ─► graph-biased ST-Transformer
```

## Highlights

- **Real-time inference** with ONNX Runtime (CUDA provider with CPU fallback), fp32 and fp16 RTMW3D models, and benchmark results for model and runtime variants (`workspace/backend/benchmarks`)
- **Exercise analysis**: One-Euro smoothed joints feed per-exercise rep counters (squat, push-up, jumping jack) with hysteresis and confidence gating
- **Learned classifier**: dataset parser (video → pose sequences → train/val `.npz`, labels taken from file names) and GPU training with AMP, label smoothing, warm-up + cosine LR schedule and best-checkpoint saving
- **3D avatar**: Next.js, React Three Fiber and a rigged GLB model driven by the predicted joints

## Getting started

Requirements: Python 3.10–3.12 (torch 2.4.1 and OpenMMLab have no wheels for newer versions), [Bun](https://bun.sh) for the Next.js client, optional NVIDIA GPU with CUDA, and [`just`](https://github.com/casey/just). The scripts were written for Windows / PowerShell first; `.sh` equivalents are provided for Linux and macOS.

**Main app** (`workspace/`):

```bash
just setup-venv          # backend virtual environment (torch, OpenMMLab, ONNX Runtime)
just fetch-models        # MMPose sources in third_party/ and the RTMW3D-L checkpoint (~400 MB)
just dev-backend         # Socket.IO backend on http://localhost:8001
just dev-frontend        # Next.js client
```

**Speedy lab** (`speedy_learning/`):

```bash
just speedy-install      # venv, dependencies, MMPose third-party, ONNX models
just speedy-dev          # FastAPI server and viewer on http://127.0.0.1:8000
```

**Tests** (also run by GitHub Actions on every push and pull request):

```bash
just test                                   # frontend typecheck + tests, backend pytest
python -m pytest labs/tests                 # filtering / kinematics experiments
```

**Train the movement classifier** on your own videos (`*.mp4` in `datasets/`, named after their label, e.g. `squat_01.mp4`):

```bash
python speedy_learning/parser_dataset_pytorch.py --datasets-dir datasets --output-dir datasets \
  --stride 1 --sequence-len 120 --sequence-step 30 --val-ratio 0.2
python speedy_learning/train_cuda_live.py --epochs 10 --batch-size 4
```

> Training videos, trained weights and ONNX model files aren't included in this repository because of their size. `just speedy-install` regenerates the required detection and pose ONNX models from MMPose.

## Repository layout

```
workspace/backend    Socket.IO server, RTMW3D runtime, rule-based classifier, benchmarks
workspace/frontend   Next.js + React Three Fiber client
speedy_learning/     FastAPI lab: detection + pose pipeline, viewer, dataset parser, training
labs/                Filtering and kinematics experiments with tests
scripts/             Setup, dev and ONNX preparation scripts (.ps1 and .sh)
docs/                Architecture, socket events and debug metrics notes
```

## Tech stack

Python · PyTorch · ONNX Runtime · MMPose (RTMW3D) · YOLOX · OpenCV · NumPy · FastAPI · Socket.IO · Next.js · React Three Fiber · Three.js
