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
- joint visibility: c >= 0.1
- low confidence: average c < 0.35

## Notes
- admin_debug is allowed to be utilitarian.
- no extra pages beyond admin_debug.
