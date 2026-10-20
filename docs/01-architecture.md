# 01-architecture.md

## Scope
- Two pages only: / (Live Coach) and /admin_debug (Debug)
- Five exercises: squat, push_up, jumping_jack (full body in frame) and bicep_curl, lateral_raise (one arm in frame is enough), picked in the UI and sent with each frame
- Backend required: Python + Socket.IO with RTMW3D-L inference

## Runtime Flow

```mermaid
flowchart LR
  Camera[Camera Frames] --> Frontend[Next.js Live Coach]
  Frontend --> SocketIn[Socket.IO pose/input]
  SocketIn --> Backend[Python RTMW3D Runtime]
  Backend --> Normalize[Normalize Pose]
  Normalize --> Metrics[Compute Metrics]
  Metrics --> Classify[Classify Exercise]
  Classify --> SocketOut[Socket.IO pose/normalized, pose/metrics, exercise/state]
  SocketOut --> FrontendUI[Live Coach + admin_debug]
```

## Session State

```mermaid
stateDiagram-v2
  [*] --> Paused
  Paused --> Running: Start session (backend connected; emits session/start)
  Running --> Paused: Stop session
```

## Key Modules
- frontend: `workspace/frontend`
- backend: `workspace/backend/app`
- docs: `docs/*.md`

## Pose Contract
- PoseFrame: { t, space, joints[] }
- joints[]: { name, x, y, z, c }
- space: camera | normalized

## Notes
- Only RTMW3D-L is the default model size.
- GPU is preferred, CPU fallback is allowed.
- The client retries the backend connection without limit. If the backend drops during a session, the session stays running and frames resume once the socket reconnects.
