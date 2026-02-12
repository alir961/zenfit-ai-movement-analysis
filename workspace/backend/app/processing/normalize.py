from __future__ import annotations

from typing import Tuple

from ..contracts.events import PoseFrame, NormalizationParams


def _get_joint(frame: PoseFrame, name: str):
    return next((joint for joint in frame["joints"] if joint["name"] == name), None)


def normalize_pose(frame: PoseFrame) -> Tuple[PoseFrame, NormalizationParams]:
    left_hip = _get_joint(frame, "left_hip")
    right_hip = _get_joint(frame, "right_hip")
    left_shoulder = _get_joint(frame, "left_shoulder")
    right_shoulder = _get_joint(frame, "right_shoulder")

    if not left_hip or not right_hip or not left_shoulder or not right_shoulder:
        params: NormalizationParams = {"center": {"x": 0, "y": 0, "z": 0}, "scale": 1.0}
        return frame, params

    center = {
        "x": (left_hip["x"] + right_hip["x"]) / 2.0,
        "y": (left_hip["y"] + right_hip["y"]) / 2.0,
        "z": (left_hip["z"] + right_hip["z"]) / 2.0,
    }

    shoulder_center = {
        "x": (left_shoulder["x"] + right_shoulder["x"]) / 2.0,
        "y": (left_shoulder["y"] + right_shoulder["y"]) / 2.0,
        "z": (left_shoulder["z"] + right_shoulder["z"]) / 2.0,
    }

    torso = (
        shoulder_center["x"] - center["x"],
        shoulder_center["y"] - center["y"],
        shoulder_center["z"] - center["z"],
    )

    scale = max((torso[0] ** 2 + torso[1] ** 2 + torso[2] ** 2) ** 0.5, 0.0001)

    normalized_joints = []
    for joint in frame["joints"]:
        normalized_joints.append(
            {
                **joint,
                "x": (joint["x"] - center["x"]) / scale,
                "y": -(joint["y"] - center["y"]) / scale,
                "z": (joint["z"] - center["z"]) / scale,
            }
        )

    params: NormalizationParams = {"center": center, "scale": scale}

    normalized_frame: PoseFrame = {
        **frame,
        "space": "normalized",
        "joints": normalized_joints,
    }

    return normalized_frame, params
