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

## Getting started

Requirements: Python 3.10–3.12 (torch 2.4.1 and OpenMMLab have no wheels for newer versions), [Bun](https://bun.sh) for the Next.js client, optional NVIDIA GPU with CUDA, and [`just`](https://github.com/casey/just). The scripts were written for Windows / PowerShell first; `.sh` equivalents are provided for Linux (macOS is not supported: the CUDA builds of torch and ONNX Runtime have no macOS wheels).

**Main app** (`workspace/`):

```bash
just setup-venv          # backend virtual environment (torch, OpenMMLab, ONNX Runtime)
just fetch-models        # MMPose sources in third_party/ and the RTMW3D-L checkpoint (~220 MB)
just dev-backend         # Socket.IO backend on http://localhost:8001, reloads on app/ changes
just dev-frontend        # Next.js client on http://localhost:3000
```

Open http://localhost:3000, wait for "Backend connected", pick an exercise and press **Start session**. `/admin_debug` shows the raw and normalized skeletons and the backend errors.

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
workspace/frontend   Next.js client: live coach page, debug page, avatar components
speedy_learning/     FastAPI lab: detection + pose pipeline, viewer, dataset parser, training
labs/                Filtering and kinematics experiments with tests
scripts/             Setup, dev and ONNX preparation scripts (.ps1 and .sh)
docs/                Architecture, socket events and debug metrics notes
```

## Tech stack

Python · PyTorch · ONNX Runtime · MMPose (RTMW3D) · YOLOX · OpenCV · NumPy · FastAPI · Socket.IO · Next.js · React Three Fiber · Three.js
