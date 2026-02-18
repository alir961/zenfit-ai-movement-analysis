from __future__ import annotations

from dataclasses import dataclass
from math import acos, atan2, asin, cos, degrees, pi, sin, sqrt
from typing import Dict, List, Sequence

from .math_types import Quaternion, Vec3
from .skeleton_map import COCO17_NAMES, RAW17_EDGES


# @dataclass
# class Joint:
#     name: str
#     parent: str             # parent link name
#     child: str              # child link name
#     joint_type: str         # "revolute", "prismatic", "ball", "fixed", "free"
#     axis: Vec3              # for revolute/prismatic
#     q_index: Tuple[int, int]  # slice [start, end) in q vector
#     T_parent_to_joint: Mat4  # bind offset
#     T_joint_to_child0: Mat4  # bind offset
@dataclass
class SkeletonJoint:
    name: str
    position: Vec3
    confidence: float
    source_points: List[str]
    is_placeholder: bool = False
    index: int = -1


class GenericSkeleton:
    schema: str = "Raw17SkeletonV2"

    def __init__(
        self,
        joints: List[SkeletonJoint],
        edges: List[Dict[str, int]],
        metadata: Dict[str, object] | None = None,
    ) -> None:
        self.joints = joints
        self.edges = edges
        self.metadata: Dict[str, object] = dict(metadata or {})

    @staticmethod
    def _v_add(a: Vec3, b: Vec3) -> Vec3:
        return Vec3(float(a.x + b.x), float(a.y + b.y), float(a.z + b.z))

    @staticmethod
    def _v_sub(a: Vec3, b: Vec3) -> Vec3:
        return Vec3(float(a.x - b.x), float(a.y - b.y), float(a.z - b.z))

    @staticmethod
    def _v_mul(a: Vec3, s: float) -> Vec3:
        return Vec3(float(a.x * s), float(a.y * s), float(a.z * s))

    @staticmethod
    def _v_dot(a: Vec3, b: Vec3) -> float:
        return float(a.x * b.x + a.y * b.y + a.z * b.z)

    @staticmethod
    def _v_cross(a: Vec3, b: Vec3) -> Vec3:
        return Vec3(
            float(a.y * b.z - a.z * b.y),
            float(a.z * b.x - a.x * b.z),
            float(a.x * b.y - a.y * b.x),
        )

    @staticmethod
    def _v_norm(a: Vec3) -> float:
        return float(sqrt(a.x * a.x + a.y * a.y + a.z * a.z))

    @classmethod
    def _v_unit(cls, a: Vec3, eps: float = 1e-8, fallback: Vec3 | None = None) -> Vec3:
        n = cls._v_norm(a)
        if n <= eps:
            return fallback.copy() if fallback is not None else Vec3(0.0, 0.0, 0.0)
        inv = 1.0 / n
        return cls._v_mul(a, inv)

    @classmethod
    def _quat_from_to(
        cls,
        src: Vec3,
        dst: Vec3,
        eps: float = 1e-8,
        up_axis: Vec3 | None = None,
    ) -> Quaternion:
        a = cls._v_unit(src, eps, Vec3(1.0, 0.0, 0.0))
        b = cls._v_unit(dst, eps, Vec3(1.0, 0.0, 0.0))
        dot = max(-1.0, min(1.0, cls._v_dot(a, b)))
        if dot > 1.0 - eps:
            return Quaternion(0.0, 0.0, 0.0, 1.0)

        cross = cls._v_cross(a, b)
        cross_n = cls._v_norm(cross)
        if cross_n <= eps:
            axis = up_axis.copy() if up_axis is not None else cls._v_cross(a, Vec3(1.0, 0.0, 0.0))
            if cls._v_norm(axis) <= eps:
                axis = cls._v_cross(a, Vec3(0.0, 1.0, 0.0))
            axis = cls._v_unit(axis, eps, Vec3(0.0, 0.0, 1.0))
            return Quaternion.from_axis_angle(axis, pi)

        q = Quaternion(cross.x, cross.y, cross.z, 1.0 + dot)
        return q.normalized()

    @staticmethod
    def _quat_to_euler_deg(q: Quaternion) -> Dict[str, float]:
        qn = q.normalized()
        x, y, z, w = qn.x, qn.y, qn.z, qn.w
        sinr_cosp = 2.0 * (w * x + y * z)
        cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
        roll = atan2(sinr_cosp, cosr_cosp)

        sinp = 2.0 * (w * y - z * x)
        if abs(sinp) >= 1.0:
            pitch = pi / 2.0 if sinp > 0 else -pi / 2.0
        else:
            pitch = asin(sinp)

        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        yaw = atan2(siny_cosp, cosy_cosp)
        return {
            "x": float(degrees(roll)),
            "y": float(degrees(pitch)),
            "z": float(degrees(yaw)),
        }

    @staticmethod
    def _compute_back_center_from_indices(joint_by_idx: Dict[int, SkeletonJoint]) -> Dict[str, object] | None:
        src = [5, 6, 11, 12]
        pts = [joint_by_idx.get(i) for i in src]
        if any(p is None for p in pts):
            return None
        n = float(len(pts))
        cx = sum(float(p.position.x) for p in pts) / n
        cy = sum(float(p.position.y) for p in pts) / n
        cz = sum(float(p.position.z) for p in pts) / n
        return {
            "x": cx,
            "y": cy,
            "z": cz,
            "source_indices": src,
        }

    def _refresh_metadata(self) -> None:
        joint_by_idx = {int(j.index if j.index >= 0 else i): j for i, j in enumerate(self.joints)}
        back_center = self._compute_back_center_from_indices(joint_by_idx)
        if back_center is not None:
            self.metadata["back_center"] = back_center

    @classmethod
    def _copy_with_metadata(cls, skeleton: "GenericSkeleton") -> tuple["GenericSkeleton", Dict[int, SkeletonJoint], float]:
        eps = 1e-8
        joints_copy = [
            SkeletonJoint(
                name=j.name,
                position=j.position.copy(),
                confidence=float(j.confidence),
                source_points=list(j.source_points),
                is_placeholder=bool(j.is_placeholder),
                index=int(j.index),
            )
            for j in skeleton.joints
        ]
        edges_copy = []
        for e in skeleton.edges:
            if not isinstance(e, dict) or "a" not in e or "b" not in e:
                continue
            edges_copy.append({"a": int(e["a"]), "b": int(e["b"])})

        out = cls(joints=joints_copy, edges=edges_copy, metadata=dict(skeleton.metadata))
        out.schema = skeleton.schema
        joint_by_idx: Dict[int, SkeletonJoint] = {}
        for pos_idx, j in enumerate(joints_copy):
            idx = j.index if j.index >= 0 else pos_idx
            joint_by_idx[idx] = j
        return out, joint_by_idx, eps

    def translated(self, delta: Vec3) -> "GenericSkeleton":
        out, _, _ = self._copy_with_metadata(self)
        out.apply_translation(delta)
        return out

    def apply_translation(self, delta: Vec3) -> None:
        for j in self.joints:
            j.position = self._v_add(j.position, delta)
        self._refresh_metadata()

    def rotated_around(self, pivot: Vec3, rotation: Quaternion) -> "GenericSkeleton":
        out, _, _ = self._copy_with_metadata(self)
        out.apply_rotation_around(pivot, rotation)
        return out

    def apply_rotation_around(self, pivot: Vec3, rotation: Quaternion) -> None:
        q = rotation.normalized()
        for j in self.joints:
            rel = self._v_sub(j.position, pivot)
            rot = q.rotate_vector(rel)
            j.position = self._v_add(pivot, rot)
        self._refresh_metadata()

    def recenter_to_back_center(self) -> "GenericSkeleton":
        out, _, _ = self._copy_with_metadata(self)
        out.apply_recenter_to_back_center()
        return out

    def apply_recenter_to_back_center(self) -> None:
        self._refresh_metadata()
        bc = self.metadata.get("back_center")
        if not isinstance(bc, dict):
            return
        center = Vec3(float(bc.get("x", 0.0)), float(bc.get("y", 0.0)), float(bc.get("z", 0.0)))
        self.apply_translation(Vec3(-center.x, -center.y, -center.z))

    def align_backcenter_to_nose_axis(self, target_axis: Vec3, up_axis: Vec3 | None = None) -> "GenericSkeleton":
        out, _, _ = self._copy_with_metadata(self)
        out.apply_align_backcenter_to_nose_axis(target_axis, up_axis)
        return out

    def apply_align_backcenter_to_nose_axis(self, target_axis: Vec3, up_axis: Vec3 | None = None) -> None:
        self._refresh_metadata()
        bc = self.metadata.get("back_center")
        if not isinstance(bc, dict):
            return
        pivot = Vec3(float(bc.get("x", 0.0)), float(bc.get("y", 0.0)), float(bc.get("z", 0.0)))

        joint_by_idx = {int(j.index if j.index >= 0 else i): j for i, j in enumerate(self.joints)}
        nose = joint_by_idx.get(0)
        if nose is None:
            return
        src = self._v_sub(nose.position, pivot)
        if self._v_norm(src) <= 1e-8:
            return
        q = self._quat_from_to(src, target_axis, 1e-8, up_axis)
        self.apply_rotation_around(pivot, q)

    @classmethod
    def with_axis_rotation(
        cls,
        skeleton: "GenericSkeleton",
        axis: Vec3,
        angle_rad: float,
        pivot: Vec3 | None = None,
    ) -> "GenericSkeleton":
        """
        Class method requested: apply a custom axis-angle rotation to a skeleton copy.
        """
        out, _, _ = cls._copy_with_metadata(skeleton)
        out.apply_axis_rotation(axis=axis, angle_rad=angle_rad, pivot=pivot)
        return out

    def apply_axis_rotation(self, axis: Vec3, angle_rad: float, pivot: Vec3 | None = None) -> None:
        q = Quaternion.from_axis_angle(axis, float(angle_rad))
        if pivot is None:
            self._refresh_metadata()
            bc = self.metadata.get("back_center")
            if isinstance(bc, dict):
                pivot = Vec3(float(bc.get("x", 0.0)), float(bc.get("y", 0.0)), float(bc.get("z", 0.0)))
            else:
                pivot = Vec3(0.0, 0.0, 0.0)
        self.apply_rotation_around(pivot, q)

    def edge_quaternion_map(self, reference_axis: Vec3 = Vec3(0.0, 1.0, 0.0)) -> Dict[str, Dict]:
        out: Dict[str, Dict] = {}
        joint_by_idx = {int(j.index if j.index >= 0 else i): j for i, j in enumerate(self.joints)}
        ref = self._v_unit(reference_axis, 1e-8, Vec3(0.0, 1.0, 0.0))
        for e in self.edges:
            a = int(e.get("a", -1))
            b = int(e.get("b", -1))
            key = f"{a}-{b}"
            ja = joint_by_idx.get(a)
            jb = joint_by_idx.get(b)
            if ja is None or jb is None:
                out[key] = {"missing_edge": True}
                continue
            d = self._v_sub(jb.position, ja.position)
            length = self._v_norm(d)
            if length <= 1e-8:
                q = Quaternion(0.0, 0.0, 0.0, 1.0)
                degenerate = True
                du = Vec3(0.0, 0.0, 0.0)
            else:
                du = self._v_mul(d, 1.0 / length)
                q = self._quat_from_to(ref, du)
                degenerate = False
            out[key] = {
                "a": a,
                "b": b,
                "quat": {"x": float(q.x), "y": float(q.y), "z": float(q.z), "w": float(q.w)},
                "euler_deg": self._quat_to_euler_deg(q),
                "direction": {"x": float(du.x), "y": float(du.y), "z": float(du.z)},
                "length": float(length),
                "degenerate": degenerate,
            }
        return out

    @classmethod
    def compare_edge_quaternions(cls, raw: "GenericSkeleton", other: "GenericSkeleton") -> Dict[str, Dict]:
        q_raw = raw.edge_quaternion_map()
        q_other = other.edge_quaternion_map()
        keys = sorted(set(q_raw.keys()) | set(q_other.keys()))
        out: Dict[str, Dict] = {}
        for key in keys:
            a = q_raw.get(key)
            b = q_other.get(key)
            if a is None or b is None or a.get("missing_edge") or b.get("missing_edge"):
                out[key] = {"missing_edge": True}
                continue
            qa = Quaternion.from_iterable([a["quat"]["x"], a["quat"]["y"], a["quat"]["z"], a["quat"]["w"]]).normalized()
            qb = Quaternion.from_iterable([b["quat"]["x"], b["quat"]["y"], b["quat"]["z"], b["quat"]["w"]]).normalized()
            dq = qb * qa.inverse()
            w = max(-1.0, min(1.0, float(abs(dq.normalized().w))))
            angle_deg = float(degrees(2.0 * acos(w)))
            len_a = float(a.get("length", 0.0))
            len_b = float(b.get("length", 0.0))
            out[key] = {
                "angle_diff_deg": angle_deg,
                "length_ratio": (len_b / len_a) if len_a > 1e-8 else None,
                "degenerate": bool(a.get("degenerate") or b.get("degenerate")),
            }
        return out

    @classmethod
    def _max_edge_length(cls, out: "GenericSkeleton", joint_by_idx: Dict[int, SkeletonJoint]) -> float:
        def _vec(a: SkeletonJoint, b: SkeletonJoint) -> tuple[float, float, float]:
            return (b.position.x - a.position.x, b.position.y - a.position.y, b.position.z - a.position.z)

        def _norm(v: tuple[float, float, float]) -> float:
            return sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])

        max_edge = 0.0
        for e in out.edges:
            a_idx = int(e["a"])
            b_idx = int(e["b"])
            ja = joint_by_idx.get(a_idx)
            jb = joint_by_idx.get(b_idx)
            if ja is None or jb is None:
                continue
            cur_len = _norm(_vec(ja, jb))
            if cur_len > max_edge:
                max_edge = cur_len
        return max_edge

    @classmethod
    def easy_normalize_skeleton(cls, skeleton: "GenericSkeleton") -> "GenericSkeleton":
        # Scale only by longest edge, preserving original axes/origin/pose directions.
        out, joint_by_idx, eps = cls._copy_with_metadata(skeleton)
        if not out.joints:
            return out
        max_edge = cls._max_edge_length(out, joint_by_idx)
        if max_edge <= eps:
            back_center = cls._compute_back_center_from_indices(joint_by_idx)
            if back_center is not None:
                out.metadata["back_center"] = back_center
            return out
        inv = 1.0 / max_edge
        for j in out.joints:
            j.position = Vec3(j.position.x * inv, j.position.y * inv, j.position.z * inv)
        back_center = cls._compute_back_center_from_indices(joint_by_idx)
        if back_center is not None:
            out.metadata["back_center"] = back_center
        return out

    @classmethod
    def normalize_skeleton(cls, skeleton: "GenericSkeleton") -> "GenericSkeleton":
        # 1. copy skeleton (cs)
        # 2. adapt the same length each arms joints (shoulder to glove) same for legs. (inside the cs) (respect kinetics)
        # 3. find the longest edge (inside the cs)
        # 4. normalize
        out, joint_by_idx, eps = cls._copy_with_metadata(skeleton)
        if not out.joints:
            return out

        def _vec(a: SkeletonJoint, b: SkeletonJoint) -> tuple[float, float, float]:
            return (b.position.x - a.position.x, b.position.y - a.position.y, b.position.z - a.position.z)

        def _norm(v: tuple[float, float, float]) -> float:
            return sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])

        def _unit(v: tuple[float, float, float], fallback: tuple[float, float, float]) -> tuple[float, float, float]:
            n = _norm(v)
            if n <= eps:
                return fallback
            return (v[0] / n, v[1] / n, v[2] / n)

        def _edge_length(a_idx: int, b_idx: int) -> float:
            ja = joint_by_idx.get(a_idx)
            jb = joint_by_idx.get(b_idx)
            if ja is None or jb is None:
                return 0.0
            return _norm(_vec(ja, jb))

        # Candidate anatomical chains (COCO17 indices).
        arm_chains = {
            "L": (5, 7, 9),
            "R": (6, 8, 10),
        }
        leg_chains = {
            "L": (11, 13, 15),
            "R": (12, 14, 16),
        }

        # Step 2: equalize limb segment lengths in the copy while preserving local directions.
        def _equal_targets(chains: Dict[str, tuple[int, int, int]]) -> tuple[float, float]:
            uppers = []
            lowers = []
            for _, (a, b, c) in chains.items():
                lu = _edge_length(a, b)
                ll = _edge_length(b, c)
                if lu > eps:
                    uppers.append(lu)
                if ll > eps:
                    lowers.append(ll)
            target_upper = max(uppers) if uppers else 0.0
            target_lower = max(lowers) if lowers else 0.0
            return target_upper, target_lower

        arm_target_upper, arm_target_lower = _equal_targets(arm_chains)
        leg_target_upper, leg_target_lower = _equal_targets(leg_chains)

        def _apply_chain(
            a_idx: int,
            b_idx: int,
            c_idx: int,
            target_upper: float,
            target_lower: float,
            fallback_dir: tuple[float, float, float],
        ) -> None:
            if target_upper <= eps and target_lower <= eps:
                return
            ja = joint_by_idx.get(a_idx)
            jb = joint_by_idx.get(b_idx)
            jc = joint_by_idx.get(c_idx)
            if ja is None or jb is None or jc is None:
                return

            d1 = _unit(_vec(ja, jb), fallback_dir)
            jb.position = Vec3(
                ja.position.x + d1[0] * max(target_upper, eps),
                ja.position.y + d1[1] * max(target_upper, eps),
                ja.position.z + d1[2] * max(target_upper, eps),
            )

            d2 = _unit(_vec(jb, jc), d1)
            jc.position = Vec3(
                jb.position.x + d2[0] * max(target_lower, eps),
                jb.position.y + d2[1] * max(target_lower, eps),
                jb.position.z + d2[2] * max(target_lower, eps),
            )

        # Keep chain directions, adjust lengths (kinetics-respecting: same direction, new magnitude).
        _apply_chain(5, 7, 9, arm_target_upper, arm_target_lower, (-1.0, 0.0, 0.0))
        _apply_chain(6, 8, 10, arm_target_upper, arm_target_lower, (1.0, 0.0, 0.0))
        _apply_chain(11, 13, 15, leg_target_upper, leg_target_lower, (0.0, -1.0, 0.0))
        _apply_chain(12, 14, 16, leg_target_upper, leg_target_lower, (0.0, -1.0, 0.0))

        # Step 3: find the longest edge in the adapted copy.
        max_edge = 0.0
        for e in out.edges:
            a_idx = int(e["a"])
            b_idx = int(e["b"])
            if a_idx not in joint_by_idx or b_idx not in joint_by_idx:
                continue
            cur_len = _edge_length(a_idx, b_idx)
            if cur_len > max_edge:
                max_edge = cur_len

        if max_edge <= eps:
            back_center = cls._compute_back_center_from_indices(joint_by_idx)
            if back_center is not None:
                out.metadata["back_center"] = back_center
            return out

        # Step 4: normalize all positions by longest edge.
        inv = 1.0 / max_edge
        for j in out.joints:
            j.position = Vec3(j.position.x * inv, j.position.y * inv, j.position.z * inv)
        back_center = cls._compute_back_center_from_indices(joint_by_idx)
        if back_center is not None:
            out.metadata["back_center"] = back_center
        return out
    
    @classmethod
    def from_coco17_points(cls, points: Sequence[Sequence[float]]) -> "GenericSkeleton":
        joints: List[SkeletonJoint] = []
        for i, name in enumerate(COCO17_NAMES):
            p = points[i] if i < len(points) else (0.0, 0.0, 0.0, 0.0)
            x = float(p[0]) if len(p) > 0 else 0.0
            y = float(p[1]) if len(p) > 1 else 0.0
            z = float(p[2]) if len(p) > 2 else 0.0
            c = float(p[3]) if len(p) > 3 else 0.0
            joints.append(
                SkeletonJoint(
                    name=name,
                    position=Vec3(x, y, z),
                    confidence=c,
                    source_points=[name],
                    is_placeholder=False,
                    index=i,
                )
            )
        edges = [{"a": int(a), "b": int(b)} for a, b in RAW17_EDGES]
        joint_by_idx = {int(j.index): j for j in joints}
        metadata: Dict[str, object] = {}
        back_center = cls._compute_back_center_from_indices(joint_by_idx)
        if back_center is not None:
            metadata["back_center"] = back_center
        return cls(joints=joints, edges=edges, metadata=metadata)

    def to_payload(self) -> Dict[str, object]:
        return {
            "schema": self.schema,
            "joints": [
                {
                    "index": int(j.index),
                    "name": j.name,
                    "x": float(j.position.x),
                    "y": float(j.position.y),
                    "z": float(j.position.z),
                    "confidence": float(j.confidence),
                    "is_placeholder": bool(j.is_placeholder),
                    "source_points": list(j.source_points),
                }
                for j in self.joints
            ],
            "edges": self.edges,
            "metadata": self.metadata,
        }
