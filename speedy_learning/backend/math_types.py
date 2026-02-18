from __future__ import annotations

from dataclasses import dataclass, field
from numbers import Real
from typing import Iterable

import numpy as np


def _coerce_array(values: Iterable[float], size: int, name: str) -> np.ndarray:
    arr = np.asarray(list(values), dtype=np.float32)
    if arr.size < size:
        raise ValueError(f"{name} requires at least {size} values")
    return arr[:size]


@dataclass
class Vec2:
    x: float = 0.0
    y: float = 0.0

    __array_priority__ = 1000

    def to_np(self) -> np.ndarray:
        return np.array([self.x, self.y], dtype=np.float32)

    def __array__(self, dtype=None) -> np.ndarray:
        return np.asarray(self.to_np(), dtype=dtype)

    def __iter__(self):
        yield self.x
        yield self.y

    def __len__(self) -> int:
        return 2

    def __getitem__(self, idx: int) -> float:
        return (self.x, self.y)[idx]

    def copy(self) -> "Vec2":
        return Vec2(self.x, self.y)

    @staticmethod
    def _coerce_operand(other: object):
        if isinstance(other, Vec2):
            return other.x, other.y
        if isinstance(other, Real):
            value = float(other)
            return value, value
        if isinstance(other, Iterable):
            arr = _coerce_array(other, 2, "Vec2 operand")
            return float(arr[0]), float(arr[1])
        return NotImplemented

    def __add__(self, other: object):
        v = self._coerce_operand(other)
        if v is NotImplemented:
            return NotImplemented
        return Vec2(self.x + v[0], self.y + v[1])

    def __radd__(self, other: object):
        return self.__add__(other)

    def __sub__(self, other: object):
        v = self._coerce_operand(other)
        if v is NotImplemented:
            return NotImplemented
        return Vec2(self.x - v[0], self.y - v[1])

    def __rsub__(self, other: object):
        v = self._coerce_operand(other)
        if v is NotImplemented:
            return NotImplemented
        return Vec2(v[0] - self.x, v[1] - self.y)

    def __mul__(self, other: object):
        v = self._coerce_operand(other)
        if v is NotImplemented:
            return NotImplemented
        return Vec2(self.x * v[0], self.y * v[1])

    def __rmul__(self, other: object):
        return self.__mul__(other)

    def __truediv__(self, other: object):
        v = self._coerce_operand(other)
        if v is NotImplemented:
            return NotImplemented
        if abs(v[0]) < 1e-8 or abs(v[1]) < 1e-8:
            raise ZeroDivisionError("division by zero")
        return Vec2(self.x / v[0], self.y / v[1])

    def __neg__(self):
        return Vec2(-self.x, -self.y)

    def dot(self, other: "Vec2") -> float:
        return float(np.dot(self.to_np(), other.to_np()))

    def norm(self) -> float:
        return float(np.linalg.norm(self.to_np()))

    def normalized(self) -> "Vec2":
        n = self.norm()
        if n < 1e-8:
            return Vec2()
        return self / n

    def distance_to(self, other: "Vec2") -> float:
        return (self - other).norm()

    def almost_equal(self, other: "Vec2", atol: float = 1e-6) -> bool:
        return bool(np.allclose(self.to_np(), other.to_np(), atol=atol))

    @classmethod
    def from_iterable(cls, values: Iterable[float]) -> "Vec2":
        v = _coerce_array(values, 2, "Vec2")
        return cls(float(v[0]), float(v[1]))


@dataclass
class Vec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    __array_priority__ = 1000

    def to_np(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z], dtype=np.float32)

    def __array__(self, dtype=None) -> np.ndarray:
        return np.asarray(self.to_np(), dtype=dtype)

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z

    def __len__(self) -> int:
        return 3

    def __getitem__(self, idx: int) -> float:
        return (self.x, self.y, self.z)[idx]

    def copy(self) -> "Vec3":
        return Vec3(self.x, self.y, self.z)

    @staticmethod
    def _coerce_operand(other: object):
        if isinstance(other, Vec3):
            return other.x, other.y, other.z
        if isinstance(other, Real):
            value = float(other)
            return value, value, value
        if isinstance(other, Iterable):
            arr = _coerce_array(other, 3, "Vec3 operand")
            return float(arr[0]), float(arr[1]), float(arr[2])
        return NotImplemented

    def __add__(self, other: object):
        v = self._coerce_operand(other)
        if v is NotImplemented:
            return NotImplemented
        return Vec3(self.x + v[0], self.y + v[1], self.z + v[2])

    def __radd__(self, other: object):
        return self.__add__(other)

    def __sub__(self, other: object):
        v = self._coerce_operand(other)
        if v is NotImplemented:
            return NotImplemented
        return Vec3(self.x - v[0], self.y - v[1], self.z - v[2])

    def __rsub__(self, other: object):
        v = self._coerce_operand(other)
        if v is NotImplemented:
            return NotImplemented
        return Vec3(v[0] - self.x, v[1] - self.y, v[2] - self.z)

    def __mul__(self, other: object):
        v = self._coerce_operand(other)
        if v is NotImplemented:
            return NotImplemented
        return Vec3(self.x * v[0], self.y * v[1], self.z * v[2])

    def __rmul__(self, other: object):
        return self.__mul__(other)

    def __truediv__(self, other: object):
        v = self._coerce_operand(other)
        if v is NotImplemented:
            return NotImplemented
        if abs(v[0]) < 1e-8 or abs(v[1]) < 1e-8 or abs(v[2]) < 1e-8:
            raise ZeroDivisionError("division by zero")
        return Vec3(self.x / v[0], self.y / v[1], self.z / v[2])

    def __neg__(self):
        return Vec3(-self.x, -self.y, -self.z)

    def dot(self, other: "Vec3") -> float:
        return float(np.dot(self.to_np(), other.to_np()))

    def cross(self, other: "Vec3") -> "Vec3":
        c = np.cross(self.to_np(), other.to_np())
        return Vec3(float(c[0]), float(c[1]), float(c[2]))

    def norm(self) -> float:
        return float(np.linalg.norm(self.to_np()))

    def normalized(self) -> "Vec3":
        n = self.norm()
        if n < 1e-8:
            return Vec3()
        return self / n

    def distance_to(self, other: "Vec3") -> float:
        return (self - other).norm()

    def almost_equal(self, other: "Vec3", atol: float = 1e-6) -> bool:
        return bool(np.allclose(self.to_np(), other.to_np(), atol=atol))

    @classmethod
    def from_iterable(cls, values: Iterable[float]) -> "Vec3":
        v = _coerce_array(values, 3, "Vec3")
        return cls(float(v[0]), float(v[1]), float(v[2]))


@dataclass
class Quaternion:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0

    __array_priority__ = 1000

    def to_np(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z, self.w], dtype=np.float32)

    def __array__(self, dtype=None) -> np.ndarray:
        return np.asarray(self.to_np(), dtype=dtype)

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z
        yield self.w

    def __len__(self) -> int:
        return 4

    def __getitem__(self, idx: int) -> float:
        return (self.x, self.y, self.z, self.w)[idx]

    @staticmethod
    def _coerce_operand(other: object):
        if isinstance(other, Quaternion):
            return other.x, other.y, other.z, other.w
        if isinstance(other, Real):
            value = float(other)
            return value, value, value, value
        if isinstance(other, Iterable):
            arr = _coerce_array(other, 4, "Quaternion operand")
            return float(arr[0]), float(arr[1]), float(arr[2]), float(arr[3])
        return NotImplemented

    def __add__(self, other: object):
        v = self._coerce_operand(other)
        if v is NotImplemented:
            return NotImplemented
        return Quaternion(self.x + v[0], self.y + v[1], self.z + v[2], self.w + v[3])

    def __sub__(self, other: object):
        v = self._coerce_operand(other)
        if v is NotImplemented:
            return NotImplemented
        return Quaternion(self.x - v[0], self.y - v[1], self.z - v[2], self.w - v[3])

    def __mul__(self, other: object):
        if isinstance(other, Real):
            s = float(other)
            return Quaternion(self.x * s, self.y * s, self.z * s, self.w * s)
        if isinstance(other, Quaternion):
            x1, y1, z1, w1 = self.x, self.y, self.z, self.w
            x2, y2, z2, w2 = other.x, other.y, other.z, other.w
            return Quaternion(
                w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
                w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            )
        return NotImplemented

    def __rmul__(self, other: object):
        if isinstance(other, Real):
            return self * other
        return NotImplemented

    def __truediv__(self, other: object):
        if not isinstance(other, Real):
            return NotImplemented
        if abs(float(other)) < 1e-8:
            raise ZeroDivisionError("division by zero")
        s = float(other)
        return Quaternion(self.x / s, self.y / s, self.z / s, self.w / s)

    def __neg__(self):
        return Quaternion(-self.x, -self.y, -self.z, -self.w)

    def norm(self) -> float:
        return float(np.linalg.norm(self.to_np()))

    def normalized(self) -> "Quaternion":
        n = self.norm()
        if n < 1e-8:
            return Quaternion()
        return self / n

    def conjugate(self) -> "Quaternion":
        return Quaternion(-self.x, -self.y, -self.z, self.w)

    def inverse(self) -> "Quaternion":
        n2 = self.norm() ** 2
        if n2 < 1e-8:
            return Quaternion()
        return self.conjugate() / n2

    def rotate_vector(self, vec: Vec3) -> Vec3:
        q = self.normalized()
        p = Quaternion(vec.x, vec.y, vec.z, 0.0)
        r = q * p * q.conjugate()
        return Vec3(r.x, r.y, r.z)

    @classmethod
    def from_axis_angle(cls, axis: Vec3, angle_rad: float) -> "Quaternion":
        a = axis.normalized()
        s = float(np.sin(angle_rad * 0.5))
        c = float(np.cos(angle_rad * 0.5))
        return cls(a.x * s, a.y * s, a.z * s, c).normalized()

    @classmethod
    def from_iterable(cls, values: Iterable[float]) -> "Quaternion":
        v = _coerce_array(values, 4, "Quaternion")
        return cls(float(v[0]), float(v[1]), float(v[2]), float(v[3]))


@dataclass
class Mat4:
    value: np.ndarray = field(default_factory=lambda: np.eye(4, dtype=np.float32))

    __array_priority__ = 1000

    def __post_init__(self) -> None:
        arr = np.asarray(self.value, dtype=np.float32)
        if arr.shape != (4, 4):
            raise ValueError("Mat4 must be shape (4,4)")
        self.value = arr

    def to_np(self) -> np.ndarray:
        return self.value

    def __array__(self, dtype=None) -> np.ndarray:
        return np.asarray(self.value, dtype=dtype)

    def __getitem__(self, idx):
        return self.value[idx]

    def __setitem__(self, idx, val) -> None:
        self.value[idx] = val

    def copy(self) -> "Mat4":
        return Mat4(self.value.copy())

    def __mul__(self, other: object):
        if isinstance(other, Real):
            return Mat4(self.value * float(other))
        if isinstance(other, Mat4):
            return Mat4(self.value * other.value)
        return NotImplemented

    def __rmul__(self, other: object):
        if isinstance(other, Real):
            return self * other
        return NotImplemented

    def __add__(self, other: object):
        if not isinstance(other, Mat4):
            return NotImplemented
        return Mat4(self.value + other.value)

    def __sub__(self, other: object):
        if not isinstance(other, Mat4):
            return NotImplemented
        return Mat4(self.value - other.value)

    def __matmul__(self, other: object):
        if isinstance(other, Mat4):
            return Mat4(self.value @ other.value)
        if isinstance(other, Vec3):
            v = np.array([other.x, other.y, other.z, 1.0], dtype=np.float32)
            out = self.value @ v
            w = out[3] if abs(float(out[3])) > 1e-8 else 1.0
            return Vec3(float(out[0] / w), float(out[1] / w), float(out[2] / w))
        if isinstance(other, np.ndarray):
            return self.value @ other
        return NotImplemented

    @property
    def T(self) -> "Mat4":
        return Mat4(self.value.T)

    def transposed(self) -> "Mat4":
        return self.T

    def determinant(self) -> float:
        return float(np.linalg.det(self.value))

    def inverse(self) -> "Mat4":
        return Mat4(np.linalg.inv(self.value).astype(np.float32))

    def almost_equal(self, other: "Mat4", atol: float = 1e-6) -> bool:
        return bool(np.allclose(self.value, other.value, atol=atol))

    @classmethod
    def identity(cls) -> "Mat4":
        return cls(np.eye(4, dtype=np.float32))

    @classmethod
    def from_translation(cls, t: Vec3) -> "Mat4":
        m = np.eye(4, dtype=np.float32)
        m[:3, 3] = t.to_np()
        return cls(m)

    @classmethod
    def from_scale(cls, s: Vec3) -> "Mat4":
        m = np.eye(4, dtype=np.float32)
        m[0, 0], m[1, 1], m[2, 2] = s.x, s.y, s.z
        return cls(m)

    @classmethod
    def from_iterable(cls, values: Iterable[Iterable[float]]) -> "Mat4":
        return cls(np.array(list(values), dtype=np.float32))

def hat(w: Vec3) -> np.ndarray:
    wx, wy, wz = w
    return np.array([[0, -wz,  wy],
                     [wz,  0, -wx],
                     [-wy, wx, 0]], dtype=float)

def rot_axis_angle(axis: Vec3, angle: float) -> Mat3:
    axis = axis / (np.linalg.norm(axis) + 1e-12)
    K = hat(axis)
    I = np.eye(3)
    return I + np.sin(angle) * K + (1 - np.cos(angle)) * (K @ K)

def make_T(R: Mat3, p: Vec3) -> Mat4:
    T = np.eye(4)
    T[:3, :3] = R
    T[:3,  3] = p
    return T

def joint_transform(j: Joint, q: np.ndarray) -> Mat4:
    qs, qe = j.q_index
    qj = q[qs:qe]

    if j.joint_type == "fixed":
        return np.eye(4)

    if j.joint_type == "revolute":
        angle = float(qj[0])
        R = rot_axis_angle(j.axis, angle)
        return make_T(R, np.zeros(3))

    if j.joint_type == "prismatic":
        dist = float(qj[0])
        p = j.axis / (np.linalg.norm(j.axis) + 1e-12) * dist
        return make_T(np.eye(3), p)

    # "ball"/"free" omitted here (would use quaternion / 6DoF)
    raise NotImplementedError(j.joint_type)

def forward_kinematics(skel: Skeleton, q: np.ndarray, T_world_root: Mat4) -> Dict[str, Mat4]:
    Tw = {skel.root: T_world_root}
    for parent in skel.topo_order():
        T_parent = Tw[parent]
        for j in skel.children[parent]:
            Tpj = j.T_parent_to_joint
            Tjc = joint_transform(j, q)
            Tc0 = j.T_joint_to_child0
            Tw[j.child] = T_parent @ Tpj @ Tjc @ Tc0
    return Tw