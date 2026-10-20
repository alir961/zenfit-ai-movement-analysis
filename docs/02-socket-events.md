# 02-socket-events.md

## Event Names
- pose/input
- session/start
- pose/normalized
- pose/metrics
- exercise/state
- debug/state

## Payloads

### pose/input (client -> server)
```
{
  timestamp: number,
  frameId: number,
  width: number,
  height: number,
  image: Blob,
  exercise: "squat" | "push_up" | "jumping_jack" | "bicep_curl" | "lateral_raise",
  clientMeta?: Record<string, string | number | boolean>
}
```

### session/start (client -> server)
No payload. Sent when the user presses Start session: the server resets that
client's rep counter and pose smoothing, so each session counts from zero.

### pose/normalized (server -> client)
```
{
  frame: PoseFrame,
  params: NormalizationParams
}
```

### pose/metrics (server -> client)
```
{
  metrics: PoseMetrics
}
```

### exercise/state (server -> client)
```
{
  state: ExerciseState
}
```

### debug/state (server -> client)
```
{
  raw: PoseFrame | null,
  normalized: PoseFrame | null,
  params: NormalizationParams | null,
  metrics: PoseMetrics | null,
  errors?: string[]
}
```

## Types

### PoseFrame
```
{
  t: number,
  space: "camera" | "normalized",
  joints: PoseJoint[]
}
```

### PoseJoint
```
{
  name: JointName,
  x: number,
  y: number,
  z: number,
  c: number
}
```

### NormalizationParams
```
{
  center: { x: number, y: number, z: number },
  scale: number
}
```

### PoseMetrics
```
{
  confidence: number,
  body: {
    height: number,
    shoulderWidth: number,
    hipWidth: number
  },
  distances: Record<string, number>
}
```

### ExerciseState
```
{
  name: "squat" | "push_up" | "jumping_jack" | "bicep_curl" | "lateral_raise" | "none",
  phase: "idle" | "down" | "up" | "hold" | "transition",
  confidence: number,
  repCount: number
}
```
