from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class OneEuroState:
    value: float = 0.0
    derivative: float = 0.0
    initialized: bool = False


class OneEuroFilter:
    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.02,
        d_cutoff: float = 1.0,
    ) -> None:
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.state = OneEuroState()

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / max(1e-6, dt))

    def reset(self) -> None:
        self.state = OneEuroState()

    def update(self, x: float, dt: float) -> float:
        x = float(x)
        dt = max(1e-6, float(dt))
        if not self.state.initialized:
            self.state.value = x
            self.state.derivative = 0.0
            self.state.initialized = True
            return x

        dx = (x - self.state.value) / dt
        alpha_d = self._alpha(self.d_cutoff, dt)
        d_hat = alpha_d * dx + (1.0 - alpha_d) * self.state.derivative
        cutoff = self.min_cutoff + self.beta * abs(d_hat)
        alpha = self._alpha(cutoff, dt)
        x_hat = alpha * x + (1.0 - alpha) * self.state.value

        self.state.derivative = d_hat
        self.state.value = x_hat
        return x_hat


class OneEuroVec3:
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.02, d_cutoff: float = 1.0) -> None:
        self.fx = OneEuroFilter(min_cutoff=min_cutoff, beta=beta, d_cutoff=d_cutoff)
        self.fy = OneEuroFilter(min_cutoff=min_cutoff, beta=beta, d_cutoff=d_cutoff)
        self.fz = OneEuroFilter(min_cutoff=min_cutoff, beta=beta, d_cutoff=d_cutoff)

    def update(self, x: float, y: float, z: float, dt: float) -> tuple[float, float, float]:
        return (
            self.fx.update(x, dt),
            self.fy.update(y, dt),
            self.fz.update(z, dt),
        )
