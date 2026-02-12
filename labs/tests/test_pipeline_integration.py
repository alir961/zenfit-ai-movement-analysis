from labs.estimation.fusion import PoseFusionEngine
from labs.types import PoseJointState, PoseMeasurement


BONES = [
    ("left_hip", "left_knee"),
    ("left_knee", "left_ankle"),
    ("left_hip", "right_hip"),
    ("left_hip", "left_shoulder"),
    ("right_hip", "right_shoulder"),
]


def _joint(name, x, y, z, c=0.9):
    return PoseJointState(name=name, x=x, y=y, z=z, c=c, px=0.0, py=0.0)


def test_fusion_pipeline_measured_then_predicted():
    fusion = PoseFusionEngine(bone_pairs=BONES, scale_mode="uncalibrated")

    meas0 = PoseMeasurement(
        frame_idx=0,
        timestamp_s=0.0,
        joints=[
            _joint("left_ankle", 100, 200, 0),
            _joint("left_knee", 100, 150, 0),
            _joint("left_hip", 100, 100, 0),
            _joint("right_hip", 130, 100, 0),
            _joint("left_shoulder", 95, 60, 0),
            _joint("right_shoulder", 135, 60, 0),
            _joint("nose", 115, 40, 0),
        ],
        infer_ms=25.0,
        queue_delay_ms=1.0,
    )
    fusion.ingest_measurement(meas0)

    est0 = fusion.estimate_for_frame(0, 0.0, (480, 640, 3))
    assert est0.source == "measured"
    assert est0.joints
    assert est0.measurement_age_frames == 0

    est1 = fusion.estimate_for_frame(1, 1.0 / 30.0, (480, 640, 3))
    assert est1.source in ("predicted", "interpolated")
    assert est1.joints
    assert isinstance(est1.canonical_yaw_deg, float)


def test_strict_policy_allows_late_init_measurement():
    fusion = PoseFusionEngine(bone_pairs=BONES, scale_mode="uncalibrated", stale_policy="strict", max_stale_frames=0)
    meas = PoseMeasurement(
        frame_idx=0,
        timestamp_s=0.0,
        joints=[
            _joint("left_ankle", 100, 200, 0),
            _joint("left_knee", 100, 150, 0),
            _joint("left_hip", 100, 100, 0),
            _joint("right_hip", 130, 100, 0),
            _joint("left_shoulder", 95, 60, 0),
            _joint("right_shoulder", 135, 60, 0),
            _joint("nose", 115, 40, 0),
        ],
        infer_ms=20.0,
        queue_delay_ms=4.0,
    )
    fusion.ingest_measurement(meas)
    est = fusion.estimate_for_frame(8, 8.0 / 30.0, (480, 640, 3))
    assert est.joints
    assert est.source in ("interpolated", "measured")
