from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple


SourceKind = Literal["measured", "predicted", "interpolated"]
ScaleMode = Literal["calibrated", "uncalibrated"]


@dataclass
class FramePacket:
    frame_idx: int
    timestamp_s: float
    frame_shape: Tuple[int, int, int]


@dataclass
class PoseJointState:
    name: str
    x: float
    y: float
    z: float
    c: float
    px: float
    py: float


@dataclass
class PoseMeasurement:
    frame_idx: int
    timestamp_s: float
    joints: List[PoseJointState]
    infer_ms: float
    queue_delay_ms: float
    bbox_xyxy: Optional[Tuple[float, float, float, float]] = None
    status: str = "ok"
    reason: str = ""


@dataclass
class QualityReport:
    score: float
    median_confidence: float
    visible_ratio: float
    motion_score: float
    flags: List[str] = field(default_factory=list)


@dataclass
class ScaleEstimate:
    mode: ScaleMode
    height_estimate_cm: float
    confidence_interval_cm: Tuple[float, float]
    quality_flags: List[str] = field(default_factory=list)


@dataclass
class PoseEstimate:
    frame_idx: int
    timestamp_s: float
    source: SourceKind
    joints: List[PoseJointState]
    fused_body17_joints: List[PoseJointState]
    normalized_joints: List[PoseJointState]
    quaternions: Dict[str, Tuple[float, float, float, float]]
    quality: QualityReport
    scale: ScaleEstimate
    bbox_xyxy: Optional[Tuple[float, float, float, float]] = None
    measurement_age_frames: int = 0
    noncore_age_frames: int = 0
    queue_delay_ms: float = 0.0
    canonical_yaw_deg: float = 0.0


@dataclass
class InferenceCommand:
    frame_idx: int
    timestamp_s: float
    slot_idx: int


@dataclass
class SharedMemorySpec:
    names: List[str]
    frame_shape: Tuple[int, int, int]
    dtype: str


@dataclass
class RuntimeMetrics:
    fps_display: float = 0.0
    fps_infer: float = 0.0
    latency_ms: float = 0.0
    queue_delay_ms: float = 0.0
    dropped_requests: int = 0


@dataclass
class CalibrationConfig:
    cm_per_unit: Optional[float] = None
    prior_height_cm_mean: float = 175.0
    prior_height_cm_std: float = 10.0


@dataclass
class PresetConfig:
    name: str
    backend: str
    detector_backend: str
    detector_model: str
    detector_variant: str
    pose_variant: str
    providers_order: List[str]
    track_interval: int
    skip_fixed: int


@dataclass
class LabsConfig:
    video_path: str
    preset: PresetConfig
    skip_mode: Literal["fixed", "adaptive"] = "fixed"
    skip_fixed: int = 3
    pyplot: bool = True
    ipc: Literal["shm_queue"] = "shm_queue"
    scale_mode: ScaleMode = "uncalibrated"
    calib_file: Optional[str] = None
    benchmark_labs: bool = False
    max_frames: Optional[int] = None
    show_ui: bool = True
    plot_interval_ms: int = 33
    shared_slots: int = 4
    queue_size: int = 8
    rig_profile: Literal["body17", "coco133"] = "coco133"
    plot_space: Literal["raw", "canonical", "both"] = "canonical"
    draw_min_conf: float = 0.10
    stale_policy: Literal["strict", "graceful"] = "graceful"
    max_stale_frames: int = 45
    canonical_lock: bool = True
    max_inflight_requests: int = 1
    camera_links: Literal["body17", "coco133"] = "body17"
    noncore_mode: Literal["hold", "predict", "drop"] = "hold"
    pyplot_rig: Literal["body17", "coco133"] = "body17"
    show_noncore_points: bool = True
