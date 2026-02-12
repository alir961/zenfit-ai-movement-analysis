from __future__ import annotations

from typing import Dict, Optional
import math

from ..contracts.events import ExerciseState, PoseFrame
from .metrics import compute_metrics


def _get_joint(frame: PoseFrame, name: str):
    return next((joint for joint in frame["joints"] if joint["name"] == name), None)


def _angle_at(a: Dict[str, float], b: Dict[str, float], c: Dict[str, float]) -> float:
    ab = (a["x"] - b["x"], a["y"] - b["y"], a["z"] - b["z"])
    cb = (c["x"] - b["x"], c["y"] - b["y"], c["z"] - b["z"])
    dot = ab[0] * cb[0] + ab[1] * cb[1] + ab[2] * cb[2]
    mag = (ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2) ** 0.5 * (cb[0] ** 2 + cb[1] ** 2 + cb[2] ** 2) ** 0.5
    if mag == 0:
        return 180.0
    cos = max(-1.0, min(1.0, dot / mag))
    return float(math.degrees(math.acos(cos)))


def _default_state() -> ExerciseState:
    return {
        "name": "none",
        "phase": "idle",
        "confidence": 0.0,
        "repCount": 0,
    }


class ExerciseClassifier:
    def __init__(self) -> None:
        self.state: ExerciseState = _default_state()

    def update(self, frame: Optional[PoseFrame]) -> ExerciseState:
        if frame is None:
            return self.state

        left_hip = _get_joint(frame, "left_hip")
        right_hip = _get_joint(frame, "right_hip")
        left_knee = _get_joint(frame, "left_knee")
        right_knee = _get_joint(frame, "right_knee")
        left_ankle = _get_joint(frame, "left_ankle")
        right_ankle = _get_joint(frame, "right_ankle")
        left_shoulder = _get_joint(frame, "left_shoulder")
        right_shoulder = _get_joint(frame, "right_shoulder")
        left_elbow = _get_joint(frame, "left_elbow")
        right_elbow = _get_joint(frame, "right_elbow")
        left_wrist = _get_joint(frame, "left_wrist")
        right_wrist = _get_joint(frame, "right_wrist")

        if not left_hip or not right_hip or not left_knee or not right_knee or not left_ankle or not right_ankle:
            return self.state

        hip = {
            "x": (left_hip["x"] + right_hip["x"]) / 2.0,
            "y": (left_hip["y"] + right_hip["y"]) / 2.0,
            "z": (left_hip["z"] + right_hip["z"]) / 2.0,
        }

        knee = {
            "x": (left_knee["x"] + right_knee["x"]) / 2.0,
            "y": (left_knee["y"] + right_knee["y"]) / 2.0,
            "z": (left_knee["z"] + right_knee["z"]) / 2.0,
        }

        left_knee_angle = _angle_at(left_hip, left_knee, left_ankle)
        right_knee_angle = _angle_at(right_hip, right_knee, right_ankle)
        knee_angle = (left_knee_angle + right_knee_angle) / 2.0

        metrics = compute_metrics(frame)
        confidence = max(0.0, min(1.0, metrics["confidence"]))

        squat_down = hip["y"] < knee["y"] - 0.08 and knee_angle < 120
        squat_up = hip["y"] >= knee["y"] - 0.02 and knee_angle > 150

        is_push_up = False
        if left_shoulder and right_shoulder and left_elbow and right_elbow and left_wrist and right_wrist:
            shoulder_y = (left_shoulder["y"] + right_shoulder["y"]) / 2.0
            wrist_y = (left_wrist["y"] + right_wrist["y"]) / 2.0
            elbow_angle = (
                _angle_at(left_shoulder, left_elbow, left_wrist)
                + _angle_at(right_shoulder, right_elbow, right_wrist)
            ) / 2.0
            is_push_up = abs(shoulder_y - hip["y"]) < 0.2 and wrist_y < shoulder_y + 0.2 and elbow_angle < 130

        is_burpee = squat_down and is_push_up

        prev = self.state
        next_state = {**prev, "confidence": confidence}

        if is_burpee:
            next_state["name"] = "burpee"
            next_state["phase"] = "down" if squat_down else "up"
        elif is_push_up:
            next_state["name"] = "push_up"
            next_state["phase"] = "down"
        elif squat_down or squat_up:
            next_state["name"] = "squat"
            next_state["phase"] = "down" if squat_down else "up"
        else:
            next_state["name"] = "none"
            next_state["phase"] = "idle"

        if prev["name"] == next_state["name"] and prev["phase"] == "down" and next_state["phase"] == "up":
            next_state["repCount"] = prev["repCount"] + 1
        else:
            next_state["repCount"] = prev["repCount"]

        self.state = next_state
        return next_state
