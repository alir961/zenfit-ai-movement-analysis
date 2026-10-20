from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from labs.types import PoseJointState, QualityReport, ScaleEstimate


class ScaleSolver:
    def __init__(
        self,
        mode: str = "uncalibrated",
        cm_per_unit: float | None = None,
        prior_height_cm_mean: float = 175.0,
        prior_height_cm_std: float = 10.0,
        history_size: int = 240,
    ) -> None:
        self.mode = mode if mode in ("calibrated", "uncalibrated") else "uncalibrated"
        self.cm_per_unit = cm_per_unit
        self.prior_height_cm_mean = float(prior_height_cm_mean)
        self.prior_height_cm_std = float(prior_height_cm_std)
        self.history: List[float] = []
        self.history_size = max(30, int(history_size))
        self._rng = np.random.default_rng(42)
        self._cached_ci: tuple[float, float] = (0.0, 0.0)
        self._cached_valid = False
        self._frame_counter = 0
        self._bootstrap_every = 12

    def _segment_height_units(self, joints: List[PoseJointState]) -> float:
        j = {x.name: x for x in joints}
        l_ankle = j.get("left_ankle")
        l_knee = j.get("left_knee")
        l_hip = j.get("left_hip")
        r_hip = j.get("right_hip")
        nose = j.get("nose")

        if not l_ankle or not l_knee or not l_hip or not r_hip or not nose:
            return 0.0

        def dist(a: PoseJointState, b: PoseJointState) -> float:
            va = np.array([a.x, a.y, a.z], dtype=np.float64)
            vb = np.array([b.x, b.y, b.z], dtype=np.float64)
            return float(np.linalg.norm(vb - va))

        hip_center = PoseJointState(
            name="hip_center",
            x=(l_hip.x + r_hip.x) * 0.5,
            y=(l_hip.y + r_hip.y) * 0.5,
            z=(l_hip.z + r_hip.z) * 0.5,
            c=min(l_hip.c, r_hip.c),
            px=0.0,
            py=0.0,
        )

        # Simple anthropometric chain proxy.
        return dist(l_ankle, l_knee) + dist(l_knee, l_hip) + dist(hip_center, nose) + 0.12

    def _bootstrap_ci(self, values: List[float], n_boot: int = 200) -> tuple[float, float]:
        if not values:
            return (0.0, 0.0)
        arr = np.array(values, dtype=np.float64)
        if arr.size < 4:
            x = float(np.mean(arr))
            return (x - 5.0, x + 5.0)
        boots = np.empty((n_boot,), dtype=np.float64)
        for _ in range(n_boot):
            sample = self._rng.choice(arr, size=arr.size, replace=True)
            boots[_] = float(np.median(sample))
        lo = float(np.percentile(boots, 2.5))
        hi = float(np.percentile(boots, 97.5))
        return (lo, hi)

    def _ci_from_history(self) -> tuple[float, float]:
        self._frame_counter += 1
        if (not self._cached_valid) or (self._frame_counter % self._bootstrap_every == 0):
            self._cached_ci = self._bootstrap_ci(self.history)
            self._cached_valid = True
        return self._cached_ci

    def estimate(self, joints: List[PoseJointState], quality: QualityReport) -> ScaleEstimate:
        flags = list(quality.flags)
        raw_units = self._segment_height_units(joints)
        if raw_units <= 1e-6:
            flags.append("height_unobservable")
            return ScaleEstimate(
                mode=self.mode,
                height_estimate_cm=0.0,
                confidence_interval_cm=(0.0, 0.0),
                quality_flags=flags,
            )

        if self.mode == "calibrated":
            if self.cm_per_unit is None:
                flags.append("calib_missing_fallback_uncalibrated")
            else:
                h = raw_units * float(self.cm_per_unit)
                self.history.append(h)
                self.history = self.history[-self.history_size :]
                ci = self._ci_from_history()
                return ScaleEstimate(
                    mode="calibrated",
                    height_estimate_cm=float(h),
                    confidence_interval_cm=ci,
                    quality_flags=flags,
                )

        # Uncalibrated Bayesian-ish prior scaling.
        scale = self.prior_height_cm_mean / max(1e-6, raw_units)
        h_unc = raw_units * scale
        # Confidence-aware uncertainty widening.
        conf = max(1e-3, quality.median_confidence)
        sigma = self.prior_height_cm_std / conf
        self.history.append(h_unc)
        self.history = self.history[-self.history_size :]
        ci_boot = self._ci_from_history()
        ci = (ci_boot[0] - 0.5 * sigma, ci_boot[1] + 0.5 * sigma)
        flags.append("scale_unobservable")
        return ScaleEstimate(
            mode="uncalibrated",
            height_estimate_cm=float(h_unc),
            confidence_interval_cm=(float(ci[0]), float(ci[1])),
            quality_flags=flags,
        )


def load_calibration_cm_per_unit(path: Optional[str]) -> Optional[float]:
    if not path:
        return None
    try:
        import json

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        v = data.get("cm_per_unit")
        if v is None:
            return None
        return float(v)
    except Exception:
        return None
