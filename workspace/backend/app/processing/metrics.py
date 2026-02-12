from __future__ import annotations

from typing import Dict

from ..contracts.events import PoseFrame, PoseMetrics


def _get_joint(frame: PoseFrame, name: str):
    return next((joint for joint in frame["joints"] if joint["name"] == name), None)


def _distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    return ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 + (a["z"] - b["z"]) ** 2) ** 0.5


def compute_metrics(frame: PoseFrame) -> PoseMetrics:
    left_shoulder = _get_joint(frame, "left_shoulder")
    right_shoulder = _get_joint(frame, "right_shoulder")
    left_hip = _get_joint(frame, "left_hip")
    right_hip = _get_joint(frame, "right_hip")
    left_ankle = _get_joint(frame, "left_ankle")
    right_ankle = _get_joint(frame, "right_ankle")
    nose = _get_joint(frame, "nose")

    shoulder_width = _distance(left_shoulder, right_shoulder) if left_shoulder and right_shoulder else 0.0
    hip_width = _distance(left_hip, right_hip) if left_hip and right_hip else 0.0

    height_top = nose or left_shoulder or right_shoulder or left_hip or right_hip
    height_bottom = left_ankle or right_ankle or left_hip or right_hip
    height = _distance(height_top, height_bottom) if height_top and height_bottom else 0.0

    confidence = (
        sum(joint["c"] for joint in frame["joints"]) / max(len(frame["joints"]), 1)
    )

    return {
        "confidence": float(confidence),
        "body": {
            "height": float(height),
            "shoulderWidth": float(shoulder_width),
            "hipWidth": float(hip_width),
        },
        "distances": {
            "shoulderWidth": float(shoulder_width),
            "hipWidth": float(hip_width),
            "height": float(height),
        },
    }
