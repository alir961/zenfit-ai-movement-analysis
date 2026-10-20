# Skeleton Layers

## Overlay A: Model Skeleton
- Driven by the loaded GLB/GLTF rig in `frontend/renderer.js`.
- Uses current armature inspector, joints, axes, T-pose, transform controls.

## Overlay B: RTMW3D Raw17
- 17 keypoints from RTMW3D prediction.
- Names follow COCO17:
  - `nose, left_eye, right_eye, left_ear, right_ear, left_shoulder, right_shoulder, left_elbow, right_elbow, left_wrist, right_wrist, left_hip, right_hip, left_knee, right_knee, left_ankle, right_ankle`
- Edges are provided in payload and rendered as coral lines.

## Overlay C: Mapped Humanoid
- Expanded skeleton generated from raw17 + placeholders.
- Includes derived joints: `Pelvis, Spine, Chest, Neck, Head, Upper`.
- Includes placeholders: `L_Hand, R_Hand, L_Foot, R_Foot, L_Toe, R_Toe`.
- `is_placeholder` and `source_points` are explicit in payload.

## Toggle Control
- `raw17` and `mapped_humanoid` checkboxes are independent.
