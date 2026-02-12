from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np


@dataclass
class JointKalmanState:
    x: np.ndarray
    P: np.ndarray
    initialized: bool = False


class JointKalmanFilter3D:
    def __init__(self) -> None:
        self.state = JointKalmanState(x=np.zeros((6, 1), dtype=np.float64), P=np.eye(6, dtype=np.float64))

    def _matrices(self, dt: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        dt = max(1e-6, float(dt))
        A = np.eye(6, dtype=np.float64)
        A[0, 3] = dt
        A[1, 4] = dt
        A[2, 5] = dt
        vel_damping = min(0.98, max(0.85, 1.0 - 0.6 * dt))
        A[3, 3] = vel_damping
        A[4, 4] = vel_damping
        A[5, 5] = vel_damping
        H = np.zeros((3, 6), dtype=np.float64)
        H[0, 0] = 1.0
        H[1, 1] = 1.0
        H[2, 2] = 1.0
        q_pos = 1.0 + 20.0 * dt
        q_vel = 4.0 + 50.0 * dt
        Q = np.diag([q_pos, q_pos, q_pos, q_vel, q_vel, q_vel]).astype(np.float64)
        R = np.diag([4.0, 4.0, 6.0]).astype(np.float64)
        I = np.eye(6, dtype=np.float64)
        return A, H, Q, R, I

    def initialize(self, pos: Tuple[float, float, float]) -> None:
        self.state.x[:] = 0.0
        self.state.x[0, 0] = float(pos[0])
        self.state.x[1, 0] = float(pos[1])
        self.state.x[2, 0] = float(pos[2])
        self.state.P = np.eye(6, dtype=np.float64) * 10.0
        self.state.initialized = True

    def predict(self, dt: float) -> Tuple[float, float, float]:
        if not self.state.initialized:
            return 0.0, 0.0, 0.0
        A, _, Q, _, _ = self._matrices(dt)
        self.state.x = A @ self.state.x
        # Guard against runaway prediction when measurements are temporarily missing.
        vel = self.state.x[3:6, 0]
        speed = float(np.linalg.norm(vel))
        if speed > 5000.0:
            self.state.x[3:6, 0] = vel * (5000.0 / speed)
        self.state.P = A @ self.state.P @ A.T + Q
        return tuple(float(v) for v in self.state.x[:3, 0])

    def update(self, measurement: Tuple[float, float, float], confidence: float, dt: float) -> Tuple[float, float, float]:
        if not self.state.initialized:
            self.initialize(measurement)
            return tuple(float(v) for v in self.state.x[:3, 0])

        A, H, Q, R_base, I = self._matrices(dt)
        self.state.x = A @ self.state.x
        self.state.P = A @ self.state.P @ A.T + Q

        z = np.array(measurement, dtype=np.float64).reshape(3, 1)
        conf = max(1e-3, min(1.0, float(confidence)))
        R = R_base / conf

        y = z - H @ self.state.x
        S = H @ self.state.P @ H.T + R
        K = self.state.P @ H.T @ np.linalg.inv(S)
        self.state.x = self.state.x + K @ y
        self.state.P = (I - K @ H) @ self.state.P
        return tuple(float(v) for v in self.state.x[:3, 0])

    def current(self) -> Tuple[float, float, float]:
        return tuple(float(v) for v in self.state.x[:3, 0])


class KalmanBank3D:
    def __init__(self) -> None:
        self.filters: Dict[str, JointKalmanFilter3D] = {}

    def ensure(self, name: str) -> JointKalmanFilter3D:
        if name not in self.filters:
            self.filters[name] = JointKalmanFilter3D()
        return self.filters[name]

    def predict_all(self, dt: float) -> Dict[str, Tuple[float, float, float]]:
        out: Dict[str, Tuple[float, float, float]] = {}
        for name, filt in self.filters.items():
            if filt.state.initialized:
                out[name] = filt.predict(dt)
        return out

    def update_joint(self, name: str, pos: Tuple[float, float, float], confidence: float, dt: float) -> Tuple[float, float, float]:
        filt = self.ensure(name)
        return filt.update(pos, confidence, dt)

    def get(self, name: str) -> Tuple[float, float, float] | None:
        filt = self.filters.get(name)
        if not filt or not filt.state.initialized:
            return None
        return filt.current()
