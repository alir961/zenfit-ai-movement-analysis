````md
# update_production_mvp.md

## Objective

Create a final MVP migration pass by consolidating all existing project information and implementing only the requested scope, with no extra features.

This plan is **strictly limited** to:
- Exercises: **squat + push-up + burpees**
- 2 pages only:
  1. **Live Coach Page**: avatar + camera + panda coach + live movement detection on classified movements
  2. **admin_debug Page**: skeleton detection debug, normalization checks, body-size metrics, rig-point distances, full dev stats/gizmos helpers
- Stack constraints exactly as defined
- If backend is required: **Socket.IO + Python**

Project constraints and stack source reference: :contentReference[oaicite:0]{index=0}

---

## Non-Negotiable Scope

- Do not add pages beyond the 2 requested pages.
- Do not add exercises beyond squat, push-up, burpees.
- Do not introduce unrequested product features.
- Do not change the requested stack.
- Consolidate and reuse existing logic/contracts before creating new modules.

---

## Required Stack

### Frontend
- Next.js 16
- React
- @react-three/fiber
- @react-three/drei
- Framer Motion
- Custom CSS + small Tailwind usage + PostCSS
- Premium clean UI style as defined

### Backend (only if needed)
- Python service
- Socket.IO real-time bridge between frontend and inference/processing pipeline

### Tooling
- `justfile`
- `./scripts/*.ps1`
- `./scripts/*.sh`

### Minimal root structure
- `./docs`
- `./workspace/frontend`
- `./scripts`
- `./.gitignore`
- `./justfile`

Stack and structure requirements source: :contentReference[oaicite:1]{index=1}

---

## UI / Design Constraints (must follow exactly)

Style:
- Clean Soft SaaS UI
- Bright airy monochrome base (white/light gray)
- High-contrast electric purple accents
- Friendly rounded geometry
- Pill-shaped buttons
- Floating UI with soft diffuse shadows, no hard borders

Palette:
- `--lavender: #e8e1efff;`
- `--majorelle-blue: #724cf9ff;`
- `--black: #020100ff;`
- `--jasmine: #ffee88ff;`
- `--mint-leaf: #00cc99ff;`

Style and palette source: :contentReference[oaicite:2]{index=2}

---

## Functional Deliverables

## 1) Live Coach Page

### Goal
Single production page for live coaching with synchronized visual and inference feedback.

### Must include
- Live camera stream
- Human avatar (R3F + Drei) rig-driven by detected pose
- Panda coach visible in page
- Live classification/detection feedback for:
  - Squat
  - Push-up
  - Burpees
- Clear session-state indicators (running / paused / no input)

### Required live pipeline behavior
- Camera frames -> pose estimation -> normalized skeleton representation -> classification for target exercises -> UI update in real time
- Avatar updates must follow processed pose signal
- If backend mode is enabled, real-time exchange via Socket.IO events

### Out of scope
- No extra exercise types
- No analytics dashboard beyond live necessities
- No user/account/payment layer

---

## 2) admin_debug Page

### Goal
Developer diagnostics page for validating detection quality, skeleton normalization, and geometric rig consistency.

### Must include
- Raw skeleton visualization
- Normalized skeleton visualization
- Side-by-side or switchable view
- Point-level metrics and distances
- Computed body-size criteria and rig-space stats
- Dev gizmos/helpers for:
  - Joint markers
  - Segment lines
  - Distance readouts
  - Normalization state indicators
  - Debug overlays for thresholds/states

### Required stats outputs (minimum)
- Per-joint visibility/confidence
- Key pair distances (all relevant rig points)
- Body width/height estimations from selected landmarks
- Normalization coefficients currently applied
- Classification intermediate values for squat/push-up/burpees

### Out of scope
- No end-user UI polish priority here
- No feature expansion outside debugging and validation

---

## Real-Time Architecture (Minimal, Requested Only)

## Mode A — Frontend-first
- Pose and classification run in frontend runtime
- Admin debug reads same internal stream for diagnostics

## Mode B — With backend (if required)
- Frontend captures frames / keypoints
- Python backend performs selected processing
- Socket.IO used for bidirectional events:
  - inbound: frame/keypoint payloads
  - outbound: normalized skeleton, metrics, classification states
- Frontend renders avatar + panda coach + debug page from event stream

No additional service layers unless strictly required.

---

## Socket.IO Event Contract (Minimal)

Define and freeze event names and payloads before coding UI logic.

### Client -> Server
- `pose/input`
  - timestamp
  - frame_id
  - points/raw skeleton data (or frame reference)
  - optional client-side metadata

### Server -> Client
- `pose/normalized`
  - normalized points
  - normalization parameters
- `pose/metrics`
  - distances
  - size/width criteria
  - confidence summary
- `exercise/state`
  - current class (squat | push_up | burpee | none)
  - phase/state
  - score/confidence
- `debug/state`
  - internal computation fields required by admin_debug

Keep payloads typed and versioned. Do not add unused fields.

---

## Proposed Repository Tree (Minimal + Implementable)

```text
.
├─ docs/
│  ├─ update_production_mvp.md
│  ├─ architecture.md
│  ├─ socket_events.md
│  └─ debug_metrics.md
├─ workspace/
│  └─ frontend/
│     ├─ src/
│     │  ├─ app/
│     │  │  ├─ page.tsx                    # Live Coach Page
│     │  │  └─ admin_debug/page.tsx        # Admin Debug Page
│     │  ├─ components/
│     │  │  ├─ coach/
│     │  │  │  ├─ PandaCoach.tsx
│     │  │  │  ├─ LiveDetectionPanel.tsx
│     │  │  │  └─ SessionState.tsx
│     │  │  ├─ avatar/
│     │  │  │  ├─ AvatarRig.tsx
│     │  │  │  └─ RigBindings.ts
│     │  │  ├─ debug/
│     │  │  │  ├─ SkeletonRawView.tsx
│     │  │  │  ├─ SkeletonNormalizedView.tsx
│     │  │  │  ├─ MetricsTable.tsx
│     │  │  │  └─ GizmosOverlay.tsx
│     │  │  └─ camera/
│     │  │     └─ CameraFeed.tsx
│     │  ├─ lib/
│     │  │  ├─ socket/
│     │  │  │  ├─ client.ts
│     │  │  │  └─ events.ts
│     │  │  ├─ pose/
│     │  │  │  ├─ normalize.ts
│     │  │  │  ├─ metrics.ts
│     │  │  │  └─ classify.ts             # squat/push-up/burpees only
│     │  │  └─ types/
│     │  │     ├─ pose.ts
│     │  │     ├─ metrics.ts
│     │  │     └─ exercise.ts
│     │  └─ styles/
│     │     ├─ globals.css
│     │     └─ tokens.css
│     ├─ package.json
│     ├─ postcss.config.* 
│     └─ tailwind.config.* (if used lightly)
├─ backend/                                # only if needed
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ socket_server.py
│  │  ├─ processing/
│  │  │  ├─ normalize.py
│  │  │  ├─ metrics.py
│  │  │  └─ classify.py                   # squat/push-up/burpees only
│  │  └─ contracts/
│  │     └─ events.py
│  ├─ requirements.txt (or pyproject.toml)
│  └─ README.md
├─ scripts/
│  ├─ dev.ps1
│  ├─ dev.sh
│  ├─ test.ps1
│  ├─ test.sh
│  ├─ lint.ps1
│  └─ lint.sh
├─ .gitignore
└─ justfile
````

---

## Agent Execution Plan (Detailed but Minimal)

## Phase 1 — Consolidation

1. Read and consolidate all existing project notes/contracts/specs.
2. Extract only relevant material for:

   * live coach page
   * admin_debug page
   * squat/push-up/burpees
3. Freeze a single source of truth in docs:

   * event contracts
   * pose/metrics schemas
   * page responsibilities

Deliverable:

* `docs/architecture.md`
* `docs/socket_events.md`
* `docs/debug_metrics.md`

## Phase 2 — Frontend base wiring

1. Create Next.js app routes:

   * `/` (Live Coach Page)
   * `/admin_debug`
2. Add camera feed module.
3. Add avatar scene and rig bindings.
4. Add panda coach component placeholder/real asset hook.
5. Add Socket.IO client adapter and typed event handlers.

Deliverable:

* Pages render
* Data pipeline stubbed
* Avatar + camera visible

## Phase 3 — Detection/classification integration

1. Integrate pose input stream.
2. Implement normalization pipeline (or connect existing one).
3. Implement classification logic for exactly:

   * squat
   * push-up
   * burpees
4. Bind results to live UI panels and panda coach indicators.

Deliverable:

* Real-time exercise state displayed
* Avatar responds to motion

## Phase 4 — admin_debug completion

1. Raw skeleton view
2. Normalized skeleton view
3. Full metrics panel
4. Distance and body-size criteria computation outputs
5. Gizmos overlays and dev helper toggles

Deliverable:

* Full debug page usable for validation and tuning

## Phase 5 — Backend optionalization (Socket.IO + Python)

1. Stand up Python Socket.IO server only if needed.
2. Move normalization/classification there only if required by perf/consistency.
3. Keep event contract unchanged between local and backend modes.

Deliverable:

* Stable real-time bridge with identical frontend interface

## Phase 6 — Hardening

1. Type checks and runtime guards on payloads
2. Minimal smoke tests for:

   * camera startup
   * socket connectivity
   * classification event flow
   * debug metrics availability
3. Script and justfile commands operational on both `.ps1` and `.sh`

Deliverable:

* MVP runnable and verifiable end-to-end

---

## Definition of Done

MVP is done only when all conditions are true:

1. Two pages exist and work:

   * Live Coach Page
   * admin_debug Page

2. Live page includes:

   * camera
   * avatar
   * panda coach
   * live detection for squat/push-up/burpees

3. admin_debug includes:

   * detected skeleton visualization
   * normalization verification
   * body-size + rig distance metrics
   * full dev stats + gizmos helpers

4. Stack compliance:

   * Next 16 + R3F + Drei + Framer Motion + CSS/Tailwind/PostCSS
   * Backend (if needed) is Socket.IO + Python only

5. Project structure and scripts respect requested layout.

---

## Agent Guardrails

* Do not add unrequested product features.
* Do not change exercise scope.
* Do not create extra pages.
* Do not replace required stack.
* Do not invent business logic not present in this spec.
* If ambiguity appears, resolve by preserving minimal requested behavior.

---

## Final Instruction to Agent

Regroup all existing information, migrate to this exact MVP shape, and deliver an implementation that is complete for the defined scope only:

* 2 pages
* 3 exercises (squat, push-up, burpees)
* live coach experience with avatar/camera/panda
* full admin_debug diagnostics
* requested stack and optional Socket.IO + Python backend path.