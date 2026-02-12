from __future__ import annotations

from typing import List, Optional

import numpy as np

from labs.types import PoseJointState, QualityReport

_BODY17_FOR_QUALITY = {
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
}


def compute_quality(
    joints: List[PoseJointState],
    prev_joints: Optional[List[PoseJointState]],
    measured: bool,
) -> QualityReport:
    flags: List[str] = []
    if not joints:
        return QualityReport(
            score=0.0,
            median_confidence=0.0,
            visible_ratio=0.0,
            motion_score=0.0,
            flags=["no_joints"],
        )

    body_joints = [j for j in joints if j.name in _BODY17_FOR_QUALITY]
    if not body_joints:
        body_joints = list(joints)
    confs = np.array([j.c for j in body_joints], dtype=np.float64)
    median_conf = float(np.median(confs))
    visible_ratio = float(np.mean(confs > 0.35))

    motion_score = 0.0
    if prev_joints:
        prev = {j.name: j for j in prev_joints}
        diffs = []
        for j in body_joints:
            p = prev.get(j.name)
            if p is None:
                continue
            diffs.append(np.linalg.norm(np.array([j.x - p.x, j.y - p.y, j.z - p.z], dtype=np.float64)))
        if diffs:
            motion_score = float(np.mean(diffs))

    if median_conf < 0.45:
        flags.append("low_confidence_keypoints")
    if visible_ratio < 0.7:
        flags.append("occlusion_high")
    if not measured:
        flags.append("predict_only")
    if motion_score > 25.0:
        flags.append("high_temporal_instability")

    score = float(np.clip((median_conf * 0.7) + (visible_ratio * 0.3), 0.0, 1.0))
    return QualityReport(
        score=score,
        median_confidence=median_conf,
        visible_ratio=visible_ratio,
        motion_score=motion_score,
        flags=flags,
    )
