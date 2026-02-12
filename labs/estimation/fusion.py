from __future__ import annotations

from collections import OrderedDict
from typing import Dict, Iterable, List, Tuple

import numpy as np

from labs.estimation.bone_constraints import BoneConstraintSolver
from labs.estimation.kalman_bank import KalmanBank3D
from labs.estimation.kinematics import KinematicsModel, slerp
from labs.estimation.one_euro import OneEuroVec3
from labs.estimation.quality import compute_quality
from labs.estimation.scale_solver import ScaleSolver
from labs.types import PoseEstimate, PoseJointState, PoseMeasurement


CORE_BODY17 = {
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
}


class PoseFusionEngine:
    def __init__(
        self,
        bone_pairs: Iterable[Tuple[str, str]],
        scale_mode: str = "uncalibrated",
        cm_per_unit: float | None = None,
        stale_policy: str = "graceful",
        max_stale_frames: int = 45,
        canonical_lock: bool = True,
        noncore_mode: str = "hold",
    ) -> None:
        self.bone_pairs = list(bone_pairs)
        self.kalman = KalmanBank3D()
        self.bones = BoneConstraintSolver(self.bone_pairs)
        self.kinematics = KinematicsModel(self.bone_pairs, canonical_lock=canonical_lock)
        self.scale = ScaleSolver(mode=scale_mode, cm_per_unit=cm_per_unit)
        self.filters: Dict[str, OneEuroVec3] = {}

        self.pending: "OrderedDict[int, PoseMeasurement]" = OrderedDict()
        self.last_timestamp_s = 0.0
        self.last_core_joints: List[PoseJointState] = []
        self.last_full_joints: List[PoseJointState] = []
        self.last_raw_full_joints: List[PoseJointState] = []
        self.last_raw_full_frame_idx = -1
        self.last_quaternions: Dict[str, np.ndarray] = {}
        self.confidence_map: Dict[str, float] = {}
        self.missing_counts: Dict[str, int] = {}
        self.max_pending = 64
        self.max_stale_frames = max(0, int(max_stale_frames))
        self.stale_policy = stale_policy if stale_policy in ("strict", "graceful") else "graceful"
        self.noncore_mode = noncore_mode if noncore_mode in ("hold", "predict", "drop") else "hold"
        self.stale_decay = 3.0
        self.init_confidence_min = 0.12
        self.last_bbox_xyxy: tuple[float, float, float, float] | None = None

    def ingest_measurement(self, measurement: PoseMeasurement) -> None:
        self.pending[measurement.frame_idx] = measurement
        while len(self.pending) > self.max_pending:
            self.pending.popitem(last=False)

    def _ensure_filter(self, name: str) -> OneEuroVec3:
        if name not in self.filters:
            self.filters[name] = OneEuroVec3(min_cutoff=1.0, beta=0.03, d_cutoff=1.0)
        return self.filters[name]

    def _core_only(self, joints: List[PoseJointState]) -> List[PoseJointState]:
        return [PoseJointState(**j.__dict__) for j in joints if j.name in CORE_BODY17]

    def _apply_measurement_core(
        self,
        joints_core: List[PoseJointState],
        dt: float,
        frame_shape: tuple[int, int, int],
        age_frames: int = 0,
    ) -> None:
        h, w = frame_shape[:2]
        diag = float(np.hypot(float(w), float(h)))
        soft_jump = max(18.0, 0.12 * diag)
        hard_jump = max(40.0, 0.30 * diag)
        z_lim = max(float(w), float(h)) * 1.5
        age_scale = float(np.exp(-max(0, int(age_frames)) / max(1e-6, self.stale_decay)))
        for j in joints_core:
            x = float(np.clip(float(j.x), -0.2 * w, 1.2 * w))
            y = float(np.clip(float(j.y), -0.2 * h, 1.2 * h))
            z = float(np.clip(float(j.z), -z_lim, z_lim))
            pos = (x, y, z)
            prev = self.kalman.get(j.name)
            conf = max(0.0, min(1.0, float(j.c))) * age_scale
            if prev is None and conf < self.init_confidence_min:
                continue
            if prev is not None:
                dist = float(np.linalg.norm(np.array(pos, dtype=np.float64) - np.array(prev, dtype=np.float64)))
                if dist > hard_jump:
                    self.missing_counts[j.name] = int(self.missing_counts.get(j.name, 0)) + 1
                    continue
                if dist > soft_jump:
                    conf *= soft_jump / max(dist, 1e-6)
            if conf < 0.08 and prev is not None:
                self.confidence_map[j.name] = max(0.05, self.confidence_map.get(j.name, 0.5) * 0.98)
                self.missing_counts[j.name] = int(self.missing_counts.get(j.name, 0)) + 1
                continue
            self.kalman.update_joint(j.name, pos, conf, dt)
            self.confidence_map[j.name] = float(max(conf, self.confidence_map.get(j.name, 0.0)))
            self.missing_counts[j.name] = 0

    def _predict_core(self, dt: float, frame_shape: tuple[int, int, int]) -> List[PoseJointState]:
        preds = self.kalman.predict_all(dt)
        h, w = frame_shape[:2]
        out: List[PoseJointState] = []
        z_lim = max(float(w), float(h)) * 1.5
        for name in CORE_BODY17:
            if name not in preds:
                continue
            pos = preds[name]
            miss = int(self.missing_counts.get(name, 0)) + 1
            self.missing_counts[name] = miss
            if miss >= 5:
                filt = self.kalman.filters.get(name)
                if filt is not None and filt.state.initialized:
                    damp = 0.75 if miss < 12 else 0.5
                    filt.state.x[3:6, 0] *= damp
            conf = max(0.05, self.confidence_map.get(name, 0.3) * 0.96)
            self.confidence_map[name] = conf
            x, y, z = pos
            x = float(np.clip(x, -0.15 * w, 1.15 * w))
            y = float(np.clip(y, -0.15 * h, 1.15 * h))
            z = float(np.clip(z, -z_lim, z_lim))
            f = self._ensure_filter(name)
            x, y, z = f.update(x, y, z, dt)
            out.append(
                PoseJointState(
                    name=name,
                    x=float(x),
                    y=float(y),
                    z=float(z),
                    c=float(conf),
                    px=float(x / max(1.0, float(w))),
                    py=float(y / max(1.0, float(h))),
                )
            )
        return out

    def _current_core(self, frame_shape: tuple[int, int, int], dt: float) -> List[PoseJointState]:
        h, w = frame_shape[:2]
        out: List[PoseJointState] = []
        z_lim = max(float(w), float(h)) * 1.5
        for name in CORE_BODY17:
            filt = self.kalman.filters.get(name)
            if filt is None or not filt.state.initialized:
                continue
            x, y, z = filt.current()
            x = float(np.clip(x, -0.15 * w, 1.15 * w))
            y = float(np.clip(y, -0.15 * h, 1.15 * h))
            z = float(np.clip(z, -z_lim, z_lim))
            f = self._ensure_filter(name)
            x, y, z = f.update(x, y, z, dt)
            conf = self.confidence_map.get(name, 0.5)
            out.append(
                PoseJointState(
                    name=name,
                    x=float(x),
                    y=float(y),
                    z=float(z),
                    c=float(conf),
                    px=float(x / max(1.0, float(w))),
                    py=float(y / max(1.0, float(h))),
                )
            )
        return out

    @staticmethod
    def _map_by_name(joints: List[PoseJointState]) -> Dict[str, PoseJointState]:
        return {j.name: j for j in joints}

    def _merge_full_joints(
        self,
        frame_shape: tuple[int, int, int],
        fused_core: List[PoseJointState],
    ) -> List[PoseJointState]:
        if self.noncore_mode == "drop":
            return [PoseJointState(**j.__dict__) for j in fused_core]
        if self.noncore_mode == "predict":
            # Non-core prediction is intentionally conservative: keep last raw for now.
            pass
        # hold mode: keep full raw, replace core with fused body17.
        full = [PoseJointState(**j.__dict__) for j in self.last_raw_full_joints] if self.last_raw_full_joints else []
        fmap = self._map_by_name(full)
        for cj in fused_core:
            fmap[cj.name] = PoseJointState(**cj.__dict__)
        merged = list(fmap.values())
        if not merged:
            merged = [PoseJointState(**j.__dict__) for j in fused_core]
        h, w = frame_shape[:2]
        for j in merged:
            j.px = float(np.clip(j.x / max(1.0, float(w)), 0.0, 1.0))
            j.py = float(np.clip(j.y / max(1.0, float(h)), 0.0, 1.0))
        return merged

    def estimate_for_frame(
        self,
        frame_idx: int,
        timestamp_s: float,
        frame_shape: tuple[int, int, int],
    ) -> PoseEstimate:
        raw_dt = float(timestamp_s - self.last_timestamp_s) if self.last_timestamp_s > 0 else 1.0 / 30.0
        dt = min(0.08, max(1.0 / 120.0, raw_dt))
        self.last_timestamp_s = float(timestamp_s)

        source = "predicted"
        applied_measurement = False
        measurement_age_frames = -1
        measurement_queue_delay_ms = 0.0

        keys_to_apply = [k for k in self.pending.keys() if k <= frame_idx]
        latest_meas: PoseMeasurement | None = None
        latest_key = -1
        for k in keys_to_apply:
            meas = self.pending.pop(k)
            if k >= latest_key:
                latest_key = k
                latest_meas = meas

        if latest_meas is not None and latest_meas.status == "ok" and latest_meas.joints:
            age_frames = max(0, int(frame_idx - latest_meas.frame_idx))
            measurement_age_frames = age_frames
            measurement_queue_delay_ms = float(latest_meas.queue_delay_ms)
            self.last_bbox_xyxy = tuple(latest_meas.bbox_xyxy) if latest_meas.bbox_xyxy is not None else self.last_bbox_xyxy
            self.last_raw_full_joints = [PoseJointState(**j.__dict__) for j in latest_meas.joints]
            self.last_raw_full_frame_idx = int(latest_meas.frame_idx)
            has_initialized_state = any(f.state.initialized for f in self.kalman.filters.values())
            allow_stale = self.stale_policy == "graceful" or age_frames <= self.max_stale_frames
            if not has_initialized_state:
                allow_stale = True
            if allow_stale:
                effective_age = 0 if not has_initialized_state else age_frames
                core_meas = self._core_only(latest_meas.joints)
                self._apply_measurement_core(core_meas, dt, frame_shape, age_frames=effective_age)
                source = "measured" if age_frames == 0 else "interpolated"
                applied_measurement = True

        fused_core = self._current_core(frame_shape, dt) if applied_measurement else self._predict_core(dt, frame_shape)
        if not fused_core and self.last_core_joints:
            fused_core = [PoseJointState(**j.__dict__) for j in self.last_core_joints]
            source = "predicted"

        if source in ("measured", "interpolated"):
            self.bones.update_reference(fused_core)
        fused_core = self.bones.solve(fused_core, iterations=2)

        h, w = frame_shape[:2]
        for j in fused_core:
            j.px = float(np.clip(j.x / max(1.0, float(w)), 0.0, 1.0))
            j.py = float(np.clip(j.y / max(1.0, float(h)), 0.0, 1.0))

        normalized = self.kinematics.normalize_pose(fused_core)
        quats_raw = self.kinematics.compute_local_quaternions(fused_core)
        blend_alpha = 0.65 if source == "measured" else (0.45 if source == "interpolated" else 0.28)
        quats: Dict[str, Tuple[float, float, float, float]] = {}
        for name, q in quats_raw.items():
            curr = np.array(q, dtype=np.float64)
            prev = self.last_quaternions.get(name)
            sm = curr if prev is None else slerp(prev, curr, blend_alpha)
            self.last_quaternions[name] = sm
            quats[name] = (float(sm[0]), float(sm[1]), float(sm[2]), float(sm[3]))

        full_joints = self._merge_full_joints(frame_shape, fused_core)
        quality = compute_quality(fused_core, self.last_core_joints, measured=(source in ("measured", "interpolated")))
        scale = self.scale.estimate(fused_core, quality)
        noncore_age_frames = max(0, int(frame_idx - self.last_raw_full_frame_idx)) if self.last_raw_full_frame_idx >= 0 else 0

        est = PoseEstimate(
            frame_idx=frame_idx,
            timestamp_s=timestamp_s,
            source=source,
            joints=full_joints,
            fused_body17_joints=fused_core,
            normalized_joints=normalized,
            quaternions=quats,
            quality=quality,
            scale=scale,
            bbox_xyxy=self.last_bbox_xyxy,
            measurement_age_frames=measurement_age_frames,
            noncore_age_frames=noncore_age_frames,
            queue_delay_ms=measurement_queue_delay_ms,
            canonical_yaw_deg=float(self.kinematics.last_canonical_yaw_deg),
        )
        self.last_core_joints = [PoseJointState(**j.__dict__) for j in fused_core]
        self.last_full_joints = [PoseJointState(**j.__dict__) for j in full_joints]
        return est

