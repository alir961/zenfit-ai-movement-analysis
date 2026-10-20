from __future__ import annotations

import math
from typing import Dict, Iterable, List, Tuple

import numpy as np

from labs.types import PoseJointState


def normalize_quat(q: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(q))
    if n <= 1e-12:
        return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
    return q / n


def quat_from_two_vectors(v0: np.ndarray, v1: np.ndarray) -> np.ndarray:
    a = v0.astype(np.float64)
    b = v1.astype(np.float64)
    a /= max(1e-12, float(np.linalg.norm(a)))
    b /= max(1e-12, float(np.linalg.norm(b)))
    dot = float(np.clip(np.dot(a, b), -1.0, 1.0))
    if dot > 0.999999:
        return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
    if dot < -0.999999:
        axis = np.cross(np.array([1.0, 0.0, 0.0]), a)
        if np.linalg.norm(axis) < 1e-6:
            axis = np.cross(np.array([0.0, 1.0, 0.0]), a)
        axis = axis / max(1e-12, float(np.linalg.norm(axis)))
        return np.array([0.0, axis[0], axis[1], axis[2]], dtype=np.float64)
    axis = np.cross(a, b)
    w = math.sqrt((1.0 + dot) * 2.0) * 0.5
    xyz = axis / max(1e-12, 2.0 * w)
    return normalize_quat(np.array([w, xyz[0], xyz[1], xyz[2]], dtype=np.float64))


def slerp(q0: np.ndarray, q1: np.ndarray, t: float) -> np.ndarray:
    t = float(np.clip(t, 0.0, 1.0))
    qa = normalize_quat(q0)
    qb = normalize_quat(q1)
    dot = float(np.dot(qa, qb))
    if dot < 0.0:
        qb = -qb
        dot = -dot
    if dot > 0.9995:
        out = qa + t * (qb - qa)
        return normalize_quat(out)
    theta_0 = math.acos(np.clip(dot, -1.0, 1.0))
    theta = theta_0 * t
    q2 = normalize_quat(qb - qa * dot)
    return normalize_quat(qa * math.cos(theta) + q2 * math.sin(theta))


class KinematicsModel:
    def __init__(
        self,
        bone_pairs: Iterable[Tuple[str, str]],
        canonical_lock: bool = True,
        lock_alpha: float = 0.22,
    ) -> None:
        self.bone_pairs = list(bone_pairs)
        self._rest_dirs: Dict[Tuple[str, str], np.ndarray] = {}
        self._last_quats: Dict[str, np.ndarray] = {}
        self.canonical_lock = bool(canonical_lock)
        self.lock_alpha = float(np.clip(lock_alpha, 0.01, 0.95))
        self._last_rot: np.ndarray | None = None
        self.last_canonical_yaw_deg: float = 0.0

    @staticmethod
    def _normalize_vec(v: np.ndarray, fallback: np.ndarray) -> np.ndarray:
        n = float(np.linalg.norm(v))
        if n <= 1e-9:
            return fallback.astype(np.float64)
        return v.astype(np.float64) / n

    @staticmethod
    def _orthonormalize(ex: np.ndarray, ey: np.ndarray) -> np.ndarray:
        x = KinematicsModel._normalize_vec(ex, np.array([1.0, 0.0, 0.0], dtype=np.float64))
        y = ey - np.dot(ey, x) * x
        y = KinematicsModel._normalize_vec(y, np.array([0.0, 1.0, 0.0], dtype=np.float64))
        z = np.cross(x, y)
        z = KinematicsModel._normalize_vec(z, np.array([0.0, 0.0, 1.0], dtype=np.float64))
        y = np.cross(z, x)
        y = KinematicsModel._normalize_vec(y, np.array([0.0, 1.0, 0.0], dtype=np.float64))
        return np.stack([x, y, z], axis=1)

    def _blend_rot(self, prev_rot: np.ndarray, curr_rot: np.ndarray, alpha: float) -> np.ndarray:
        alpha = float(np.clip(alpha, 0.01, 0.99))
        blend = (1.0 - alpha) * prev_rot + alpha * curr_rot
        return self._orthonormalize(blend[:, 0], blend[:, 1])

    def _vector(self, jmap: Dict[str, PoseJointState], a: str, b: str) -> np.ndarray | None:
        ja = jmap.get(a)
        jb = jmap.get(b)
        if not ja or not jb:
            return None
        return np.array([jb.x - ja.x, jb.y - ja.y, jb.z - ja.z], dtype=np.float64)

    def compute_pelvis_frame(self, joints: List[PoseJointState]) -> tuple[np.ndarray, np.ndarray, float]:
        jmap = {j.name: j for j in joints}
        lhip = jmap.get("left_hip")
        rhip = jmap.get("right_hip")
        lsho = jmap.get("left_shoulder")
        rsho = jmap.get("right_shoulder")
        if not lhip or not rhip:
            center = np.zeros((3,), dtype=np.float64)
            rot = np.eye(3, dtype=np.float64)
            self.last_canonical_yaw_deg = 0.0
            return center, rot, self.last_canonical_yaw_deg

        hip_center = np.array(
            [(lhip.x + rhip.x) * 0.5, (lhip.y + rhip.y) * 0.5, (lhip.z + rhip.z) * 0.5],
            dtype=np.float64,
        )

        ex_candidates: List[np.ndarray] = [
            np.array([rhip.x - lhip.x, rhip.y - lhip.y, rhip.z - lhip.z], dtype=np.float64)
        ]
        if lsho and rsho:
            ex_candidates.append(np.array([rsho.x - lsho.x, rsho.y - lsho.y, rsho.z - lsho.z], dtype=np.float64))
        ex = np.zeros((3,), dtype=np.float64)
        for cand in ex_candidates:
            n = float(np.linalg.norm(cand))
            if n > 1e-9:
                ex += cand / n
        ex = self._normalize_vec(ex, np.array([1.0, 0.0, 0.0], dtype=np.float64))

        if lsho and rsho:
            shoulder_center = np.array(
                [(lsho.x + rsho.x) * 0.5, (lsho.y + rsho.y) * 0.5, (lsho.z + rsho.z) * 0.5],
                dtype=np.float64,
            )
            ey_seed = shoulder_center - hip_center
        elif jmap.get("nose") is not None:
            n = jmap["nose"]
            ey_seed = np.array([n.x, n.y, n.z], dtype=np.float64) - hip_center
        else:
            ey_seed = np.array([0.0, -1.0, 0.0], dtype=np.float64)

        rot = self._orthonormalize(ex, ey_seed)
        ex = rot[:, 0]
        ey = rot[:, 1]
        ez = rot[:, 2]

        # Keep subject orientation stable in canonical space using face direction when available.
        nose = jmap.get("nose")
        if nose is not None:
            face_vec = np.array([nose.x, nose.y, nose.z], dtype=np.float64) - hip_center
            if float(np.dot(face_vec, ez)) < 0.0:
                ex = -ex
                ez = -ez
                rot = np.stack([ex, ey, ez], axis=1)

        if self._last_rot is not None and float(np.dot(ex, self._last_rot[:, 0])) < 0.0:
            ex = -ex
            ez = -ez
            rot = np.stack([ex, ey, ez], axis=1)

        if self.canonical_lock and self._last_rot is not None:
            rot = self._blend_rot(self._last_rot, rot, self.lock_alpha)

        self._last_rot = rot
        yaw_deg = float(np.degrees(np.arctan2(rot[2, 0], rot[0, 0])))
        self.last_canonical_yaw_deg = yaw_deg
        return hip_center, rot, yaw_deg

    def normalize_pose(self, joints: List[PoseJointState]) -> List[PoseJointState]:
        if not joints:
            return []
        center, rot, _ = self.compute_pelvis_frame(joints)
        jmap = {j.name: j for j in joints}
        lhip = jmap.get("left_hip")
        rhip = jmap.get("right_hip")
        lsho = jmap.get("left_shoulder")
        rsho = jmap.get("right_shoulder")

        scale = 1.0
        if lhip and rhip and lsho and rsho:
            hip_mid = np.array([(lhip.x + rhip.x) * 0.5, (lhip.y + rhip.y) * 0.5, (lhip.z + rhip.z) * 0.5])
            sho_mid = np.array([(lsho.x + rsho.x) * 0.5, (lsho.y + rsho.y) * 0.5, (lsho.z + rsho.z) * 0.5])
            torso = float(np.linalg.norm(sho_mid - hip_mid))
            shoulder_w = float(np.linalg.norm(np.array([rsho.x - lsho.x, rsho.y - lsho.y, rsho.z - lsho.z])))
            hip_w = float(np.linalg.norm(np.array([rhip.x - lhip.x, rhip.y - lhip.y, rhip.z - lhip.z])))
            scale_candidates = []
            if torso > 1e-6:
                scale_candidates.append(torso)
            if shoulder_w > 1e-6:
                scale_candidates.append(0.9 * shoulder_w)
            if hip_w > 1e-6:
                scale_candidates.append(1.1 * hip_w)
            if scale_candidates:
                scale = float(np.median(np.array(scale_candidates, dtype=np.float64)))
        else:
            pts = np.array([[j.x, j.y, j.z] for j in joints], dtype=np.float64)
            spread = float(np.median(np.linalg.norm(pts - center.reshape(1, 3), axis=1)))
            if spread > 1e-6:
                scale = spread

        out: List[PoseJointState] = []
        for j in joints:
            v = np.array([j.x, j.y, j.z], dtype=np.float64)
            n = (v - center) / max(1e-9, scale)
            # Normalize into pelvis local frame for stable orientation.
            n = rot.T @ n
            n = np.clip(n, -4.0, 4.0)
            out.append(
                PoseJointState(
                    name=j.name,
                    x=float(n[0]),
                    y=float(n[1]),
                    z=float(n[2]),
                    c=j.c,
                    px=j.px,
                    py=j.py,
                )
            )
        return out

    def compute_local_quaternions(self, joints: List[PoseJointState]) -> Dict[str, Tuple[float, float, float, float]]:
        jmap = {j.name: j for j in joints}
        out: Dict[str, Tuple[float, float, float, float]] = {}

        for parent, child in self.bone_pairs:
            vec = self._vector(jmap, parent, child)
            if vec is None:
                continue
            name = f"{parent}->{child}"
            n = float(np.linalg.norm(vec))
            if n <= 1e-9:
                continue
            curr = vec / n
            if (parent, child) not in self._rest_dirs:
                self._rest_dirs[(parent, child)] = curr
            rest = self._rest_dirs[(parent, child)]
            quat = quat_from_two_vectors(rest, curr)
            prev = self._last_quats.get(name)
            if prev is not None and float(np.dot(prev, quat)) < 0.0:
                quat = -quat
            self._last_quats[name] = quat
            out[name] = (float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3]))

        return out
