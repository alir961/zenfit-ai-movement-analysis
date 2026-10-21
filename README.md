# ZenFit — Real-Time 3D Pose Estimation for Exercise Analysis

ZenFit estimates a person's **3D body pose in real time from a regular camera** and uses it to count exercise repetitions. The web app draws the detected skeleton over the camera feed and shows the rep count, the movement phase and the tracking confidence live.

The repository holds two pipelines built on the same pose model, plus the training code for a learned movement classifier:

| Part | What it does |
|---|---|
| `workspace/` | Main app. A Python Socket.IO backend runs RTMDet person detection and RTMW3D 3D pose estimation on camera frames, then counts reps of **squats, push-ups, jumping jacks, bicep curls and lateral raises with joint-angle rules**. The Next.js client streams the camera, overlays the skeleton and shows the live stats; a `/admin_debug` page shows raw and normalized skeletons, metrics and errors |
| `speedy_learning/` | Standalone lab. FastAPI server with a WebSocket camera stream, YOLOX person detection + RTMW3D 3D pose on ONNX Runtime, COCO-17 skeleton mapping and post-processing, and a plain Three.js viewer with live overlays |
| `speedy_learning/models`, `train_cuda_live.py` | Learned movement classifier, trained offline: a spatio-temporal Transformer whose attention is biased by the skeleton graph. It is **not yet wired into either live pipeline** |
| `labs/` | Signal-processing experiments for pose stability: One-Euro and Kalman filters, bone-length constraints, scale solving, kinematics, with unit tests |

## Pipeline

```
workspace (main app)

browser camera ─► JPEG frames, 10 FPS, Socket.IO ─► RTMDet person box ─► RTMW3D 3D pose
                                                    (re-detected every   (ONNX Runtime CUDA/CPU,
                                                     few frames)          PyTorch fallback)
                                                                                │
browser: skeleton overlay, ◄── Socket.IO ◄── rep counter ◄── One-Euro ◄── hip-centred,
rep count, phase, confidence                  (joint-angle    smoothing    torso-scaled
                                               rules)                      normalization

speedy_learning (lab)

camera ─► WebSocket ─► YOLOX ─► RTMW3D (ONNX) ─► COCO-17 skeleton ─► Three.js viewer

offline

videos ─► pose sequences (.npz) ─► graph-biased ST-Transformer
```

## Exercises

Each exercise is a two-phase state machine on joint angles from the normalized pose. A phase only changes after it has been seen on 2 frames in a row, there is a dead zone between the two thresholds, and joints below 0.3 confidence are ignored, so jitter does not create extra reps.

| Exercise | Measured | Needs in frame |
|---|---|---|
| Squat | knee angle (down < 120°, up > 155°) | hips, knees, ankles |
| Push-up | elbow angle (down < 100°, up > 150°) while the torso is roughly horizontal | shoulders, elbows, wrists, hips |
| Jumping jack | wrists above shoulders and feet spread vs. shoulder width | wrists, shoulders, ankles |
| Bicep curl | elbow angle of the most bent arm (up < 60°, down > 140°) | one shoulder, elbow and wrist |
| Lateral raise | arm elevation from hanging (up > 70°, down < 30°) | one shoulder and wrist |

Bicep curls and lateral raises work when you stand close to the camera; the full-body exercises need you to step back until your legs are visible. The skeleton overlay draws joints the backend cannot use in red, which shows what is missing.

## Highlights

- **Real-time inference** with ONNX Runtime (CUDA provider with CPU fallback), fp32 and fp16 RTMW3D models, and benchmark results for model and runtime variants (`workspace/backend/benchmarks`)
- **Rep counting** from One-Euro smoothed joints, with hysteresis, frame confirmation and confidence gating; tested in `workspace/backend/tests`
- **Live coach UI**: Next.js client with the skeleton drawn over the mirrored camera feed, exercise picker with framing tips, rep counter, phase and tracking confidence, backend connection status
- **Learned classifier**: dataset parser (video → pose sequences → train/val `.npz`, labels taken from file names) and GPU training with AMP, label smoothing, warm-up + cosine LR schedule and best-checkpoint saving
- **3D avatar (work in progress)**: a rigged GLB model and bone bindings driven by the normalized joints (`workspace/frontend/src/components/avatar`); the debug page shows the model, but the pose-driven avatar is not displayed in the UI yet

## Supported platforms

| OS | Status |
|---|---|
| Windows 10/11 | Supported: the scripts were written for PowerShell first (`.ps1`), and `just` picks them automatically |
| Linux | Supported with the `.sh` scripts (tested on Arch with an NVIDIA GPU; CI runs the tests on Ubuntu) |
| macOS | Not supported: the CUDA builds of torch, mmcv and ONNX Runtime have no macOS wheels |

A GPU is optional: without CUDA the backend falls back to the CPU, which works but gives a low frame rate.

## Requirements

- **Python 3.10, 3.11 or 3.12**: torch 2.4.1 and the OpenMMLab packages have no wheels for newer versions. If your system Python is newer (Arch, Fedora, Ubuntu 25.04+), install 3.12 with [uv](https://docs.astral.sh/uv/) (`uv python install 3.12`) or pyenv, and pass it as `PYTHON=/path/to/python3.12`
- **[`just`](https://github.com/casey/just)** command runner (`cargo install just`, `winget install Casey.Just`, or your package manager)
- **[Bun](https://bun.sh) 1.3+** for the Next.js client
- **git** and **curl** (the scripts clone MMPose and download the checkpoint)
- A C/C++ compiler (`build-essential` on Debian/Ubuntu, Visual Studio Build Tools on Windows) for the `chumpy` and `xtcocotools` source packages
- Optional, for GPU inference: an NVIDIA GPU with a driver that supports **CUDA 12.1+** (torch is installed from the cu121 index and ONNX Runtime GPU 1.22 needs CUDA 12 with cuDNN 9)
- About 8 GB of disk space for the virtual environment, MMPose and the models, an internet connection for the first setup and the first backend start, and a webcam

## Getting started

```bash
git clone https://github.com/alir961/zenfit-ai-movement-analysis.git
cd zenfit-ai-movement-analysis
```

**Main app** (`workspace/`):

```bash
just setup-venv          # workspace/backend/.venv: torch (CUDA 12.1), OpenMMLab, ONNX Runtime; several GB, takes a while
just fetch-models        # MMPose (pinned commit) in third_party/ and the RTMW3D-L checkpoint (~220 MB, SHA-256 checked) at the repository root
(cd workspace/frontend && bun install)   # client dependencies, once
just dev-backend         # Socket.IO backend on http://localhost:8001, reloads on app/ changes
just dev-frontend        # Next.js client on http://localhost:3000 (second terminal)
```

The first backend start also downloads the RTMDet person-detector weights from OpenMMLab, then logs `RTMW3D runner initialized with size l on cuda` (or `cpu`). `just doctor-venv` checks the environment, and `ZENFIT_DEVICE=cpu just dev-backend` forces the CPU. The other backend settings (model size, detector, ONNX providers, CORS origins) are listed in [`workspace/backend/README.md`](workspace/backend/README.md).

Open http://localhost:3000 in Chrome, Edge or Firefox, allow the camera, wait for "Backend connected", pick an exercise and press **Start session**. `/admin_debug` shows the raw and normalized skeletons and the backend errors. If the backend runs on another machine, start the client with `NEXT_PUBLIC_POSE_SERVER_URL=http://<host>:8001` and add the client's origin to `ZENFIT_CORS_ORIGINS`.

**Speedy lab** (`speedy_learning/`):

```bash
just speedy-install      # venv, dependencies, MMPose third-party, ONNX models
just speedy-dev          # FastAPI server and viewer on http://127.0.0.1:8000
```

**Tests** (also run by GitHub Actions on every push and pull request):

```bash
just test                                   # frontend typecheck + tests, backend pytest (needs bun install and the backend venv)
workspace/backend/.venv/bin/python -m pytest labs/tests   # filtering / kinematics experiments (Windows: .venv\Scripts\python.exe)
just lint                                   # ESLint on the client
```

The tested modules only need NumPy, so any Python 3.10+ with `pip install pytest "numpy<2.0.0"` runs them as CI does: `cd workspace/backend && python -m pytest tests`, and `python -m pytest labs/tests` from the repository root.

**Train the movement classifier** on your own videos (`*.mp4` in `datasets/`, named after their label, e.g. `squat_01.mp4`), with the speedy lab's Python (`speedy_learning/.venv/bin/python`, created by `just speedy-install`) and an NVIDIA GPU:

```bash
python speedy_learning/parser_dataset_pytorch.py --datasets-dir datasets --output-dir datasets \
  --stride 1 --sequence-len 120 --sequence-step 30 --val-ratio 0.2
python speedy_learning/train_cuda_live.py --epochs 10 --batch-size 4
```

> Training videos, trained weights and ONNX model files aren't included in this repository because of their size. `just speedy-install` regenerates the required detection and pose ONNX models from MMPose.

## Repository layout

```
workspace/backend    Socket.IO server, RTMW3D runtime, rule-based classifier, benchmarks
workspace/frontend   Next.js client: live coach page, debug page, avatar components
speedy_learning/     FastAPI lab: detection + pose pipeline, viewer, dataset parser, training
labs/                Filtering and kinematics experiments with tests
scripts/             Setup, dev and ONNX preparation scripts (.ps1 and .sh)
docs/                Architecture, socket events and debug metrics notes
```

## Tech stack

Python · PyTorch · ONNX Runtime · MMPose (RTMW3D) · YOLOX · OpenCV · NumPy · FastAPI · Socket.IO · Next.js · React Three Fiber · Three.js

## License

[MIT](LICENSE)
