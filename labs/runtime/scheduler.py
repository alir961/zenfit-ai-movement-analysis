from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AdaptiveState:
    motion_score: float = 0.0
    confidence_score: float = 1.0
    infer_ms: float = 30.0


class FrameScheduler:
    def __init__(
        self,
        mode: str = "fixed",
        skip_fixed: int = 3,
        target_latency_ms: float = 33.0,
        max_skip: int = 5,
        lambda_motion: float = 1.0,
        lambda_confidence: float = 1.0,
    ) -> None:
        self.mode = mode if mode in ("fixed", "adaptive") else "fixed"
        self.skip_fixed = max(0, int(skip_fixed))
        self.target_latency_ms = max(1.0, float(target_latency_ms))
        self.max_skip = max(1, int(max_skip))
        self.lambda_motion = float(lambda_motion)
        self.lambda_confidence = float(lambda_confidence)
        self._adaptive_skip = self.skip_fixed

    def _adaptive_interval(self, state: AdaptiveState) -> int:
        infer_ms = max(1e-6, float(state.infer_ms))
        motion = max(0.0, float(state.motion_score))
        conf = min(1.0, max(0.0, float(state.confidence_score)))

        value = (
            (self.target_latency_ms / infer_ms)
            * (1.0 / (1.0 + self.lambda_motion * motion))
            * (1.0 + self.lambda_confidence * (1.0 - conf))
        )
        n = int(value)
        n = max(0, min(self.max_skip, n))
        return n

    def infer_interval(self, frame_idx: int, state: AdaptiveState) -> int:
        if self.mode == "fixed":
            return self.skip_fixed
        self._adaptive_skip = self._adaptive_interval(state)
        return self._adaptive_skip

    def should_infer(self, frame_idx: int, state: AdaptiveState) -> bool:
        skip = self.infer_interval(frame_idx, state)
        return frame_idx % (skip + 1) == 0
