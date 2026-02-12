
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import runpy
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import onnxruntime as ort

import matplotlib


ROOT = Path(__file__).resolve().parents[3]

BODY17_NAMES = [
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

BODY17_LINKS = [
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

BONE_QUAT_SPEC = {
    "spine": (("left_hip", "right_hip"), ("left_shoulder", "right_shoulder"), np.array([0.0, 1.0, 0.0], dtype=np.float64)),
    "left_clavicle": (("left_shoulder", "left_shoulder"), ("left_shoulder", "left_elbow"), np.array([-1.0, 0.0, 0.0], dtype=np.float64)),
    "right_clavicle": (("right_shoulder", "right_shoulder"), ("right_shoulder", "right_elbow"), np.array([1.0, 0.0, 0.0], dtype=np.float64)),
    "left_upper_arm": (("left_shoulder", "left_shoulder"), ("left_shoulder", "left_elbow"), np.array([-1.0, 0.0, 0.0], dtype=np.float64)),
    "right_upper_arm": (("right_shoulder", "right_shoulder"), ("right_shoulder", "right_elbow"), np.array([1.0, 0.0, 0.0], dtype=np.float64)),
    "left_lower_arm": (("left_elbow", "left_elbow"), ("left_elbow", "left_wrist"), np.array([-1.0, 0.0, 0.0], dtype=np.float64)),
    "right_lower_arm": (("right_elbow", "right_elbow"), ("right_elbow", "right_wrist"), np.array([1.0, 0.0, 0.0], dtype=np.float64)),
    "left_thigh": (("left_hip", "left_hip"), ("left_hip", "left_knee"), np.array([-0.2, -1.0, 0.0], dtype=np.float64)),
    "right_thigh": (("right_hip", "right_hip"), ("right_hip", "right_knee"), np.array([0.2, -1.0, 0.0], dtype=np.float64)),
    "left_shank": (("left_knee", "left_knee"), ("left_knee", "left_ankle"), np.array([0.0, -1.0, 0.0], dtype=np.float64)),
    "right_shank": (("right_knee", "right_knee"), ("right_knee", "right_ankle"), np.array([0.0, -1.0, 0.0], dtype=np.float64)),
}


def parse_bool_flag(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "on", "yes", "y")


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.float16, np.float32, np.float64)):
        v = float(value)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(value, (np.int32, np.int64, np.uint8, np.uint16)):
        return int(value)
    if isinstance(value, float):
        return None if (math.isnan(value) or math.isinf(value)) else value
    return value


def configure_matplotlib_backend(show_plot: bool) -> None:
    if show_plot:
        try:
            matplotlib.use("TkAgg")
            return
        except Exception:
            pass
    matplotlib.use("Agg")


def resolve_path(path_value: str | Path) -> Path:
    p = Path(path_value)
    return p if p.is_absolute() else (ROOT / p)


def parse_requested_providers(raw: str) -> list[str]:
    requested = [x.strip() for x in str(raw).split(",") if x.strip()]
    if not requested:
        requested = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return requested


def configure_windows_nvidia_dll_paths() -> None:
    if os.name != "nt":
        return
    base = ROOT / "workspace" / "backend" / ".venv" / "Lib" / "site-packages" / "nvidia"
    candidates = [
        base / "cudnn" / "bin",
        base / "cublas" / "bin",
        base / "cuda_runtime" / "bin",
    ]
    prepend = []
    for p in candidates:
        if p.exists():
            prepend.append(str(p))
            try:
                os.add_dll_directory(str(p))
            except Exception:
                pass
    if prepend:
        os.environ["PATH"] = ";".join(prepend) + ";" + os.environ.get("PATH", "")


def resolve_providers(requested: list[str]) -> list[str]:
    available = set(ort.get_available_providers())
    selected = [p for p in requested if p in available]
    if not selected and "CPUExecutionProvider" in available:
        selected = ["CPUExecutionProvider"]
    if not selected and available:
        selected = [sorted(available)[0]]
    if not selected:
        raise RuntimeError("No ONNX Runtime providers available.")
    return selected


def create_session(model_path: Path, requested_providers: list[str]) -> ort.InferenceSession:
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    providers = resolve_providers(requested_providers)
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    opts.enable_mem_pattern = True
    opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    opts.log_severity_level = 3
    try:
        return ort.InferenceSession(str(model_path), sess_options=opts, providers=providers)
    except Exception:
        if "CPUExecutionProvider" in ort.get_available_providers():
            return ort.InferenceSession(
                str(model_path),
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
        raise


def list_videos(datasets_dir: Path) -> list[Path]:
    exts = {".mp4", ".mov", ".avi", ".mkv"}
    if not datasets_dir.exists():
        return []
    files = [p for p in datasets_dir.rglob("*") if p.is_file() and p.suffix.lower() in exts]
    files.sort()
    return files


def pick_video_and_frame(
    datasets_dir: Path,
    video_arg: str,
    frame_index_arg: str,
    seed: int,
) -> tuple[Path, int, np.ndarray, int]:
    rng = random.Random(int(seed))
    if str(video_arg).strip().lower() == "random":
        files = list_videos(datasets_dir)
        if not files:
            raise RuntimeError(f"No videos found in {datasets_dir}")
        video_path = files[rng.randrange(0, len(files))]
    else:
        video_path = resolve_path(video_arg)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        cap.release()
        raise RuntimeError(f"Video has no readable frames: {video_path}")

    if str(frame_index_arg).strip().lower() == "random":
        frame_idx = rng.randrange(0, total_frames)
    else:
        frame_idx = max(0, min(total_frames - 1, int(frame_index_arg)))

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    if not ok or frame is None:
        cap.release()
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot reopen video: {video_path}")
        ok = False
        frame = None
        for idx in range(total_frames):
            ok, candidate = cap.read()
            if not ok:
                break
            if idx == frame_idx:
                frame = candidate
                ok = True
                break
    cap.release()
    if not ok or frame is None:
        raise RuntimeError(f"Failed reading frame {frame_idx} from {video_path}")

    return video_path, frame_idx, frame, total_frames


def get_input_wh(input_shape: list[Any], default_wh: tuple[int, int]) -> tuple[int, int]:
    if len(input_shape) != 4:
        return default_wh
    h = input_shape[2]
    w = input_shape[3]
    if isinstance(h, int) and isinstance(w, int) and h > 0 and w > 0:
        return int(w), int(h)
    return default_wh


def letterbox_bgr(frame_bgr: np.ndarray, out_wh: tuple[int, int], pad_value: int = 114) -> tuple[np.ndarray, tuple[float, int, int]]:
    src_h, src_w = frame_bgr.shape[:2]
    out_w, out_h = out_wh
    scale = min(out_w / float(src_w), out_h / float(src_h))
    new_w = max(1, int(round(src_w * scale)))
    new_h = max(1, int(round(src_h * scale)))
    resized = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((out_h, out_w, 3), pad_value, dtype=np.uint8)
    pad_x = (out_w - new_w) // 2
    pad_y = (out_h - new_h) // 2
    canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized
    return canvas, (scale, pad_x, pad_y)


def nms_xyxy(boxes: np.ndarray, scores: np.ndarray, iou_thr: float = 0.45) -> np.ndarray:
    if len(boxes) == 0:
        return np.empty((0,), dtype=np.int64)
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    order = np.argsort(scores)[::-1]
    keep = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        union = areas[i] + areas[order[1:]] - inter
        iou = np.where(union > 0.0, inter / union, 0.0)
        inds = np.where(iou <= iou_thr)[0]
        order = order[inds + 1]
    return np.asarray(keep, dtype=np.int64)


def decode_yolox_nx6(output: np.ndarray, score_thr: float, person_class_id: int = 0) -> tuple[np.ndarray | None, float, int]:
    arr = np.asarray(output)
    if arr.ndim == 3 and arr.shape[0] == 1:
        arr = arr[0]
    if arr.ndim != 2 or arr.shape[1] < 6:
        raise RuntimeError(f"Unsupported YOLOX output shape: {arr.shape}")
    boxes = arr[:, :4].astype(np.float32)
    c4 = arr[:, 4].astype(np.float32)
    c5 = arr[:, 5].astype(np.float32)
    c4_int_like = np.all(np.abs(c4 - np.round(c4)) < 1e-4)
    c5_int_like = np.all(np.abs(c5 - np.round(c5)) < 1e-4)

    if c4_int_like and not c5_int_like:
        labels = c4.astype(np.int32)
        scores = c5
    elif c5_int_like and not c4_int_like:
        labels = c5.astype(np.int32)
        scores = c4
    elif float(np.nanmax(c4)) > 1.0 and float(np.nanmax(c5)) <= 1.0:
        labels = c4.astype(np.int32)
        scores = c5
    elif float(np.nanmax(c5)) > 1.0 and float(np.nanmax(c4)) <= 1.0:
        labels = c5.astype(np.int32)
        scores = c4
    else:
        labels = c4.astype(np.int32)
        scores = c5

    finite = np.isfinite(scores) & np.isfinite(boxes).all(axis=1)
    boxes = boxes[finite]
    scores = scores[finite]
    labels = labels[finite]
    if len(boxes) == 0:
        return None, float("nan"), -1

    valid = (labels == int(person_class_id)) & (scores >= float(score_thr))
    if not np.any(valid):
        person_mask = labels == int(person_class_id)
        if np.any(person_mask):
            idx = int(np.argmax(scores * person_mask.astype(np.float32)))
        else:
            idx = int(np.argmax(scores))
        return boxes[idx].astype(np.float32), float(scores[idx]), int(labels[idx])

    boxes_v = boxes[valid]
    scores_v = scores[valid]
    labels_v = labels[valid]
    keep = nms_xyxy(boxes_v, scores_v, iou_thr=0.45)
    if keep.size == 0:
        idx = int(np.argmax(scores_v))
        return boxes_v[idx].astype(np.float32), float(scores_v[idx]), int(labels_v[idx])
    top = keep[int(np.argmax(scores_v[keep]))]
    return boxes_v[top].astype(np.float32), float(scores_v[top]), int(labels_v[top])


def restore_bbox_from_letterbox(
    bbox_xyxy: np.ndarray,
    letterbox_meta: tuple[float, int, int],
    src_wh: tuple[int, int],
) -> np.ndarray | None:
    scale, pad_x, pad_y = letterbox_meta
    src_w, src_h = src_wh
    x1, y1, x2, y2 = [float(v) for v in bbox_xyxy]
    x1 = (x1 - pad_x) / max(scale, 1e-8)
    y1 = (y1 - pad_y) / max(scale, 1e-8)
    x2 = (x2 - pad_x) / max(scale, 1e-8)
    y2 = (y2 - pad_y) / max(scale, 1e-8)
    x1 = float(np.clip(x1, 0.0, float(src_w - 1)))
    y1 = float(np.clip(y1, 0.0, float(src_h - 1)))
    x2 = float(np.clip(x2, 0.0, float(src_w - 1)))
    y2 = float(np.clip(y2, 0.0, float(src_h - 1)))
    if x2 <= x1 or y2 <= y1:
        return None
    return np.array([x1, y1, x2, y2], dtype=np.float32)


def detect_bbox_yolox(
    frame_bgr: np.ndarray,
    det_session: ort.InferenceSession,
    score_thr: float,
) -> tuple[np.ndarray | None, dict[str, Any]]:
    input_meta = det_session.get_inputs()[0]
    input_name = input_meta.name
    input_type = input_meta.type
    input_wh = get_input_wh(input_meta.shape, (640, 640))
    letterboxed, lb_meta = letterbox_bgr(frame_bgr, input_wh)
    rgb = cv2.cvtColor(letterboxed, cv2.COLOR_BGR2RGB)
    tensor = rgb.astype(np.float32)
    tensor = tensor.transpose(2, 0, 1)[None, ...]
    if "float16" in input_type:
        tensor = tensor.astype(np.float16)
    tensor = np.ascontiguousarray(tensor)

    t0 = time.perf_counter()
    outputs = det_session.run(None, {input_name: tensor})
    det_ms = (time.perf_counter() - t0) * 1000.0

    bbox_model, det_score, det_class = decode_yolox_nx6(outputs[0], score_thr=score_thr, person_class_id=0)
    if bbox_model is None:
        return None, {
            "det_ms": det_ms,
            "det_score": None,
            "det_class": None,
            "input_wh": input_wh,
        }
    bbox_src = restore_bbox_from_letterbox(bbox_model, lb_meta, (frame_bgr.shape[1], frame_bgr.shape[0]))
    return bbox_src, {
        "det_ms": det_ms,
        "det_score": float(det_score),
        "det_class": int(det_class),
        "input_wh": input_wh,
    }

def load_coco_wholebody_names() -> list[str]:
    cfg = ROOT / "third_party" / "mmpose" / "configs" / "_base_" / "datasets" / "coco_wholebody.py"
    if not cfg.exists():
        return [f"kpt_{i}" for i in range(133)]
    try:
        data = runpy.run_path(str(cfg))
        dataset_info = data.get("dataset_info", {})
        kp_info = dataset_info.get("keypoint_info", {})
        names: list[str] = []
        for _, item in sorted(kp_info.items(), key=lambda kv: int(kv[0])):
            names.append(str(item.get("name", f"kpt_{len(names)}")))
        return names if names else [f"kpt_{i}" for i in range(133)]
    except Exception:
        return [f"kpt_{i}" for i in range(133)]


def expand_bbox(bbox_xyxy: np.ndarray, frame_shape: tuple[int, int, int], ratio: float = 0.10) -> np.ndarray:
    x1, y1, x2, y2 = [float(v) for v in bbox_xyxy]
    bw = max(1.0, x2 - x1)
    bh = max(1.0, y2 - y1)
    mx = ratio * bw
    my = ratio * bh
    x1 -= mx
    x2 += mx
    y1 -= my
    y2 += my
    h, w = frame_shape[:2]
    x1 = float(np.clip(x1, 0.0, float(w - 1)))
    y1 = float(np.clip(y1, 0.0, float(h - 1)))
    x2 = float(np.clip(x2, 0.0, float(w - 1)))
    y2 = float(np.clip(y2, 0.0, float(h - 1)))
    return np.array([x1, y1, x2, y2], dtype=np.float32)


def infer_pose_rtmw3d(
    frame_bgr: np.ndarray,
    bbox_xyxy: np.ndarray,
    pose_session: ort.InferenceSession,
    joint_names: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    x1, y1, x2, y2 = expand_bbox(bbox_xyxy, frame_bgr.shape, ratio=0.10).tolist()
    x1i, y1i, x2i, y2i = int(x1), int(y1), int(x2), int(y2)
    crop = frame_bgr[y1i:y2i, x1i:x2i]
    if crop.size == 0:
        raise RuntimeError("Pose crop is empty after bbox expansion.")

    in_w, in_h = 288, 384
    crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(crop_rgb, (in_w, in_h), interpolation=cv2.INTER_LINEAR)
    arr = resized.astype(np.float32)
    arr = (arr - np.array([123.675, 116.28, 103.53], dtype=np.float32)) / np.array(
        [58.395, 57.12, 57.375], dtype=np.float32
    )
    arr = arr.transpose(2, 0, 1)[None, ...]
    in_type = pose_session.get_inputs()[0].type
    if "float16" in in_type:
        arr = arr.astype(np.float16)
    else:
        arr = arr.astype(np.float32)
    arr = np.ascontiguousarray(arr)

    t0 = time.perf_counter()
    simcc_x, simcc_y, simcc_z = pose_session.run(None, {pose_session.get_inputs()[0].name: arr})
    pose_ms = (time.perf_counter() - t0) * 1000.0

    loc_x = np.argmax(simcc_x[0], axis=1)
    loc_y = np.argmax(simcc_y[0], axis=1)
    loc_z = np.argmax(simcc_z[0], axis=1)
    kx = loc_x.astype(np.float32) / 2.0
    ky = loc_y.astype(np.float32) / 2.0
    kz = loc_z.astype(np.float32) / 2.0

    box_w = max(1.0, x2 - x1)
    box_h = max(1.0, y2 - y1)
    sx = box_w / float(in_w)
    sy = box_h / float(in_h)
    px = kx * sx + x1
    py = ky * sy + y1

    z_rel = (kz / (in_w / 2.0) - 1.0) * 2.1744869
    z_scale = max(1.0, 0.5 * max(box_w, box_h))
    pz = z_rel * z_scale

    scores_x = np.max(simcc_x[0], axis=1).astype(np.float32)
    scores_y = np.max(simcc_y[0], axis=1).astype(np.float32)
    scores_z = np.max(simcc_z[0], axis=1).astype(np.float32)
    scores = np.minimum(np.minimum(scores_x, scores_y), scores_z)

    h_img, w_img = frame_bgr.shape[:2]
    joints: list[dict[str, Any]] = []
    for i in range(len(px)):
        name = joint_names[i] if i < len(joint_names) else f"kpt_{i}"
        joints.append(
            {
                "name": str(name),
                "x": float(px[i]),
                "y": float(py[i]),
                "z": float(pz[i]),
                "c": float(scores[i]),
                "px": float(px[i] / max(1.0, float(w_img))),
                "py": float(py[i] / max(1.0, float(h_img))),
            }
        )

    return joints, {"pose_ms": pose_ms, "crop_xyxy": [float(x1), float(y1), float(x2), float(y2)]}


def joints_by_name(joints: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(j["name"]): j for j in joints}


def extract_body17(joints_133: list[dict[str, Any]]) -> list[dict[str, Any]]:
    src = joints_by_name(joints_133)
    out: list[dict[str, Any]] = []
    for name in BODY17_NAMES:
        if name in src:
            out.append(dict(src[name]))
    return out


def normalize_vec(v: np.ndarray, fallback: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n <= 1e-9:
        return fallback.astype(np.float64)
    return v.astype(np.float64) / n


def orthonormal_basis(ex: np.ndarray, ey_seed: np.ndarray) -> np.ndarray:
    x = normalize_vec(ex, np.array([1.0, 0.0, 0.0], dtype=np.float64))
    y = ey_seed - np.dot(ey_seed, x) * x
    y = normalize_vec(y, np.array([0.0, 1.0, 0.0], dtype=np.float64))
    z = np.cross(x, y)
    z = normalize_vec(z, np.array([0.0, 0.0, 1.0], dtype=np.float64))
    y = np.cross(z, x)
    y = normalize_vec(y, np.array([0.0, 1.0, 0.0], dtype=np.float64))
    return np.stack([x, y, z], axis=1)


def build_canonical_frame(body17: list[dict[str, Any]]) -> dict[str, Any]:
    jmap = joints_by_name(body17)
    required = ["left_hip", "right_hip", "left_shoulder", "right_shoulder"]
    missing = [k for k in required if k not in jmap]
    if missing:
        raise RuntimeError(f"Missing joints for canonical frame: {missing}")

    lhip = np.array([jmap["left_hip"]["x"], jmap["left_hip"]["y"], jmap["left_hip"]["z"]], dtype=np.float64)
    rhip = np.array([jmap["right_hip"]["x"], jmap["right_hip"]["y"], jmap["right_hip"]["z"]], dtype=np.float64)
    lsho = np.array([jmap["left_shoulder"]["x"], jmap["left_shoulder"]["y"], jmap["left_shoulder"]["z"]], dtype=np.float64)
    rsho = np.array([jmap["right_shoulder"]["x"], jmap["right_shoulder"]["y"], jmap["right_shoulder"]["z"]], dtype=np.float64)

    pelvis = 0.5 * (lhip + rhip)
    shoulder_mid = 0.5 * (lsho + rsho)

    # Torso plane from the 4 anchor joints via PCA/eigendecomposition.
    torso_pts = np.stack([lhip, rhip, lsho, rsho], axis=0)
    torso_center = np.mean(torso_pts, axis=0)
    torso_zero = torso_pts - torso_center
    cov = torso_zero.T @ torso_zero / max(1, torso_zero.shape[0] - 1)
    evals, evecs = np.linalg.eigh(cov)
    sort_idx = np.argsort(evals)
    evals = evals[sort_idx]
    evecs = evecs[:, sort_idx]
    plane_normal = normalize_vec(evecs[:, 0], np.array([0.0, 0.0, 1.0], dtype=np.float64))

    hip_lr = normalize_vec(rhip - lhip, np.array([1.0, 0.0, 0.0], dtype=np.float64))
    shoulder_lr = normalize_vec(rsho - lsho, np.array([1.0, 0.0, 0.0], dtype=np.float64))
    x_seed = normalize_vec(0.5 * (hip_lr + shoulder_lr), hip_lr)
    x_seed = x_seed - float(np.dot(x_seed, plane_normal)) * plane_normal
    x_seed = normalize_vec(x_seed, shoulder_lr)

    torso_vec = shoulder_mid - pelvis
    y_seed = torso_vec - float(np.dot(torso_vec, plane_normal)) * plane_normal
    y_seed = normalize_vec(y_seed, np.array([0.0, 1.0, 0.0], dtype=np.float64))

    rot = orthonormal_basis(x_seed, y_seed)
    x_axis = rot[:, 0]
    y_axis = rot[:, 1]
    z_axis = rot[:, 2]

    # Keep anatomical left/right stable in canonical space.
    shoulder_lr = rsho - lsho
    if float(np.dot(shoulder_lr, x_axis)) < 0.0:
        x_axis *= -1.0
        z_axis *= -1.0

    # Keep anatomical "up" stable.
    if float(np.dot(torso_vec, y_axis)) < 0.0:
        y_axis *= -1.0
        z_axis *= -1.0

    rot = np.stack([x_axis, y_axis, z_axis], axis=1)

    torso_len = float(np.linalg.norm(shoulder_mid - pelvis))
    shoulder_w = float(np.linalg.norm(rsho - lsho))
    hip_w = float(np.linalg.norm(rhip - lhip))
    scale_candidates = [v for v in [torso_len, 0.9 * shoulder_w, 1.1 * hip_w] if v > 1e-6]
    scale = float(np.median(np.asarray(scale_candidates, dtype=np.float64))) if scale_candidates else 1.0
    yaw_deg = float(np.degrees(np.arctan2(rot[2, 0], rot[0, 0])))

    return {
        "origin_pelvis": pelvis,
        "rotation": rot,
        "axis_x_lateral": rot[:, 0],
        "axis_y_up": rot[:, 1],
        "axis_z_depth": rot[:, 2],
        "torso_plane_normal": plane_normal,
        "torso_plane_eigenvalues": evals,
        "torso_plane_planarity": float(evals[0] / max(1e-9, evals[1] + evals[2])),
        "yaw_deg": yaw_deg,
        "scale_unit": max(scale, 1e-6),
    }


def canonicalize_body17(body17: list[dict[str, Any]], canonical_frame: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    origin = canonical_frame["origin_pelvis"]
    rot = canonical_frame["rotation"]
    scale = canonical_frame["scale_unit"]
    canonical: list[dict[str, Any]] = []
    raw_centered: list[dict[str, Any]] = []
    for j in body17:
        vec = np.array([j["x"], j["y"], j["z"]], dtype=np.float64)
        centered = (vec - origin) / max(scale, 1e-9)
        canon = rot.T @ centered
        base = {
            "name": str(j["name"]),
            "c": float(j["c"]),
            "px": float(j["px"]),
            "py": float(j["py"]),
        }
        raw_centered.append(
            {
                **base,
                "x": float(centered[0]),
                "y": float(centered[1]),
                "z": float(centered[2]),
            }
        )
        canonical.append(
            {
                **base,
                "x": float(canon[0]),
                "y": float(canon[1]),
                "z": float(canon[2]),
            }
        )
    return canonical, raw_centered


def canonical_to_zup(canonical_body17: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Internal canonical uses (X=lateral, Y=up, Z=depth).
    # This view remaps to (X=lateral, Y=depth, Z=up).
    out: list[dict[str, Any]] = []
    for j in canonical_body17:
        out.append(
            {
                "name": str(j["name"]),
                "x": float(j["x"]),
                "y": float(j["z"]),
                "z": float(j["y"]),
                "c": float(j["c"]),
                "px": float(j["px"]),
                "py": float(j["py"]),
            }
        )
    return out


def angle_at(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    ba = a - b
    bc = c - b
    nba = float(np.linalg.norm(ba))
    nbc = float(np.linalg.norm(bc))
    if nba < 1e-8 or nbc < 1e-8:
        return float("nan")
    cosang = float(np.dot(ba, bc) / (nba * nbc))
    cosang = max(-1.0, min(1.0, cosang))
    return float(np.degrees(np.arccos(cosang)))


def quat_normalize(q: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(q))
    if n <= 1e-12:
        return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
    return q / n


def quat_from_two_vectors(v0: np.ndarray, v1: np.ndarray) -> np.ndarray:
    a = normalize_vec(v0, np.array([1.0, 0.0, 0.0], dtype=np.float64))
    b = normalize_vec(v1, np.array([1.0, 0.0, 0.0], dtype=np.float64))
    dot = float(np.clip(np.dot(a, b), -1.0, 1.0))
    if dot > 0.999999:
        return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
    if dot < -0.999999:
        axis = np.cross(np.array([1.0, 0.0, 0.0], dtype=np.float64), a)
        if float(np.linalg.norm(axis)) < 1e-6:
            axis = np.cross(np.array([0.0, 1.0, 0.0], dtype=np.float64), a)
        axis = normalize_vec(axis, np.array([0.0, 0.0, 1.0], dtype=np.float64))
        return np.array([0.0, axis[0], axis[1], axis[2]], dtype=np.float64)
    axis = np.cross(a, b)
    w = math.sqrt((1.0 + dot) * 2.0) * 0.5
    xyz = axis / max(1e-12, 2.0 * w)
    q = quat_normalize(np.array([w, xyz[0], xyz[1], xyz[2]], dtype=np.float64))
    if q[0] < 0.0:
        q = -q
    return q


def compute_ik_quantities(body17_raw: list[dict[str, Any]], body17_canonical: list[dict[str, Any]]) -> dict[str, Any]:
    raw_map = joints_by_name(body17_raw)
    can_map = joints_by_name(body17_canonical)

    def p(m: dict[str, dict[str, Any]], name: str) -> np.ndarray | None:
        j = m.get(name)
        if not j:
            return None
        return np.array([j["x"], j["y"], j["z"]], dtype=np.float64)

    angles = {
        "left_elbow": float("nan"),
        "right_elbow": float("nan"),
        "left_knee": float("nan"),
        "right_knee": float("nan"),
        "left_shoulder": float("nan"),
        "right_shoulder": float("nan"),
        "left_hip": float("nan"),
        "right_hip": float("nan"),
        "trunk_flexion": float("nan"),
    }

    lsho, lel, lwr = p(can_map, "left_shoulder"), p(can_map, "left_elbow"), p(can_map, "left_wrist")
    rsho, rel, rwr = p(can_map, "right_shoulder"), p(can_map, "right_elbow"), p(can_map, "right_wrist")
    lhip, lk, la = p(can_map, "left_hip"), p(can_map, "left_knee"), p(can_map, "left_ankle")
    rhip, rk, ra = p(can_map, "right_hip"), p(can_map, "right_knee"), p(can_map, "right_ankle")

    if lsho is not None and lel is not None and lwr is not None:
        angles["left_elbow"] = angle_at(lsho, lel, lwr)
    if rsho is not None and rel is not None and rwr is not None:
        angles["right_elbow"] = angle_at(rsho, rel, rwr)
    if lhip is not None and lk is not None and la is not None:
        angles["left_knee"] = angle_at(lhip, lk, la)
    if rhip is not None and rk is not None and ra is not None:
        angles["right_knee"] = angle_at(rhip, rk, ra)
    if lel is not None and lsho is not None and lhip is not None:
        angles["left_shoulder"] = angle_at(lel, lsho, lhip)
    if rel is not None and rsho is not None and rhip is not None:
        angles["right_shoulder"] = angle_at(rel, rsho, rhip)
    if lk is not None and lhip is not None and lsho is not None:
        angles["left_hip"] = angle_at(lk, lhip, lsho)
    if rk is not None and rhip is not None and rsho is not None:
        angles["right_hip"] = angle_at(rk, rhip, rsho)

    if lhip is not None and rhip is not None and lsho is not None and rsho is not None:
        pelvis = 0.5 * (lhip + rhip)
        shoulder_mid = 0.5 * (lsho + rsho)
        trunk = normalize_vec(shoulder_mid - pelvis, np.array([0.0, 1.0, 0.0], dtype=np.float64))
        up = np.array([0.0, 1.0, 0.0], dtype=np.float64)
        cosv = float(np.clip(np.dot(trunk, up), -1.0, 1.0))
        angles["trunk_flexion"] = float(np.degrees(np.arccos(cosv)))

    quats: dict[str, list[float]] = {}
    raw_lengths: dict[str, float] = {}
    can_lengths: dict[str, float] = {}

    for bone_name, (_, raw_cd, rest_dir) in BONE_QUAT_SPEC.items():
        parent_name = raw_cd[0]
        child_name = raw_cd[1]
        rp = p(raw_map, parent_name)
        rc = p(raw_map, child_name)
        cp = p(can_map, parent_name)
        cc = p(can_map, child_name)
        if rp is not None and rc is not None:
            raw_lengths[bone_name] = float(np.linalg.norm(rc - rp))
        else:
            raw_lengths[bone_name] = float("nan")
        if cp is not None and cc is not None:
            vec = cc - cp
            can_lengths[bone_name] = float(np.linalg.norm(vec))
            if float(np.linalg.norm(vec)) > 1e-9:
                q = quat_from_two_vectors(rest_dir, vec)
                quats[bone_name] = [float(q[0]), float(q[1]), float(q[2]), float(q[3])]
            else:
                quats[bone_name] = [1.0, 0.0, 0.0, 0.0]
        else:
            can_lengths[bone_name] = float("nan")
            quats[bone_name] = [float("nan")] * 4

    return {
        "joint_angles_deg": angles,
        "bone_quaternions_wxyz": quats,
        "bone_lengths_raw": raw_lengths,
        "bone_lengths_canonical": can_lengths,
    }


def quality_report(body17_raw: list[dict[str, Any]]) -> dict[str, Any]:
    if not body17_raw:
        return {"visible_ratio_body17": 0.0, "min_conf_body17": 0.0, "notes": ["no_body17_joints"]}
    confs = np.asarray([float(j["c"]) for j in body17_raw], dtype=np.float64)
    vis_ratio = float(np.mean(confs >= 0.10))
    min_conf = float(np.min(confs))
    notes: list[str] = []
    if vis_ratio < 0.50:
        notes.append("low_visible_ratio_body17")
    if min_conf < 0.05:
        notes.append("very_low_confidence")
    return {"visible_ratio_body17": vis_ratio, "min_conf_body17": min_conf, "notes": notes}


def color_for_joint(name: str) -> tuple[int, int, int]:
    lname = name.lower()
    if "left" in lname:
        # Magenta-ish for left side to stay visible on green backgrounds.
        return (96, 96, 192)
    if "right" in lname:
        # Cyan-ish for right side.
        return (255, 96, 96)
    # Center line / face fallback.
    return (40, 180, 255)


def color_for_link(a: str, b: str) -> tuple[int, int, int]:
    pair = {a, b}
    # Core torso links should stay neutral for readability.
    # if pair == {"left_shoulder", "right_shoulder"}:
    #     return (210, 210, 210)
    # if pair == {"left_hip", "right_hip"}:
    #     return (210, 210, 210)
    # if pair == {"left_shoulder", "left_hip"}:
    #     return (210, 210, 210)
    # if pair == {"right_shoulder", "right_hip"}:
    #     return (210, 210, 210)
    if "left" in a and "left" in b:
        return (255, 90, 255)
    if "right" in a and "right" in b:
        return (255, 220, 40)
    return (40, 180, 255)


def draw_overlay(
    frame_bgr: np.ndarray,
    bbox_xyxy: np.ndarray | None,
    body17_raw: list[dict[str, Any]],
    out_path: Path,
    meta_text: list[str],
) -> None:
    img = frame_bgr.copy()
    h, w = img.shape[:2]

    if bbox_xyxy is not None:
        x1, y1, x2, y2 = [int(v) for v in bbox_xyxy.tolist()]
        cv2.rectangle(img, (x1, y1), (x2, y2), (40, 255, 90), 2, cv2.LINE_AA)

    jmap = joints_by_name(body17_raw)
    for a, b in BODY17_LINKS:
        ja = jmap.get(a)
        jb = jmap.get(b)
        if ja is None or jb is None:
            continue
        conf = min(float(ja["c"]), float(jb["c"]))
        if conf < 0.05:
            continue
        p1 = (int(float(ja["px"]) * w), int(float(ja["py"]) * h))
        p2 = (int(float(jb["px"]) * w), int(float(jb["py"]) * h))
        cv2.line(img, p1, p2, color_for_link(a, b), 2, cv2.LINE_AA)

    for j in body17_raw:
        conf = float(j["c"])
        if conf < 0.03:
            continue
        px = int(float(j["px"]) * w)
        py = int(float(j["py"]) * h)
        cv2.circle(img, (px, py), 4, color_for_joint(str(j["name"])), -1, cv2.LINE_AA)

    y = 24
    for txt in meta_text:
        cv2.putText(img, txt, (10, y), cv2.FONT_HERSHEY_DUPLEX, 0.55, (240, 240, 240), 1, cv2.LINE_AA)
        y += 22

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), img)


def plot_3d(
    raw_centered: list[dict[str, Any]],
    canonical_zup: list[dict[str, Any]],
    out_path: Path,
    title_left: str,
    title_right: str,
    save_plot: bool = True,
    show_plot: bool = False,
    view_elev: float = 24.0,
    view_azim: float = -58.0,
) -> None:
    import matplotlib.pyplot as plt

    def remap_raw_to_zup(joints: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for j in joints:
            out.append(
                {
                    "name": str(j["name"]),
                    "x": float(j["x"]),
                    "y": float(j["y"]),
                    "z": float(j["z"]),
                    
                    
                    # "x": float(j["x"]),
                    # "y": float(j["z"]),
                    # Raw centered comes from image coordinates where y is down.
                    # Flip sign so display uses z-up.
                    # "z": float(-j["y"]),
                    "c": float(j["c"]),
                }
            )
        return out

    def orient_for_display_zup(joints: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = [dict(j) for j in joints]
        jmap = joints_by_name(out)

        # Step 1: keep feet visually below hips.
        if all(k in jmap for k in ["left_hip", "right_hip", "left_ankle", "right_ankle"]):
            z_hip = 0.5 * (float(jmap["left_hip"]["z"]) + float(jmap["right_hip"]["z"]))
            z_ank = 0.5 * (float(jmap["left_ankle"]["z"]) + float(jmap["right_ankle"]["z"]))
            if z_ank > z_hip:
                for j in out:
                    j["z"] = -float(j["z"])

        # Step 2: rotate around z-up so subject faces +X in the plot.
        jmap = joints_by_name(out)
        fxy = None
        if all(k in jmap for k in ["nose", "left_shoulder", "right_shoulder"]):
            n = np.array([jmap["nose"]["x"], jmap["nose"]["y"]], dtype=np.float64)
            sm = 0.5 * (
                np.array([jmap["left_shoulder"]["x"], jmap["left_shoulder"]["y"]], dtype=np.float64)
                + np.array([jmap["right_shoulder"]["x"], jmap["right_shoulder"]["y"]], dtype=np.float64)
            )
            d = n - sm
            if float(np.linalg.norm(d)) > 1e-6:
                fxy = d

        if fxy is None and all(k in jmap for k in ["left_shoulder", "right_shoulder"]):
            ls = np.array([jmap["left_shoulder"]["x"], jmap["left_shoulder"]["y"]], dtype=np.float64)
            rs = np.array([jmap["right_shoulder"]["x"], jmap["right_shoulder"]["y"]], dtype=np.float64)
            lateral = rs - ls
            if float(np.linalg.norm(lateral)) > 1e-6:
                fxy = np.array([-lateral[1], lateral[0]], dtype=np.float64)

        if fxy is not None:
            theta = float(np.arctan2(fxy[1], fxy[0]))
            c = float(np.cos(-theta))
            s = float(np.sin(-theta))
            for j in out:
                x = float(j["x"])
                y = float(j["y"])
                j["x"] = c * x - s * y
                j["y"] = s * x + c * y

            # Ensure display-forward points to +X.
            jmap = joints_by_name(out)
            if all(k in jmap for k in ["nose", "left_shoulder", "right_shoulder"]):
                n = np.array([jmap["nose"]["x"], jmap["nose"]["y"]], dtype=np.float64)
                sm = 0.5 * (
                    np.array([jmap["left_shoulder"]["x"], jmap["left_shoulder"]["y"]], dtype=np.float64)
                    + np.array([jmap["right_shoulder"]["x"], jmap["right_shoulder"]["y"]], dtype=np.float64)
                )
                d = n - sm
                if float(d[0]) < 0.0:
                    for j in out:
                        j["x"] = -float(j["x"])
                        j["y"] = -float(j["y"])

            # Small fixed yaw for iso readability (avoid flat-looking frontal projection).
            iso = float(np.deg2rad(30.0))
            c2 = float(np.cos(iso))
            s2 = float(np.sin(iso))
            for j in out:
                x = float(j["x"])
                y = float(j["y"])
                j["x"] = c2 * x - s2 * y
                j["y"] = s2 * x + c2 * y

        return out

    def normalize_size_max_connection_01(joints: list[dict[str, Any]], conf_thr: float = 0.05) -> tuple[list[dict[str, Any]], float]:
        required = ["left_hip", "right_hip", "left_shoulder", "right_shoulder"]
        out = [dict(j) for j in joints]
        jmap = joints_by_name(out)
        
        lengths = []
        for a, b in BODY17_LINKS:
            ja = jmap.get(a)
            jb = jmap.get(b)
            if ja is None or jb is None:
                continue
            if min(float(ja.get("c", 0.0)), float(jb.get("c", 0.0))) < conf_thr:
                continue
            va = np.array([float(ja["x"]), float(ja["y"]), float(ja["z"])], dtype=np.float64)
            vb = np.array([float(jb["x"]), float(jb["y"]), float(jb["z"])], dtype=np.float64)
            d = float(np.linalg.norm(vb - va))
            if np.isfinite(d) and d > 1e-9:
                lengths.append(d)
        if not lengths:
            return out, 1.0

        scale = float(np.max(np.asarray(lengths, dtype=np.float64)))
        scale = max(scale, 1e-9)
        for j in out:
            j["x"] = float(j["x"]) / scale
            j["y"] = float(j["y"]) / scale
            j["z"] = float(j["z"]) / scale
        jmap = joints_by_name(out)
        chest = [v for k, v in jmap.items() if k in required]
        
        print(chest)
        exit()
            
        pts = np.asarray([[float(j["x"]), float(j["y"]), float(j["z"])] for j in out], dtype=np.float64)
        mins = np.min(pts, axis=0)
        maxs = np.max(pts, axis=0)
        spans = np.maximum(maxs - mins, 1e-9)
        for j in out:
            j["x"] = float((j["x"] - mins[0]) / spans[0])
            j["y"] = float((j["y"] - mins[1]) / spans[1])
            j["z"] = float((j["z"] - mins[2]) / spans[2])
        return out, scale

    def to_arrays(joints: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], np.ndarray]:
        xs, ys, zs, names, confs = [], [], [], [], []
        for j in joints:
            xs.append(float(j["x"]))
            ys.append(float(j["y"]))
            zs.append(float(j["z"]))
            names.append(str(j["name"]))
            confs.append(float(j["c"]))
        return (
            np.asarray(xs, dtype=np.float64),
            np.asarray(ys, dtype=np.float64),
            np.asarray(zs, dtype=np.float64),
            names,
            np.asarray(confs, dtype=np.float64),
        )

    def draw_subplot(ax, joints: list[dict[str, Any]], title: str) -> None:
        xs, ys, zs, names, confs = to_arrays(joints)
        if len(xs) == 0:
            ax.set_title(f"{title} (empty)")
            return
        colors = []
        for n in names:
            bgr = color_for_joint(n)
            colors.append((bgr[2] / 255.0, bgr[1] / 255.0, bgr[0] / 255.0))
        mask = confs >= 0.05
        ax.scatter(xs[mask], ys[mask], zs[mask], c=np.asarray(colors)[mask], s=28)

        jmap = {str(j["name"]): j for j in joints}
        for a, b in BODY17_LINKS:
            ja = jmap.get(a)
            jb = jmap.get(b)
            if ja is None or jb is None:
                continue
            conf = min(float(ja["c"]), float(jb["c"]))
            if conf < 0.05:
                continue
            col = color_for_link(a, b)
            ax.plot(
                [float(ja["x"]), float(jb["x"])],
                [float(ja["y"]), float(jb["y"])],
                [float(ja["z"]), float(jb["z"])],
                color=(col[2] / 255.0, col[1] / 255.0, col[0] / 255.0),
                linewidth=2.0,
            )

        finite_vals = np.hstack([np.abs(xs), np.abs(ys), np.abs(zs)])
        finite_vals = finite_vals[np.isfinite(finite_vals)]
        span = 1.2
        if finite_vals.size > 0:
            span = max(1.2, min(5.0, float(np.percentile(finite_vals, 95)) * 1.4))
        ax.set_xlim(-span, span)
        ax.set_ylim(-span, span)
        ax.set_zlim(-span, span)
        ax.set_xlabel("X lateral")
        ax.set_ylabel("Y depth")
        ax.set_zlabel("Z up")
        ax.set_title(title)
        ax.view_init(elev=float(view_elev), azim=float(view_azim))

    raw_display = orient_for_display_zup(remap_raw_to_zup(raw_centered))
    canonical_display = orient_for_display_zup(canonical_zup)
    raw_norm_01, max_conn_scale = normalize_size_max_connection_01(raw_display, conf_thr=0.05)

    fig = plt.figure(figsize=(18.5, 5.8))
    ax1 = fig.add_subplot(1, 3, 1, projection="3d")
    ax2 = fig.add_subplot(1, 3, 2, projection="3d")
    ax3 = fig.add_subplot(1, 3, 3, projection="3d")
    draw_subplot(ax1, raw_display, title_left)
    draw_subplot(ax2, canonical_display, title_right)
    draw_subplot(ax3, raw_norm_01, f"Raw normalized [0,1] (max-connection={max_conn_scale:.3f})")
    fig.tight_layout()
    if save_plot:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(out_path), dpi=140)
    if show_plot:
        plt.show()
    plt.close(fig)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(to_jsonable(payload), f, ensure_ascii=False, indent=2)


def write_angles_csv(path: Path, angles: dict[str, Any], meta: dict[str, Any]) -> None:
    keys = sorted(angles.keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["video", "frame_idx", *keys])
        writer.writerow([meta["video"], meta["frame_idx"], *[angles[k] for k in keys]])


def write_joints_csv(
    path: Path,
    body17_raw: list[dict[str, Any]],
    body17_canonical: list[dict[str, Any]],
    body17_canonical_zup: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["space", "joint", "x", "y", "z", "c", "px", "py"])
        for j in body17_raw:
            writer.writerow(["raw", j["name"], j["x"], j["y"], j["z"], j["c"], j["px"], j["py"]])
        for j in body17_canonical:
            writer.writerow(["canonical", j["name"], j["x"], j["y"], j["z"], j["c"], j["px"], j["py"]])
        for j in body17_canonical_zup:
            writer.writerow(["canonical_zup", j["name"], j["x"], j["y"], j["z"], j["c"], j["px"], j["py"]])


def build_failure_payload(meta: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "reason": reason,
        "meta": meta,
        "bbox_xyxy": None,
        "raw_joints_133": [],
        "body17_raw": [],
        "canonical_body17": [],
        "canonical_frame": {},
        "ik": {
            "bone_quaternions_wxyz": {},
            "joint_angles_deg": {},
            "bone_lengths_raw": {},
            "bone_lengths_canonical": {},
        },
        "quality": {"visible_ratio_body17": 0.0, "min_conf_body17": 0.0, "notes": [reason]},
    }

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Proof script: 1-frame ONNX detection + RTMW3D canonical normalization.")
    parser.add_argument("--datasets-dir", default="datasets")
    parser.add_argument("--video", default="random")
    parser.add_argument("--frame-index", default="random")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--det-model", default="workspace/backend/models/onnx/yolox_s_humanart_fp32.onnx")
    parser.add_argument("--pose-model", default="workspace/backend/models/onnx/rtmw3d_l_fp16.onnx")
    parser.add_argument("--providers", default="CUDAExecutionProvider,CPUExecutionProvider")
    parser.add_argument("--det-score-thr", type=float, default=0.35)
    parser.add_argument("--out-dir", default="workspace/backend/benchmarks/canonical_proof")
    parser.add_argument("--save-plot", choices=["on", "off"], default="on")
    parser.add_argument("--plot-show", choices=["on", "off"], default="off")
    parser.add_argument("--plot-elev", type=float, default=24.0)
    parser.add_argument("--plot-azim", type=float, default=-58.0)
    parser.add_argument("--save-overlay", choices=["on", "off"], default="on")
    parser.add_argument("--save-json", choices=["on", "off"], default="on")
    parser.add_argument("--save-csv", choices=["on", "off"], default="on")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plot_show = parse_bool_flag(args.plot_show)
    configure_matplotlib_backend(show_plot=plot_show)
    configure_windows_nvidia_dll_paths()
    out_dir = resolve_path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    datasets_dir = resolve_path(args.datasets_dir)
    det_model = resolve_path(args.det_model)
    pose_model = resolve_path(args.pose_model)
    requested_providers = parse_requested_providers(args.providers)

    video_path, frame_idx, frame_bgr, total_frames = pick_video_and_frame(
        datasets_dir=datasets_dir,
        video_arg=args.video,
        frame_index_arg=args.frame_index,
        seed=args.seed,
    )

    det_session = create_session(det_model, requested_providers)
    pose_session = create_session(pose_model, requested_providers)
    active_det_providers = det_session.get_providers()
    active_pose_providers = pose_session.get_providers()
    names133 = load_coco_wholebody_names()

    meta = {
        "video": str(video_path),
        "frame_idx": int(frame_idx),
        "video_total_frames": int(total_frames),
        "seed": int(args.seed),
        "det_model": str(det_model),
        "pose_model": str(pose_model),
        "requested_providers": requested_providers,
        "det_active_providers": active_det_providers,
        "pose_active_providers": active_pose_providers,
        "timestamp_unix_s": float(time.time()),
    }

    try:
        bbox_xyxy, det_info = detect_bbox_yolox(frame_bgr, det_session, score_thr=float(args.det_score_thr))
        meta.update(det_info)
        if bbox_xyxy is None:
            payload = build_failure_payload(meta, "detector_no_bbox")
            if parse_bool_flag(args.save_json):
                write_json(out_dir / "canonical_proof_latest.json", payload)
            return 2

        joints_133, pose_info = infer_pose_rtmw3d(frame_bgr, bbox_xyxy, pose_session, names133)
        meta.update(pose_info)

        body17_raw = extract_body17(joints_133)
        canonical_frame = build_canonical_frame(body17_raw)
        canonical_body17, raw_centered_body17 = canonicalize_body17(body17_raw, canonical_frame)
        canonical_body17_zup = canonical_to_zup(canonical_body17)
        ik = compute_ik_quantities(body17_raw, canonical_body17)
        quality = quality_report(body17_raw)

        pelvis_norm = None
        can_map = joints_by_name(canonical_body17)
        if "left_hip" in can_map and "right_hip" in can_map:
            pelvis_norm = (
                0.5 * np.array(
                    [
                        can_map["left_hip"]["x"] + can_map["right_hip"]["x"],
                        can_map["left_hip"]["y"] + can_map["right_hip"]["y"],
                        can_map["left_hip"]["z"] + can_map["right_hip"]["z"],
                    ],
                    dtype=np.float64,
                )
            ).tolist()
        quality["notes"].append("pelvis_norm_near_zero" if pelvis_norm is not None else "pelvis_norm_missing")

        payload = {
            "status": "ok",
            "meta": meta,
            "bbox_xyxy": [float(v) for v in bbox_xyxy.tolist()],
            "raw_joints_133": joints_133,
            "body17_raw": body17_raw,
            "canonical_body17": canonical_body17,
            "canonical_body17_zup": canonical_body17_zup,
            "coordinate_conventions": {
                "raw_3d": "x/y image-plane pixels, z relative-depth-like (RTMW3D)",
                "canonical_body17": "X=lateral, Y=up, Z=depth",
                "canonical_body17_zup": "X=lateral, Y=depth, Z=up",
            },
            "canonical_frame": {
                "origin_pelvis": canonical_frame["origin_pelvis"].tolist(),
                "axis_x_lateral": canonical_frame["axis_x_lateral"].tolist(),
                "axis_y_up": canonical_frame["axis_y_up"].tolist(),
                "axis_z_depth": canonical_frame["axis_z_depth"].tolist(),
                "torso_plane_normal": canonical_frame["torso_plane_normal"].tolist(),
                "torso_plane_eigenvalues": canonical_frame["torso_plane_eigenvalues"].tolist(),
                "torso_plane_planarity": float(canonical_frame["torso_plane_planarity"]),
                "yaw_deg": float(canonical_frame["yaw_deg"]),
                "scale_unit": float(canonical_frame["scale_unit"]),
            },
            "ik": ik,
            "quality": quality,
            "invariants": {
                "pelvis_norm_xyz": pelvis_norm,
                "canonical_has_z": bool(np.any(np.abs(np.asarray([j["z"] for j in canonical_body17], dtype=np.float64)) > 1e-6)),
            },
        }

        if parse_bool_flag(args.save_overlay):
            overlay_meta = [
                f"video={video_path.name} frame={frame_idx}/{total_frames - 1}",
                f"det_ms={meta.get('det_ms', float('nan')):.2f} pose_ms={meta.get('pose_ms', float('nan')):.2f}",
                f"det_provider={active_det_providers[0] if active_det_providers else 'unknown'}",
                f"pose_provider={active_pose_providers[0] if active_pose_providers else 'unknown'}",
                f"yaw={payload['canonical_frame']['yaw_deg']:.2f} scale={payload['canonical_frame']['scale_unit']:.3f}",
                f"visible_ratio={quality['visible_ratio_body17']:.2f} min_conf={quality['min_conf_body17']:.2f}",
            ]
            draw_overlay(
                frame_bgr=frame_bgr,
                bbox_xyxy=bbox_xyxy,
                body17_raw=body17_raw,
                out_path=out_dir / "canonical_proof_overlay_latest.png",
                meta_text=overlay_meta,
            )

        save_plot = parse_bool_flag(args.save_plot)
        if save_plot or plot_show:
            plot_3d(
                raw_centered=raw_centered_body17,
                canonical_zup=canonical_body17_zup,
                out_path=out_dir / "canonical_proof_plot_latest.png",
                title_left="Raw pelvis-centered (Z-up iso)",
                title_right="Canonical pelvis-frame (Z-up iso)",
                save_plot=save_plot,
                show_plot=plot_show,
                view_elev=float(args.plot_elev),
                view_azim=float(args.plot_azim),
            )

        if parse_bool_flag(args.save_json):
            write_json(out_dir / "canonical_proof_latest.json", payload)

        if parse_bool_flag(args.save_csv):
            write_angles_csv(
                out_dir / "canonical_proof_angles_latest.csv",
                payload["ik"]["joint_angles_deg"],
                {"video": payload["meta"]["video"], "frame_idx": payload["meta"]["frame_idx"]},
            )
            write_joints_csv(
                out_dir / "canonical_proof_joints_latest.csv",
                body17_raw=body17_raw,
                body17_canonical=canonical_body17,
                body17_canonical_zup=canonical_body17_zup,
            )

        print("status=ok")
        print(f"video={video_path}")
        print(f"frame_idx={frame_idx}")
        print(f"det_provider={active_det_providers}")
        print(f"pose_provider={active_pose_providers}")
        print(f"out_dir={out_dir}")
        return 0

    except Exception as exc:
        payload = build_failure_payload(meta, f"{type(exc).__name__}: {exc}")
        if parse_bool_flag(args.save_json):
            write_json(out_dir / "canonical_proof_latest.json", payload)
        print(f"status=failed reason={exc}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
