from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List

import numpy as np


@dataclass
class OnlineGaussian:
    dimension: int
    count: int = 0
    accepted: int = 0
    rejected: int = 0
    mean: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float64))
    m2: np.ndarray = field(default_factory=lambda: np.array([[]], dtype=np.float64))

    def __post_init__(self) -> None:
        if self.mean.size == 0:
            self.mean = np.zeros(self.dimension, dtype=np.float64)
        if self.m2.size == 0 or self.m2.shape != (self.dimension, self.dimension):
            self.m2 = np.zeros((self.dimension, self.dimension), dtype=np.float64)

    def update(self, vector: Iterable[float], confidence: float = 1.0) -> None:
        x = np.asarray(list(vector), dtype=np.float64)
        if x.shape[0] != self.dimension:
            self.rejected += 1
            return

        if confidence < 0.15:
            self.rejected += 1
            return

        self.count += 1
        self.accepted += 1

        if self.count == 1:
            self.mean = x.copy()
            return

        delta = x - self.mean
        self.mean = self.mean + delta / self.count
        delta2 = x - self.mean
        self.m2 += np.outer(delta, delta2)

    def covariance(self) -> np.ndarray:
        if self.count < 2:
            return np.eye(self.dimension, dtype=np.float64) * 1e-6
        return self.m2 / (self.count - 1)

    def snapshot(self) -> Dict:
        cov = self.covariance()
        diag = np.diag(cov)
        m2_diag = np.diag(self.m2)
        return {
            "dimension": self.dimension,
            "count": self.count,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "mean": self.mean.tolist(),
            "cov_diag": diag.tolist(),
            "m2_diag": m2_diag.tolist(),
        }

    @classmethod
    def from_snapshot(cls, data: Dict) -> "OnlineGaussian":
        dim = int(data.get("dimension", 0))
        inst = cls(dimension=dim)
        inst.count = int(data.get("count", 0))
        inst.accepted = int(data.get("accepted", 0))
        inst.rejected = int(data.get("rejected", 0))
        mean = np.asarray(data.get("mean", []), dtype=np.float64)
        if mean.shape[0] == dim:
            inst.mean = mean
        m2_diag = np.asarray(data.get("m2_diag", []), dtype=np.float64)
        if m2_diag.shape[0] == dim:
            inst.m2 = np.diag(m2_diag)
        elif int(inst.count) > 1:
            cov_diag = np.asarray(data.get("cov_diag", []), dtype=np.float64)
            if cov_diag.shape[0] == dim:
                inst.m2 = np.diag(cov_diag * max(inst.count - 1, 1))
        return inst
