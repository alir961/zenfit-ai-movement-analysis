# 03-debug-metrics.md

## Required Debug Outputs
- Per joint confidence (c)
- Key distances (shoulder width, hip width, body height)
- Normalization params (center, scale)
- Exercise intermediate values (phase + confidence)

## UI Expectations
- Raw skeleton view
- Normalized skeleton view
- Metrics table with numeric values
- Gizmo toggles for bones, joints, labels

## Data Mapping
- raw pose: camera space pose
- normalized pose: centered and scaled pose
- metrics: computed from normalized pose

## Common Thresholds
- joint drawn in the debug skeleton: c >= 0.1 (`SkeletonView.tsx`)
- joint used for smoothing and exercise classification: c >= 0.3 (`MIN_JOINT_CONFIDENCE`)
- person detection score: > 0.35 (RTMW3D detector)
- the debug `confidence` metric averages c over every joint in the frame (133 for
  RTMW3D), so face and hand keypoints pull it down

## Notes
- admin_debug is allowed to be utilitarian.
- no extra pages beyond admin_debug.
