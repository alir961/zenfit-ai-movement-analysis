from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence


COCO17_NAMES = [
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
]

RAW17_EDGES = [
    (0, 1), (1, 3), (0, 2), (2, 4),
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
]

HUMANOID_EDGES = [
    ("Pelvis", "Spine"),
    ("Spine", "Chest"),
    ("Chest", "Neck"),
    ("Neck", "Head"),
    ("Chest", "L_Shoulder"),
    ("L_Shoulder", "L_Elbow"),
    ("L_Elbow", "L_Wrist"),
    ("L_Wrist", "L_Hand"),
    ("Chest", "R_Shoulder"),
    ("R_Shoulder", "R_Elbow"),
    ("R_Elbow", "R_Wrist"),
    ("R_Wrist", "R_Hand"),
    ("Pelvis", "L_Hip"),
    ("L_Hip", "L_Knee"),
    ("L_Knee", "L_Ankle"),
    ("L_Ankle", "L_Foot"),
    ("L_Foot", "L_Toe"),
    ("Pelvis", "R_Hip"),
    ("R_Hip", "R_Knee"),
    ("R_Knee", "R_Ankle"),
    ("R_Ankle", "R_Foot"),
    ("R_Foot", "R_Toe"),
]


@dataclass
class Joint3D:
    name: str
    x: float
    y: float
    z: float
    confidence: float


@dataclass
class Raw17Skeleton:
    joints: List[Dict]
    edges: List[Dict]
    schema: str = "Raw17SkeletonV1"


def raw17_from_points(points: Sequence[Sequence[float]]) -> List[Dict]:
    joints: List[Dict] = []
    for i, name in enumerate(COCO17_NAMES):
        p = points[i] if i < len(points) else (0.0, 0.0, 0.0, 0.0)
        x, y, z = float(p[0]), float(p[1]), float(p[2])
        c = float(p[3]) if len(p) > 3 else 0.0
        joints.append(
            {
                "index": i,
                "name": name,
                "x": x,
                "y": y,
                "z": z,
                "confidence": c,
                "is_placeholder": False,
                "source_points": [name],
            }
        )
    return joints


def build_raw17_skeleton(points: Sequence[Sequence[float]]) -> Raw17Skeleton:
    joints = raw17_from_points(points)
    edges = [{"a": a, "b": b} for a, b in RAW17_EDGES]
    return Raw17Skeleton(joints=joints, edges=edges)


def _mid(a: Dict, b: Dict, name: str, conf_scale: float = 0.5) -> Dict:
    return {
        "name": name,
        "x": (float(a["x"]) + float(b["x"])) * 0.5,
        "y": (float(a["y"]) + float(b["y"])) * 0.5,
        "z": (float(a["z"]) + float(b["z"])) * 0.5,
        "confidence": min(float(a.get("confidence", 0.0)), float(b.get("confidence", 0.0))) * conf_scale,
        "is_placeholder": True,
        "source_points": [a["name"], b["name"]],
    }


def map_raw17_to_humanoid(raw17_joints: Sequence[Dict]) -> Dict:
    by_name = {j["name"]: j for j in raw17_joints}

    left_shoulder = by_name.get("left_shoulder")
    right_shoulder = by_name.get("right_shoulder")
    left_hip = by_name.get("left_hip")
    right_hip = by_name.get("right_hip")
    nose = by_name.get("nose")

    if not (left_shoulder and right_shoulder and left_hip and right_hip):
        raise ValueError("raw17 incomplete for humanoid mapping")

    pelvis = _mid(left_hip, right_hip, "Pelvis", conf_scale=1.0)
    chest = _mid(left_shoulder, right_shoulder, "Chest", conf_scale=0.9)
    spine = _mid(pelvis, chest, "Spine", conf_scale=0.8)

    if nose:
        neck = _mid(chest, nose, "Neck", conf_scale=0.9)
        head = {
            "name": "Head",
            "x": float(nose["x"]),
            "y": float(nose["y"]),
            "z": float(nose["z"]),
            "confidence": float(nose.get("confidence", 0.0)),
            "is_placeholder": True,
            "source_points": ["nose"],
        }
    else:
        neck = _mid(left_shoulder, right_shoulder, "Neck", conf_scale=0.7)
        head = _mid(neck, chest, "Head", conf_scale=0.5)

    mapped = [
        pelvis,
        spine,
        chest,
        neck,
        head,
        {"name": "L_Shoulder", **_clone(by_name.get("left_shoulder"), "left_shoulder")},
        {"name": "L_Elbow", **_clone(by_name.get("left_elbow"), "left_elbow")},
        {"name": "L_Wrist", **_clone(by_name.get("left_wrist"), "left_wrist")},
        {"name": "R_Shoulder", **_clone(by_name.get("right_shoulder"), "right_shoulder")},
        {"name": "R_Elbow", **_clone(by_name.get("right_elbow"), "right_elbow")},
        {"name": "R_Wrist", **_clone(by_name.get("right_wrist"), "right_wrist")},
        {"name": "L_Hip", **_clone(by_name.get("left_hip"), "left_hip")},
        {"name": "L_Knee", **_clone(by_name.get("left_knee"), "left_knee")},
        {"name": "L_Ankle", **_clone(by_name.get("left_ankle"), "left_ankle")},
        {"name": "R_Hip", **_clone(by_name.get("right_hip"), "right_hip")},
        {"name": "R_Knee", **_clone(by_name.get("right_knee"), "right_knee")},
        {"name": "R_Ankle", **_clone(by_name.get("right_ankle"), "right_ankle")},
    ]

    by_mapped = {j["name"]: j for j in mapped}

    mapped.extend(
        [
            _offset_from(by_mapped["L_Wrist"], "L_Hand", 0.04, 0.0, 0.0),
            _offset_from(by_mapped["R_Wrist"], "R_Hand", -0.04, 0.0, 0.0),
            _offset_from(by_mapped["L_Ankle"], "L_Foot", 0.0, -0.03, 0.06),
            _offset_from(by_mapped["R_Ankle"], "R_Foot", 0.0, -0.03, 0.06),
            _offset_from(by_mapped["L_Ankle"], "L_Toe", 0.0, -0.03, 0.12),
            _offset_from(by_mapped["R_Ankle"], "R_Toe", 0.0, -0.03, 0.12),
            _mid(pelvis, chest, "Upper", conf_scale=0.95),
        ]
    )

    return {
        "joints": mapped,
        "edges": [{"a": a, "b": b} for a, b in HUMANOID_EDGES],
    }


def _clone(src: Dict | None, source_name: str) -> Dict:
    if not src:
        return {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "confidence": 0.0,
            "is_placeholder": True,
            "source_points": [source_name],
        }
    return {
        "x": float(src.get("x", 0.0)),
        "y": float(src.get("y", 0.0)),
        "z": float(src.get("z", 0.0)),
        "confidence": float(src.get("confidence", 0.0)),
        "is_placeholder": bool(src.get("is_placeholder", False)),
        "source_points": list(src.get("source_points", [source_name])),
    }


def _offset_from(src: Dict, name: str, dx: float, dy: float, dz: float) -> Dict:
    return {
        "name": name,
        "x": float(src["x"]) + dx,
        "y": float(src["y"]) + dy,
        "z": float(src["z"]) + dz,
        "confidence": float(src.get("confidence", 0.0)) * 0.65,
        "is_placeholder": True,
        "source_points": list(src.get("source_points", [])),
    }
