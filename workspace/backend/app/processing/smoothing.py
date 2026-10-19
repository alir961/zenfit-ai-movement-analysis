from __future__ import annotations

import math
import time
from typing import Callable, Dict, Optional

from ..contracts.events import PoseFrame

# Tuned for normalized space (torso length = 1) at ~10 FPS input:
# steady joints are smoothed hard, fast joints follow with little lag.
MIN_CUTOFF_HZ = 1.5
BETA = 0.5
D_CUTOFF_HZ = 1.0
# Joints below this confidence are passed through and do not update the filter.
MIN_JOINT_CONFIDENCE = 0.3
# After a gap this long (no person, dropped frames) the filters restart.
RESET_AFTER_S = 0.5


def _alpha(cutoff: float, dt: float) -> float:
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class _OneEuro:
    """One-Euro filter (Casiez et al. 2012), same algorithm as labs/estimation/one_euro.py."""

    def __init__(self) -> None:
        self.value: Optional[float] = None
        self.derivative = 0.0

    def update(self, x: float, dt: float) -> float:
        if self.value is None:
            self.value = x
            return x
        dx = (x - self.value) / dt
        a_d = _alpha(D_CUTOFF_HZ, dt)
        self.derivative = a_d * dx + (1.0 - a_d) * self.derivative
        a = _alpha(MIN_CUTOFF_HZ + BETA * abs(self.derivative), dt)
        self.value = a * x + (1.0 - a) * self.value
        return self.value


class PoseSmoother:
    """Per-joint One-Euro smoothing of normalized pose frames for one client."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._filters: Dict[str, tuple[_OneEuro, _OneEuro, _OneEuro]] = {}
        self._last_t: Optional[float] = None

    def reset(self) -> None:
        self._filters.clear()
        self._last_t = None

    def update(self, frame: PoseFrame) -> PoseFrame:
        now = self._clock()
        if self._last_t is None or now - self._last_t > RESET_AFTER_S:
            self._filters.clear()
            dt = 1.0
        else:
            dt = max(now - self._last_t, 1e-3)
        self._last_t = now

        joints = []
        for joint in frame["joints"]:
            if joint.get("c", 0.0) < MIN_JOINT_CONFIDENCE:
                joints.append(joint)
                continue
            fx, fy, fz = self._filters.setdefault(joint["name"], (_OneEuro(), _OneEuro(), _OneEuro()))
            joints.append(
                {
                    **joint,
                    "x": fx.update(joint["x"], dt),
                    "y": fy.update(joint["y"], dt),
                    "z": fz.update(joint["z"], dt),
                }
            )
        return {**frame, "joints": joints}
