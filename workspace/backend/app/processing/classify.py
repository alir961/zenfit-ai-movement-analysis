from __future__ import annotations

from typing import Dict, Iterable, Optional
import math

from ..contracts.events import ExerciseName, ExerciseState, PoseFrame

# Joints below this confidence are treated as missing.
MIN_JOINT_CONFIDENCE = 0.3
# A new phase must be seen on this many consecutive frames before it is accepted.
PHASE_CONFIRM_FRAMES = 2

# Squat: average knee angle (degrees).
SQUAT_DOWN_ANGLE = 120.0
SQUAT_UP_ANGLE = 155.0
# Push-up: average elbow angle (degrees), only while the torso is roughly horizontal.
PUSH_UP_DOWN_ANGLE = 100.0
PUSH_UP_UP_ANGLE = 150.0
# Max |shoulder.y - hip.y| in torso lengths (normalized space) to count as a plank (~30 deg).
PLANK_MAX_TORSO_RISE = 0.5
# Jumping jack: ankle spread relative to shoulder width.
JACK_OPEN_FEET_RATIO = 1.6
JACK_CLOSED_FEET_RATIO = 1.2

SUPPORTED_EXERCISES: tuple[ExerciseName, ...] = ("squat", "push_up", "jumping_jack")

_REQUIRED_JOINTS: Dict[str, tuple[str, ...]] = {
    "squat": ("left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"),
    "push_up": (
        "left_shoulder",
        "right_shoulder",
        "left_elbow",
        "right_elbow",
        "left_wrist",
        "right_wrist",
        "left_hip",
        "right_hip",
    ),
    "jumping_jack": (
        "left_shoulder",
        "right_shoulder",
        "left_wrist",
        "right_wrist",
        "left_ankle",
        "right_ankle",
    ),
}

# Entering this phase from the opposite one completes a repetition.
_REP_COMPLETING_PHASE = {"squat": "up", "push_up": "up", "jumping_jack": "down"}


def _angle_at(a: Dict[str, float], b: Dict[str, float], c: Dict[str, float]) -> float:
    ab = (a["x"] - b["x"], a["y"] - b["y"], a["z"] - b["z"])
    cb = (c["x"] - b["x"], c["y"] - b["y"], c["z"] - b["z"])
    dot = ab[0] * cb[0] + ab[1] * cb[1] + ab[2] * cb[2]
    mag = (ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2) ** 0.5 * (cb[0] ** 2 + cb[1] ** 2 + cb[2] ** 2) ** 0.5
    if mag == 0:
        return 180.0
    cos = max(-1.0, min(1.0, dot / mag))
    return float(math.degrees(math.acos(cos)))


def _mid_y(a: Dict[str, float], b: Dict[str, float]) -> float:
    return (a["y"] + b["y"]) / 2.0


def _default_state(name: ExerciseName = "none") -> ExerciseState:
    return {
        "name": name,
        "phase": "idle",
        "confidence": 0.0,
        "repCount": 0,
    }


def _squat_phase(j: Dict[str, Dict[str, float]]) -> Optional[str]:
    knee_angle = (
        _angle_at(j["left_hip"], j["left_knee"], j["left_ankle"])
        + _angle_at(j["right_hip"], j["right_knee"], j["right_ankle"])
    ) / 2.0
    if knee_angle < SQUAT_DOWN_ANGLE:
        return "down"
    if knee_angle > SQUAT_UP_ANGLE:
        return "up"
    return None


def _push_up_phase(j: Dict[str, Dict[str, float]]) -> Optional[str]:
    shoulder_y = _mid_y(j["left_shoulder"], j["right_shoulder"])
    hip_y = _mid_y(j["left_hip"], j["right_hip"])
    if abs(shoulder_y - hip_y) > PLANK_MAX_TORSO_RISE:
        return None
    elbow_angle = (
        _angle_at(j["left_shoulder"], j["left_elbow"], j["left_wrist"])
        + _angle_at(j["right_shoulder"], j["right_elbow"], j["right_wrist"])
    ) / 2.0
    if elbow_angle < PUSH_UP_DOWN_ANGLE:
        return "down"
    if elbow_angle > PUSH_UP_UP_ANGLE:
        return "up"
    return None


def _jumping_jack_phase(j: Dict[str, Dict[str, float]]) -> Optional[str]:
    shoulder_width = abs(j["left_shoulder"]["x"] - j["right_shoulder"]["x"])
    if shoulder_width <= 1e-6:
        return None
    feet_ratio = abs(j["left_ankle"]["x"] - j["right_ankle"]["x"]) / shoulder_width
    shoulder_y = _mid_y(j["left_shoulder"], j["right_shoulder"])
    wrists_above = j["left_wrist"]["y"] > shoulder_y and j["right_wrist"]["y"] > shoulder_y
    wrists_below = j["left_wrist"]["y"] < shoulder_y and j["right_wrist"]["y"] < shoulder_y
    if wrists_above and feet_ratio > JACK_OPEN_FEET_RATIO:
        return "up"
    if wrists_below and feet_ratio < JACK_CLOSED_FEET_RATIO:
        return "down"
    return None


_PHASE_DETECTORS = {
    "squat": _squat_phase,
    "push_up": _push_up_phase,
    "jumping_jack": _jumping_jack_phase,
}


class ExerciseClassifier:
    """Counts repetitions of the selected exercise from normalized pose frames.

    Expects frames in normalized space (hip-centred, y pointing up). Each exercise
    has separate enter thresholds for its two phases; between them the previous
    phase is kept, so noise around a single threshold cannot produce extra reps.
    """

    def __init__(self, exercise: ExerciseName = "squat") -> None:
        self.state: ExerciseState = _default_state(exercise)
        self._candidate: Optional[str] = None
        self._candidate_frames = 0

    def set_exercise(self, exercise: Optional[str]) -> None:
        if exercise not in SUPPORTED_EXERCISES or exercise == self.state["name"]:
            return
        self.state = _default_state(exercise)  # type: ignore[arg-type]
        self._candidate = None
        self._candidate_frames = 0

    def update(self, frame: Optional[PoseFrame]) -> ExerciseState:
        name = self.state["name"]
        if frame is None or frame.get("space") != "normalized" or name not in _PHASE_DETECTORS:
            return self.state

        joints = _confident_joints(frame["joints"], _REQUIRED_JOINTS[name])
        if joints is None:
            return self.state

        confidence = sum(joint["c"] for joint in joints.values()) / len(joints)
        next_state: ExerciseState = {**self.state, "confidence": float(max(0.0, min(1.0, confidence)))}

        observed = _PHASE_DETECTORS[name](joints)
        if observed is None or observed == self.state["phase"]:
            self._candidate = None
            self._candidate_frames = 0
            self.state = next_state
            return next_state

        if observed == self._candidate:
            self._candidate_frames += 1
        else:
            self._candidate = observed
            self._candidate_frames = 1

        if self._candidate_frames >= PHASE_CONFIRM_FRAMES:
            prev_phase = self.state["phase"]
            next_state["phase"] = observed  # type: ignore[typeddict-item]
            if prev_phase not in ("idle", observed) and observed == _REP_COMPLETING_PHASE[name]:
                next_state["repCount"] = self.state["repCount"] + 1
            self._candidate = None
            self._candidate_frames = 0

        self.state = next_state
        return next_state


def _confident_joints(joints: Iterable[Dict[str, float]], required: tuple[str, ...]) -> Optional[Dict[str, Dict[str, float]]]:
    by_name = {joint["name"]: joint for joint in joints}  # type: ignore[index]
    selected = {}
    for name in required:
        joint = by_name.get(name)
        if joint is None or joint.get("c", 0.0) < MIN_JOINT_CONFIDENCE:
            return None
        selected[name] = joint
    return selected
