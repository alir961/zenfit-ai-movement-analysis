from __future__ import annotations

import math
from copy import deepcopy
from typing import Dict, Iterable, List, Tuple

import numpy as np


def _vec(j: Dict) -> np.ndarray:
    return np.array([float(j["x"]), float(j["y"]), float(j["z"])], dtype=np.float32)


def _distance(a: Dict, b: Dict) -> float:
    return float(np.linalg.norm(_vec(a) - _vec(b)))


def _safe_unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n < 1e-8:
        return np.array([0.0, 0.0, 0.0], dtype=np.float32)
    return v / n


def _joint_map(joints: Iterable[Dict]) -> Dict[str, Dict]:
    return {j["name"]: j for j in joints}


def _chain_length(by_name: Dict[str, Dict], chain: List[str]) -> float:
    total = 0.0
    for a, b in zip(chain, chain[1:]):
        if a in by_name and b in by_name:
            total += _distance(by_name[a], by_name[b])
    return total


def _extract_lengths(by_name: Dict[str, Dict]) -> Dict[str, float]:
    def d(a: str, b: str) -> float:
        if a not in by_name or b not in by_name:
            return 0.0
        return _distance(by_name[a], by_name[b])

    return {
        "left_arm_upper": d("L_Shoulder", "L_Elbow"),
        "left_arm_lower": d("L_Elbow", "L_Wrist"),
        "right_arm_upper": d("R_Shoulder", "R_Elbow"),
        "right_arm_lower": d("R_Elbow", "R_Wrist"),
        "left_leg_upper": d("L_Hip", "L_Knee"),
        "left_leg_lower": d("L_Knee", "L_Ankle"),
        "right_leg_upper": d("R_Hip", "R_Knee"),
        "right_leg_lower": d("R_Knee", "R_Ankle"),
    }


def _rescale_chain(by_name: Dict[str, Dict], chain: Tuple[str, str, str], target_a: float, target_b: float) -> None:
    root_name, mid_name, end_name = chain
    if root_name not in by_name or mid_name not in by_name or end_name not in by_name:
        return

    root = _vec(by_name[root_name])
    mid = _vec(by_name[mid_name])
    end = _vec(by_name[end_name])

    dir_a = _safe_unit(mid - root)
    dir_b = _safe_unit(end - mid)

    if float(np.linalg.norm(dir_a)) < 1e-8:
        dir_a = np.array([0.0, -1.0, 0.0], dtype=np.float32)
    if float(np.linalg.norm(dir_b)) < 1e-8:
        dir_b = dir_a

    new_mid = root + dir_a * max(target_a, 1e-6)
    new_end = new_mid + dir_b * max(target_b, 1e-6)

    by_name[mid_name]["x"], by_name[mid_name]["y"], by_name[mid_name]["z"] = map(float, new_mid)
    by_name[end_name]["x"], by_name[end_name]["y"], by_name[end_name]["z"] = map(float, new_end)


def regularize_proportions(joints: List[Dict]) -> Dict:
    out_joints = deepcopy(joints)
    by_name = _joint_map(out_joints)

    pre = _extract_lengths(by_name)

    def dominant_target(prefix: str) -> Tuple[float, float]:
        l1 = pre[f"left_{prefix}_upper"]
        l2 = pre[f"left_{prefix}_lower"]
        r1 = pre[f"right_{prefix}_upper"]
        r2 = pre[f"right_{prefix}_lower"]

        total_l = l1 + l2
        total_r = r1 + r2
        if total_l < 1e-6 and total_r < 1e-6:
            return 0.0, 0.0

        if total_l >= total_r:
            base_1, base_2, base_total = l1, l2, total_l
            target_total = total_l
        else:
            base_1, base_2, base_total = r1, r2, total_r
            target_total = total_r

        ratio = 0.5 if base_total < 1e-6 else float(np.clip(base_1 / base_total, 0.25, 0.75))
        return target_total * ratio, target_total * (1.0 - ratio)

    arm_target_a, arm_target_b = dominant_target("arm")
    leg_target_a, leg_target_b = dominant_target("leg")

    _rescale_chain(by_name, ("L_Shoulder", "L_Elbow", "L_Wrist"), arm_target_a, arm_target_b)
    _rescale_chain(by_name, ("R_Shoulder", "R_Elbow", "R_Wrist"), arm_target_a, arm_target_b)
    _rescale_chain(by_name, ("L_Hip", "L_Knee", "L_Ankle"), leg_target_a, leg_target_b)
    _rescale_chain(by_name, ("R_Hip", "R_Knee", "R_Ankle"), leg_target_a, leg_target_b)

    post = _extract_lengths(by_name)

    return {
        "joints": list(by_name.values()),
        "pre": pre,
        "post": post,
        "targets": {
            "arm_upper": arm_target_a,
            "arm_lower": arm_target_b,
            "leg_upper": leg_target_a,
            "leg_lower": leg_target_b,
        },
    }


def _angle_deg(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    v1 = _safe_unit(a - b)
    v2 = _safe_unit(c - b)
    dot = float(np.clip(np.dot(v1, v2), -1.0, 1.0))
    return math.degrees(math.acos(dot))


def compute_joint_angles(joints_by_name: Dict[str, Dict]) -> Dict[str, float]:
    triples = {
        "left_elbow": ("L_Shoulder", "L_Elbow", "L_Wrist"),
        "right_elbow": ("R_Shoulder", "R_Elbow", "R_Wrist"),
        "left_knee": ("L_Hip", "L_Knee", "L_Ankle"),
        "right_knee": ("R_Hip", "R_Knee", "R_Ankle"),
        "spine": ("Pelvis", "Spine", "Chest"),
    }
    out: Dict[str, float] = {}
    for key, (a, b, c) in triples.items():
        if a in joints_by_name and b in joints_by_name and c in joints_by_name:
            out[key] = _angle_deg(_vec(joints_by_name[a]), _vec(joints_by_name[b]), _vec(joints_by_name[c]))
    return out


def _orientation_features(joints_by_name: Dict[str, Dict]) -> Dict:
    pelvis = _vec(joints_by_name.get("Pelvis", {"x": 0.0, "y": 0.0, "z": 0.0}))
    chest = _vec(joints_by_name.get("Chest", {"x": 0.0, "y": 1.0, "z": 0.0}))
    l_sh = _vec(joints_by_name.get("L_Shoulder", {"x": -0.5, "y": 1.0, "z": 0.0}))
    r_sh = _vec(joints_by_name.get("R_Shoulder", {"x": 0.5, "y": 1.0, "z": 0.0}))

    up = _safe_unit(chest - pelvis)
    shoulder_axis = _safe_unit(r_sh - l_sh)
    forward = _safe_unit(np.cross(shoulder_axis, up))
    if float(np.linalg.norm(forward)) < 1e-6:
        forward = np.array([0.0, 0.0, 1.0], dtype=np.float32)

    forward_xz = _safe_unit(np.array([forward[0], 0.0, forward[2]], dtype=np.float32))
    yaw_deg = math.degrees(math.atan2(float(forward_xz[0]), float(forward_xz[2])))

    surface_ref = _safe_unit(np.array([1.0, 0.0, 1.0], dtype=np.float32))
    surface_alignment = float(np.dot(forward_xz, surface_ref))

    return {
        "forward": forward.tolist(),
        "up": up.tolist(),
        "surface_ref": surface_ref.tolist(),
        "surface_alignment": surface_alignment,
        "yaw_deg": yaw_deg,
    }


def normalize_pose(joints: List[Dict], upper_anchor_name: str, scale: float) -> List[Dict]:
    by_name = _joint_map(joints)
    upper = by_name.get(upper_anchor_name) or by_name.get("Chest") or by_name.get("Pelvis")
    upper_vec = _vec(upper) if upper else np.zeros(3, dtype=np.float32)

    denom = max(float(scale), 1e-6)
    out: List[Dict] = []
    for joint in joints:
        p = (_vec(joint) - upper_vec) / denom
        out.append(
            {
                **joint,
                "x": float(p[0]),
                "y": float(p[1]),
                "z": float(p[2]),
            }
        )
    return out


def process_pose(raw17_joints: List[Dict], mapped_humanoid: Dict) -> Dict:
    mapped_joints = deepcopy(mapped_humanoid["joints"])
    mapped_by_name = _joint_map(mapped_joints)

    ik_chains = [
        ["L_Ankle", "L_Knee", "L_Hip", "Pelvis", "Spine", "Chest", "Neck", "Head"],
        ["R_Ankle", "R_Knee", "R_Hip", "Pelvis", "Spine", "Chest", "Neck", "Head"],
    ]
    chain_lengths = [_chain_length(mapped_by_name, chain) for chain in ik_chains]
    ik_max_length = max(max(chain_lengths), 1e-6)

    regularized = regularize_proportions(mapped_joints)
    reg_joints = regularized["joints"]
    reg_by_name = _joint_map(reg_joints)

    upper_name = "Upper" if "Upper" in reg_by_name else "Chest"
    normalized_mapped = normalize_pose(reg_joints, upper_name, ik_max_length)
    normalized_raw17 = normalize_pose(raw17_joints, "nose", ik_max_length)

    orientation = _orientation_features(reg_by_name)
    angles = compute_joint_angles(reg_by_name)

    feature_vector = []
    for j in normalized_mapped:
        feature_vector.extend([float(j["x"]), float(j["y"]), float(j["z"])])
    for key in sorted(angles.keys()):
        feature_vector.append(float(angles[key]))
    feature_vector.append(float(orientation["yaw_deg"]))
    feature_vector.append(float(orientation["surface_alignment"]))

    return {
        "pose_normalized": {
            "scale_basis": "max_ik_length",
            "ik_max_length": ik_max_length,
            "joints_raw17": normalized_raw17,
            "joints_mapped_humanoid": normalized_mapped,
        },
        "postprocess": {
            "upper_anchor": upper_name,
            "ik_max_length": ik_max_length,
            "regularization": {
                "targets": regularized["targets"],
                "limb_lengths_pre": regularized["pre"],
                "limb_lengths_post": regularized["post"],
            },
            "surface_vector": orientation["forward"],
            "surface_ref": orientation["surface_ref"],
            "surface_alignment": orientation["surface_alignment"],
            "yaw_deg": orientation["yaw_deg"],
            "joint_angles_deg": angles,
        },
        "feature_vector": feature_vector,
    }
