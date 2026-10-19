import math

from app.processing.classify import ExerciseClassifier, PHASE_CONFIRM_FRAMES


def _frame(joints, c=0.9):
    return {
        "t": 0.0,
        "space": "normalized",
        "joints": [{"name": n, "x": x, "y": y, "z": 0.0, "c": c} for n, (x, y) in joints.items()],
    }


def _standing(knee_angle_deg=180.0, arms="down", feet=0.3):
    # Hip centre at origin, y up, torso length 1.
    bend = math.radians(180.0 - knee_angle_deg)
    shin = (math.sin(bend) * 0.9, -math.cos(bend) * 0.9)
    wrist_y = 1.6 if arms == "up" else 0.0
    return {
        "left_shoulder": (-0.2, 1.0),
        "right_shoulder": (0.2, 1.0),
        "left_elbow": (-0.3, 0.5),
        "right_elbow": (0.3, 0.5),
        "left_wrist": (-0.4, wrist_y),
        "right_wrist": (0.4, wrist_y),
        "left_hip": (-0.1, 0.0),
        "right_hip": (0.1, 0.0),
        "left_knee": (-0.1, -0.9),
        "right_knee": (0.1, -0.9),
        "left_ankle": (-feet / 2 + shin[0], -0.9 + shin[1]),
        "right_ankle": (feet / 2 + shin[0], -0.9 + shin[1]),
    }


def _plank(elbow_angle_deg):
    # Side view, body horizontal: shoulders and hips at the same height.
    half = math.radians(elbow_angle_deg) / 2
    elbow = (1.0, 0.0 - 0.4)
    return {
        "left_shoulder": (1.0, 0.0),
        "right_shoulder": (1.0, 0.0),
        "left_elbow": elbow,
        "right_elbow": elbow,
        "left_wrist": (elbow[0] + 0.4 * math.sin(math.pi - 2 * half), elbow[1] - 0.4 * math.cos(math.pi - 2 * half)),
        "right_wrist": (elbow[0] + 0.4 * math.sin(math.pi - 2 * half), elbow[1] - 0.4 * math.cos(math.pi - 2 * half)),
        "left_hip": (0.0, 0.0),
        "right_hip": (0.0, 0.0),
    }


def _feed(clf, joints, frames=PHASE_CONFIRM_FRAMES):
    state = None
    for _ in range(frames):
        state = clf.update(_frame(joints))
    return state


def test_squat_counts_one_rep_per_down_up_cycle():
    clf = ExerciseClassifier("squat")
    for _ in range(3):
        _feed(clf, _standing(175))
        _feed(clf, _standing(135))  # between thresholds: phase is kept
        _feed(clf, _standing(90))
        _feed(clf, _standing(135))
    state = _feed(clf, _standing(175))
    assert state["repCount"] == 3
    assert state["phase"] == "up"


def test_push_up_counts_reps():
    clf = ExerciseClassifier("push_up")
    for _ in range(2):
        _feed(clf, _plank(170))
        _feed(clf, _plank(80))
    state = _feed(clf, _plank(170))
    assert state["repCount"] == 2


def test_jumping_jack_counts_on_return_to_closed():
    clf = ExerciseClassifier("jumping_jack")
    _feed(clf, _standing(arms="down", feet=0.3))
    _feed(clf, _standing(arms="up", feet=0.9))
    state = _feed(clf, _standing(arms="down", feet=0.3))
    assert state["repCount"] == 1


def test_single_noisy_frame_does_not_change_phase():
    clf = ExerciseClassifier("squat")
    _feed(clf, _standing(175))
    _feed(clf, _standing(90), frames=1)
    state = _feed(clf, _standing(175))
    assert state["phase"] == "up"
    assert state["repCount"] == 0


def test_low_confidence_frames_are_ignored():
    clf = ExerciseClassifier("squat")
    _feed(clf, _standing(175))
    for _ in range(5):
        clf.update(_frame(_standing(90), c=0.1))
    assert clf.state["phase"] == "up"


def test_switching_exercise_resets_count():
    clf = ExerciseClassifier("squat")
    _feed(clf, _standing(175))
    _feed(clf, _standing(90))
    _feed(clf, _standing(175))
    assert clf.state["repCount"] == 1
    clf.set_exercise("push_up")
    assert clf.state == {"name": "push_up", "phase": "idle", "confidence": 0.0, "repCount": 0}
    clf.set_exercise("unknown")
    assert clf.state["name"] == "push_up"


def test_camera_space_frames_are_ignored():
    clf = ExerciseClassifier("squat")
    frame = _frame(_standing(90))
    frame["space"] = "camera"
    for _ in range(3):
        clf.update(frame)
    assert clf.state["phase"] == "idle"
