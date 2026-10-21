from __future__ import annotations

from typing import List, NotRequired, TypedDict, Literal, Dict

POSE_INPUT = "pose/input"
SESSION_START = "session/start"
POSE_NORMALIZED = "pose/normalized"
POSE_METRICS = "pose/metrics"
EXERCISE_STATE = "exercise/state"
DEBUG_STATE = "debug/state"

JointName = str

JOINT_NAMES: List[JointName] = [
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


class PoseJoint(TypedDict):
    name: JointName
    x: float
    y: float
    z: float
    c: float
    # Image position (0..1); sent with camera-space frames
    px: NotRequired[float]
    py: NotRequired[float]


class PoseFrame(TypedDict):
    t: float
    space: Literal["camera", "normalized"]
    joints: List[PoseJoint]


class NormalizationParams(TypedDict):
    center: Dict[str, float]
    scale: float


class PoseMetrics(TypedDict):
    confidence: float
    body: Dict[str, float]
    distances: Dict[str, float]


ExerciseName = Literal["squat", "push_up", "jumping_jack", "bicep_curl", "lateral_raise", "none"]


class ExerciseState(TypedDict):
    name: ExerciseName
    phase: Literal["idle", "down", "up", "hold", "transition"]
    confidence: float
    repCount: int
