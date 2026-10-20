from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, Iterable, List, Tuple

import numpy as np

from labs.types import PoseJointState


class BoneConstraintSolver:
    def __init__(
        self,
        bone_pairs: Iterable[Tuple[str, str]],
        min_confidence: float = 0.3,
        history_size: int = 90,
    ) -> None:
        self.bone_pairs = list(bone_pairs)
        self.min_confidence = float(min_confidence)
        self._history: Dict[Tuple[str, str], deque[float]] = defaultdict(lambda: deque(maxlen=history_size))
        self._reference: Dict[Tuple[str, str], float] = {}

    def update_reference(self, joints: List[PoseJointState]) -> None:
        jmap = {j.name: j for j in joints}
        for a, b in self.bone_pairs:
            ja = jmap.get(a)
            jb = jmap.get(b)
            if not ja or not jb:
                continue
            if ja.c < self.min_confidence or jb.c < self.min_confidence:
                continue
            va = np.array([ja.x, ja.y, ja.z], dtype=np.float64)
            vb = np.array([jb.x, jb.y, jb.z], dtype=np.float64)
            dist = float(np.linalg.norm(vb - va))
            if dist <= 1e-6:
                continue
            key = (a, b)
            self._history[key].append(dist)
            self._reference[key] = float(np.median(self._history[key]))

    def solve(self, joints: List[PoseJointState], iterations: int = 2) -> List[PoseJointState]:
        if not joints:
            return joints

        jmap = {j.name: PoseJointState(**j.__dict__) for j in joints}
        if not self._reference:
            return list(jmap.values())

        for _ in range(max(1, int(iterations))):
            for a, b in self.bone_pairs:
                target_len = self._reference.get((a, b))
                if target_len is None:
                    continue
                ja = jmap.get(a)
                jb = jmap.get(b)
                if not ja or not jb:
                    continue
                va = np.array([ja.x, ja.y, ja.z], dtype=np.float64)
                vb = np.array([jb.x, jb.y, jb.z], dtype=np.float64)
                d = vb - va
                n = float(np.linalg.norm(d))
                if n <= 1e-9:
                    continue
                direction = d / n
                vb_new = va + direction * target_len
                jb.x = float(vb_new[0])
                jb.y = float(vb_new[1])
                jb.z = float(vb_new[2])

        return list(jmap.values())
