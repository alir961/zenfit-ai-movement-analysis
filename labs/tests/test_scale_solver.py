from labs.estimation.quality import compute_quality
from labs.estimation.scale_solver import ScaleSolver
from labs.types import PoseJointState


def _make_joint(name, x, y, z, c=0.9):
    return PoseJointState(name=name, x=x, y=y, z=z, c=c, px=0.5, py=0.5)


def test_scale_solver_uncalibrated_outputs_ci_and_flag():
    joints = [
        _make_joint("left_ankle", 0.0, 0.0, 0.0),
        _make_joint("left_knee", 0.0, 0.4, 0.0),
        _make_joint("left_hip", 0.0, 0.8, 0.0),
        _make_joint("right_hip", 0.2, 0.8, 0.0),
        _make_joint("nose", 0.1, 1.3, 0.0),
    ]
    quality = compute_quality(joints, None, measured=True)
    solver = ScaleSolver(mode="uncalibrated")
    out = solver.estimate(joints, quality)
    assert out.height_estimate_cm > 0
    assert out.confidence_interval_cm[1] > out.confidence_interval_cm[0]
    assert "scale_unobservable" in out.quality_flags


def test_scale_solver_calibrated_uses_cm_per_unit():
    joints = [
        _make_joint("left_ankle", 0.0, 0.0, 0.0),
        _make_joint("left_knee", 0.0, 0.5, 0.0),
        _make_joint("left_hip", 0.0, 1.0, 0.0),
        _make_joint("right_hip", 0.2, 1.0, 0.0),
        _make_joint("nose", 0.1, 1.5, 0.0),
    ]
    quality = compute_quality(joints, None, measured=True)
    solver = ScaleSolver(mode="calibrated", cm_per_unit=100.0)
    out = solver.estimate(joints, quality)
    assert out.mode == "calibrated"
    assert out.height_estimate_cm > 0
