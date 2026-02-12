from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import runpy
from typing import Dict, List, Tuple


ColorBGR = Tuple[int, int, int]
Link = Tuple[str, str]


@dataclass
class RigProfile:
    name: str
    keypoint_names: List[str]
    skeleton_links: List[Link]
    keypoint_colors: Dict[str, ColorBGR]
    link_colors: Dict[Link, ColorBGR]


def _to_bgr(color: object, default: ColorBGR = (0, 230, 230)) -> ColorBGR:
    if isinstance(color, (list, tuple)) and len(color) >= 3:
        r, g, b = int(color[0]), int(color[1]), int(color[2])
        return (int(b), int(g), int(r))
    return default


def _default_color_for_name(name: str) -> ColorBGR:
    lname = (name or "").lower()
    if "left" in lname:
        return (80, 220, 80)
    if "right" in lname:
        return (80, 80, 240)
    if any(k in lname for k in ("nose", "eye", "ear", "face", "head")):
        return (255, 180, 40)
    return (0, 230, 230)


@lru_cache(maxsize=1)
def _load_coco_wholebody_profile() -> RigProfile:
    root = Path(__file__).resolve().parents[1]
    cfg_path = root / "third_party" / "mmpose" / "configs" / "_base_" / "datasets" / "coco_wholebody.py"
    try:
        data = runpy.run_path(str(cfg_path))
        dataset_info = data.get("dataset_info", {})

        keypoint_info = dataset_info.get("keypoint_info", {})
        keypoint_names: List[str] = []
        keypoint_colors: Dict[str, ColorBGR] = {}

        for _, v in sorted(keypoint_info.items(), key=lambda kv: int(kv[0])):
            name = str(v.get("name", f"kpt_{len(keypoint_names)}"))
            keypoint_names.append(name)
            keypoint_colors[name] = _to_bgr(v.get("color"), _default_color_for_name(name))

        skeleton_info = dataset_info.get("skeleton_info", {})
        skeleton_links: List[Link] = []
        link_colors: Dict[Link, ColorBGR] = {}

        for _, v in sorted(skeleton_info.items(), key=lambda kv: int(kv[0])):
            link = v.get("link")
            if not isinstance(link, (list, tuple)) or len(link) != 2:
                continue
            a = str(link[0])
            b = str(link[1])
            pair = (a, b)
            skeleton_links.append(pair)
            link_colors[pair] = _to_bgr(v.get("color"), (200, 200, 200))

        if keypoint_names and skeleton_links:
            return RigProfile(
                name="coco133",
                keypoint_names=keypoint_names,
                skeleton_links=skeleton_links,
                keypoint_colors=keypoint_colors,
                link_colors=link_colors,
            )
    except Exception:
        pass

    fallback_names = [
        "nose",
        "left_eye",
        "right_eye",
        "left_ear",
        "right_ear",
        "left_shoulder",
        "right_shoulder",
        "left_elbow",
        "right_elbow",
        "left_wrist",
        "right_wrist",
        "left_hip",
        "right_hip",
        "left_knee",
        "right_knee",
        "left_ankle",
        "right_ankle",
    ]
    fallback_links: List[Link] = [
        ("nose", "left_eye"),
        ("nose", "right_eye"),
        ("left_eye", "left_ear"),
        ("right_eye", "right_ear"),
        ("left_shoulder", "right_shoulder"),
        ("left_shoulder", "left_elbow"),
        ("left_elbow", "left_wrist"),
        ("right_shoulder", "right_elbow"),
        ("right_elbow", "right_wrist"),
        ("left_shoulder", "left_hip"),
        ("right_shoulder", "right_hip"),
        ("left_hip", "right_hip"),
        ("left_hip", "left_knee"),
        ("left_knee", "left_ankle"),
        ("right_hip", "right_knee"),
        ("right_knee", "right_ankle"),
    ]
    fallback_kp_colors = {name: _default_color_for_name(name) for name in fallback_names}
    fallback_link_colors = {pair: (200, 200, 200) for pair in fallback_links}
    return RigProfile(
        name="coco133",
        keypoint_names=fallback_names,
        skeleton_links=fallback_links,
        keypoint_colors=fallback_kp_colors,
        link_colors=fallback_link_colors,
    )


@lru_cache(maxsize=2)
def get_rig_profile(profile_name: str) -> RigProfile:
    coco = _load_coco_wholebody_profile()
    if str(profile_name).lower().strip() == "body17":
        keep = set(coco.keypoint_names[:17])
        keypoint_names = list(coco.keypoint_names[:17])
        keypoint_colors = {k: coco.keypoint_colors.get(k, _default_color_for_name(k)) for k in keypoint_names}
        skeleton_links = [link for link in coco.skeleton_links if link[0] in keep and link[1] in keep]
        link_colors = {link: coco.link_colors.get(link, (200, 200, 200)) for link in skeleton_links}
        return RigProfile(
            name="body17",
            keypoint_names=keypoint_names,
            skeleton_links=skeleton_links,
            keypoint_colors=keypoint_colors,
            link_colors=link_colors,
        )
    return RigProfile(
        name="coco133",
        keypoint_names=list(coco.keypoint_names),
        skeleton_links=list(coco.skeleton_links),
        keypoint_colors=dict(coco.keypoint_colors),
        link_colors=dict(coco.link_colors),
    )


def get_coco133_names() -> List[str]:
    return list(_load_coco_wholebody_profile().keypoint_names)
