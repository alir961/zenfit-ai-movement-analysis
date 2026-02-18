from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from backend.inference_rtmw3d import RTMW3DEstimator
from backend.inference_yolox import YOLOXDetector
from backend.math_types import Vec3
from backend.postprocess import process_pose
from backend.skeleton_generic import GenericSkeleton
from backend.skeleton_map import RAW17_EDGES, map_raw17_to_humanoid


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse videos into JSONL + NPZ for PyTorch training")
    parser.add_argument("--datasets-dir", default="datasets")
    parser.add_argument("--output-dir", default="datasets")
    parser.add_argument("--det-model", default=None)
    parser.add_argument("--pose-model", default=None)
    parser.add_argument("--label-map", default=None, help="JSON file mapping label_name -> label_id")
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument("--max-frames-per-video", type=int, default=0)
    parser.add_argument("--sequence-len", type=int, default=120)
    parser.add_argument("--sequence-step", type=int, default=30)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-det-score", type=float, default=0.30)
    parser.add_argument("--min-joint-conf", type=float, default=0.35)
    parser.add_argument("--min-valid-joints", type=int, default=17)
    parser.add_argument("--save-preview", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def log(msg: str, verbose: bool = True) -> None:
    if verbose:
        print(msg)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_label_map(path: str | None) -> dict[str, int] | None:
    if not path:
        return None
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("label-map must be a JSON object {label_name: label_id}")
    out: dict[str, int] = {}
    for k, v in data.items():
        out[str(k)] = int(v)
    return out


def infer_label_name(video_path: Path) -> str:
    stem = video_path.stem
    m = re.match(r"^(.*?)(?:_?\d+)$", stem)
    if m and m.group(1):
        return m.group(1).rstrip("_")
    return stem


def resolve_label_id(label_name: str, known_map: dict[str, int] | None, auto_map: dict[str, int]) -> int:
    if known_map is not None:
        if label_name not in known_map:
            raise ValueError(f"label '{label_name}' missing from provided --label-map")
        return int(known_map[label_name])
    if label_name not in auto_map:
        auto_map[label_name] = len(auto_map)
    return auto_map[label_name]


def validate_bbox(bbox_xyxy: Any, width: int, height: int) -> bool:
    if not isinstance(bbox_xyxy, (list, tuple)) or len(bbox_xyxy) != 4:
        return False
    try:
        x1, y1, x2, y2 = [float(v) for v in bbox_xyxy]
    except Exception:
        return False
    if not (x2 > x1 and y2 > y1):
        return False
    if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
        return False
    return True


def compute_quality(
    det: dict[str, Any],
    pose: dict[str, Any],
    frame_wh: tuple[int, int],
    min_det_score: float,
    min_joint_conf: float,
    min_valid_joints: int,
) -> dict[str, Any]:
    w, h = frame_wh
    det_source = str(det.get("source", "unknown"))
    pose_source = str(pose.get("source", "unknown"))
    det_score = float(det.get("score", 0.0))
    bbox_valid = validate_bbox(det.get("bbox_xyxy", [0, 0, 0, 0]), w, h)

    joints = pose.get("joints", []) if isinstance(pose.get("joints", []), list) else []
    confs: list[float] = []
    for j in joints:
        if isinstance(j, (list, tuple)) and len(j) >= 4:
            try:
                confs.append(float(j[3]))
            except Exception:
                confs.append(0.0)

    mean_joint_conf = float(np.mean(confs)) if confs else 0.0
    valid_joint_count = int(sum(c >= min_joint_conf for c in confs))

    reasons: list[str] = []
    score = 1.0

    is_fallback_det = det_source != "onnx"
    is_fallback_pose = pose_source != "onnx"

    if is_fallback_det:
        reasons.append("detector_not_onnx")
        score -= 0.35
    if is_fallback_pose:
        reasons.append("pose_not_onnx")
        score -= 0.35
    if not bbox_valid:
        reasons.append("bbox_invalid")
        score -= 0.20
    if det_score < min_det_score:
        reasons.append("det_score_low")
        score -= 0.15
    if len(joints) != 17:
        reasons.append("joint_count_not_17")
        score -= 0.20
    if mean_joint_conf < min_joint_conf:
        reasons.append("mean_joint_conf_low")
        score -= 0.15
    if valid_joint_count < min_valid_joints:
        reasons.append("valid_joint_count_low")
        score -= 0.15

    score = float(np.clip(score, 0.0, 1.0))

    return {
        "is_fallback_det": bool(is_fallback_det),
        "is_fallback_pose": bool(is_fallback_pose),
        "bbox_valid": bool(bbox_valid),
        "det_score": det_score,
        "mean_joint_conf": mean_joint_conf,
        "valid_joint_count": valid_joint_count,
        "quality_score": score,
        "quality_reasons": reasons,
    }


def extract_transformed_17x7(payload: dict[str, Any]) -> np.ndarray:
    transformed = payload.get("pose_raw17_transformed")
    if not isinstance(transformed, dict):
        raise ValueError("pose_raw17_transformed missing")

    joints = transformed.get("joints")
    if not isinstance(joints, list) or len(joints) != 17:
        raise ValueError("pose_raw17_transformed.joints must have length 17")

    rows: list[list[float]] = []
    for idx, j in enumerate(joints):
        if not isinstance(j, dict):
            raise ValueError(f"pose_raw17_transformed.joints[{idx}] invalid type")
        try:
            x = float(j["x"])
            y = float(j["y"])
            z = float(j["z"])
        except Exception as exc:
            raise ValueError(f"pose_raw17_transformed.joints[{idx}] missing/invalid xyz") from exc
        rows.append([x, y, z, 1.0, 0.0, 0.0, 0.0])
    return np.asarray(rows, dtype=np.float32)


def draw_preview(frame: np.ndarray, det: dict[str, Any], pose: dict[str, Any], quality: dict[str, Any]) -> np.ndarray:
    out = frame.copy()
    bbox = det.get("bbox_xyxy", [0, 0, 0, 0])
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        x1, y1, x2, y2 = [int(float(v)) for v in bbox]
        color = (0, 220, 0) if quality["bbox_valid"] else (0, 0, 255)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)

    joints = pose.get("joints", []) if isinstance(pose.get("joints", []), list) else []
    for a, b in RAW17_EDGES:
        if a < len(joints) and b < len(joints):
            ja = joints[a]
            jb = joints[b]
            if isinstance(ja, (list, tuple)) and isinstance(jb, (list, tuple)) and len(ja) >= 2 and len(jb) >= 2:
                cv2.line(out, (int(float(ja[0])), int(float(ja[1]))), (int(float(jb[0])), int(float(jb[1]))), (0, 180, 255), 1)
    for j in joints:
        if isinstance(j, (list, tuple)) and len(j) >= 4:
            c = float(j[3])
            color = (0, 255, 0) if c >= 0.35 else (0, 128, 255)
            cv2.circle(out, (int(float(j[0])), int(float(j[1]))), 2, color, -1)

    cv2.putText(out, f"q={quality['quality_score']:.2f}", (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    if quality["quality_reasons"]:
        cv2.putText(out, ",".join(quality["quality_reasons"][:3]), (10, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1, cv2.LINE_AA)
    return out


def stratified_split(samples: list[dict[str, Any]], val_ratio: float, seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_label: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for s in samples:
        by_label[int(s["label_id"])].append(s)

    rng = random.Random(seed)
    train: list[dict[str, Any]] = []
    val: list[dict[str, Any]] = []

    for _, group in by_label.items():
        rng.shuffle(group)
        n = len(group)
        n_val = int(round(n * val_ratio))
        if n > 1:
            n_val = min(max(n_val, 1), n - 1)
        else:
            n_val = 0
        val.extend(group[:n_val])
        train.extend(group[n_val:])

    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


def save_npz_split(
    split_name: str,
    split_samples: list[dict[str, Any]],
    samples_dir: Path,
) -> tuple[Path, Path]:
    npz_path = samples_dir / f"{split_name}.npz"
    index_path = samples_dir / f"index_{split_name}.json"

    if split_samples:
        X = np.stack([s["X"] for s in split_samples], axis=0).astype(np.float32)
        y = np.asarray([s["label_id"] for s in split_samples], dtype=np.int64)
    else:
        X = np.zeros((0, 0, 17, 7), dtype=np.float32)
        y = np.zeros((0,), dtype=np.int64)
    meta_idx = np.arange(len(split_samples), dtype=np.int64)

    np.savez(npz_path, X=X, y=y, meta_idx=meta_idx)

    index_payload = []
    for i, s in enumerate(split_samples):
        index_payload.append(
            {
                "sample_id": i,
                "video": s["video"],
                "label_name": s["label_name"],
                "label_id": int(s["label_id"]),
                "start_frame": int(s["start_frame"]),
                "end_frame": int(s["end_frame"]),
                "mean_quality": float(s["mean_quality"]),
                "frames_source_path": s["frames_source_path"],
            }
        )
    index_path.write_text(json.dumps(index_payload, indent=2), encoding="utf-8")
    return npz_path, index_path


def run() -> int:
    args = parse_args()
    start_at = now_iso()

    base_output = Path(args.output_dir)
    videos_dir = base_output / "videos"
    samples_dir = base_output / "samples"
    preview_dir = base_output / "preview"

    videos_dir.mkdir(parents=True, exist_ok=True)
    samples_dir.mkdir(parents=True, exist_ok=True)
    if args.save_preview:
        preview_dir.mkdir(parents=True, exist_ok=True)

    for old in videos_dir.glob("*.jsonl"):
        old.unlink(missing_ok=True)
    for old in samples_dir.glob("*"):
        if old.is_file():
            old.unlink(missing_ok=True)
    if args.save_preview:
        for old in preview_dir.glob("*.jpg"):
            old.unlink(missing_ok=True)

    stats_path = base_output / "stats.json"
    manifest_path = base_output / "manifest.json"

    try:
        label_map_in = load_label_map(args.label_map)
    except Exception as exc:
        stats_path.write_text(
            json.dumps({"ok": False, "error": f"invalid_label_map: {exc}"}, indent=2),
            encoding="utf-8",
        )
        print(f"[parser] FAIL invalid --label-map: {exc}")
        return 1

    log("[parser] initializing models...", True)
    detector = YOLOXDetector(model_path=args.det_model)
    estimator = RTMW3DEstimator(model_path=args.pose_model)

    hard_errors: list[str] = []
    if detector.model_path is None:
        hard_errors.append("detector_model_missing")
    if estimator.model_path is None:
        hard_errors.append("pose_model_missing")
    if detector.session is None or detector.input_name is None:
        hard_errors.append("detector_onnx_not_ready")
    if estimator.session is None or estimator.input_name is None:
        hard_errors.append("pose_onnx_not_ready")

    datasets_dir = Path(args.datasets_dir)
    videos = sorted(datasets_dir.glob("*.mp4"))

    if not videos:
        hard_errors.append("dataset_no_mp4")

    if hard_errors:
        payload = {
            "ok": False,
            "started_at": start_at,
            "ended_at": now_iso(),
            "hard_errors": hard_errors,
            "detector": {
                "model_path": str(detector.model_path) if detector.model_path else None,
                "providers": detector.providers,
                "warnings": detector.warnings,
            },
            "pose_estimator": {
                "model_path": str(estimator.model_path) if estimator.model_path else None,
                "providers": estimator.providers,
                "warnings": estimator.warnings,
            },
        }
        stats_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print("[parser] FAIL precheck:")
        for e in hard_errors:
            print(f"  - {e}")
        return 1

    log(f"[parser] videos found: {len(videos)}", True)

    auto_label_map: dict[str, int] = {}
    error_counts: Counter[str] = Counter()
    quality_scores: list[float] = []
    per_label_frames: Counter[str] = Counter()
    per_label_sequences: Counter[str] = Counter()

    all_sequences: list[dict[str, Any]] = []

    for video_path in videos:
        label_name = infer_label_name(video_path)
        try:
            label_id = resolve_label_id(label_name, label_map_in, auto_label_map)
        except Exception as exc:
            error_counts["label_resolve_failed"] += 1
            log(f"[parser] skip {video_path.name}: {exc}", True)
            continue

        log(f"[parser] video={video_path.name} label={label_name}:{label_id}", True)

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            error_counts["video_open_failed"] += 1
            log("  - fail video open", True)
            continue

        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        video_jsonl = videos_dir / f"{video_path.stem}.jsonl"
        sequence_frames: list[np.ndarray] = []
        sequence_qualities: list[float] = []
        sequence_frame_ids: list[int] = []

        frame_idx = -1
        kept = 0

        with video_jsonl.open("w", encoding="utf-8") as fout:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frame_idx += 1

                if args.stride > 1 and (frame_idx % args.stride != 0):
                    continue
                if args.max_frames_per_video > 0 and kept >= args.max_frames_per_video:
                    break

                kept += 1
                h, w = frame.shape[:2]
                timestamp_ms_est = int((frame_idx / max(fps, 1e-6)) * 1000.0)

                det = detector.detect(frame)
                pose = estimator.predict(frame, det.get("bbox_xyxy", [0, 0, 1, 1]))

                raw17_skeleton = GenericSkeleton.from_coco17_points(pose.get("joints", []))
                raw17_payload = raw17_skeleton.to_payload()
                raw17_joints = raw17_payload["joints"]
                raw17_normalized_easy_payload = GenericSkeleton.easy_normalize_skeleton(raw17_skeleton).to_payload()
                raw17_normalized_full = GenericSkeleton.normalize_skeleton(raw17_skeleton)
                raw17_normalized_full_payload = raw17_normalized_full.to_payload()
                raw17_transformed_payload = GenericSkeleton.with_axis_rotation(
                    raw17_normalized_full.recenter_to_back_center(),
                    axis=Vec3(1.0, 0.0, 0.0),
                    angle_rad=float(np.deg2rad(180.0)),
                    pivot=Vec3(0.0, 0.0, 0.0),
                ).to_payload()

                frame_payload = {
                    "pose_raw17_transformed": {
                        "joints": raw17_transformed_payload["joints"],
                        "edges": raw17_transformed_payload["edges"],
                        "schema": raw17_transformed_payload["schema"],
                        "metadata": raw17_transformed_payload.get("metadata", {}),
                        "source": str(pose.get("source", "unknown")),
                        "mode": "recenter_back_center_then_rotate_x_180deg",
                        "axes_origin": "unchanged_from_input",
                    }
                }

                map_failed = None
                try:
                    mapped_humanoid = map_raw17_to_humanoid(raw17_joints)
                except Exception as exc:
                    mapped_humanoid = {"joints": [], "edges": []}
                    map_failed = str(exc)
                    error_counts["map_failed"] += 1

                pp_failed = None
                try:
                    if mapped_humanoid.get("joints"):
                        pp = process_pose(raw17_joints, mapped_humanoid)
                    else:
                        pp = {
                            "pose_normalized": {
                                "scale_basis": "max_ik_length",
                                "ik_max_length": 1.0,
                                "joints_raw17": raw17_joints,
                                "joints_mapped_humanoid": [],
                            },
                            "postprocess": {
                                "upper_anchor": "none",
                                "ik_max_length": 1.0,
                                "regularization": {
                                    "targets": {},
                                    "limb_lengths_pre": {},
                                    "limb_lengths_post": {},
                                },
                                "surface_vector": [0.0, 0.0, 1.0],
                                "surface_ref": [1.0, 0.0, 1.0],
                                "surface_alignment": 0.0,
                                "yaw_deg": 0.0,
                                "joint_angles_deg": {},
                            },
                            "feature_vector": [0.0],
                        }
                except Exception as exc:
                    pp_failed = str(exc)
                    error_counts["postprocess_failed"] += 1
                    pp = {
                        "pose_normalized": {
                            "scale_basis": "max_ik_length",
                            "ik_max_length": 1.0,
                            "joints_raw17": raw17_joints,
                            "joints_mapped_humanoid": [],
                        },
                        "postprocess": {
                            "upper_anchor": "none",
                            "ik_max_length": 1.0,
                            "regularization": {
                                "targets": {},
                                "limb_lengths_pre": {},
                                "limb_lengths_post": {},
                            },
                            "surface_vector": [0.0, 0.0, 1.0],
                            "surface_ref": [1.0, 0.0, 1.0],
                            "surface_alignment": 0.0,
                            "yaw_deg": 0.0,
                            "joint_angles_deg": {},
                        },
                        "feature_vector": [0.0],
                    }

                quality = compute_quality(
                    det,
                    pose,
                    frame_wh=(w, h),
                    min_det_score=args.min_det_score,
                    min_joint_conf=args.min_joint_conf,
                    min_valid_joints=args.min_valid_joints,
                )
                if map_failed:
                    quality["quality_reasons"].append("map_failed")
                    quality["quality_score"] = float(max(0.0, quality["quality_score"] - 0.1))
                if pp_failed:
                    quality["quality_reasons"].append("postprocess_failed")
                    quality["quality_score"] = float(max(0.0, quality["quality_score"] - 0.1))

                try:
                    feature_17x7 = extract_transformed_17x7(frame_payload)
                except Exception as exc:
                    quality["quality_reasons"].append("transformed_missing_or_invalid")
                    quality["quality_score"] = float(max(0.0, quality["quality_score"] - 0.25))
                    error_counts["transformed_missing_or_invalid"] += 1
                    cap.release()
                    fail_payload = {
                        "ok": False,
                        "started_at": start_at,
                        "ended_at": now_iso(),
                        "error": "transformed_missing_or_invalid",
                        "details": {
                            "video": video_path.name,
                            "frame_index": frame_idx,
                            "reason": str(exc),
                            "quality": quality,
                        },
                        "error_counts": dict(error_counts),
                    }
                    stats_path.write_text(json.dumps(fail_payload, indent=2), encoding="utf-8")
                    manifest_path.write_text(json.dumps(fail_payload, indent=2), encoding="utf-8")
                    print(
                        f"[parser] FAIL transformed_missing_or_invalid "
                        f"video={video_path.name} frame={frame_idx} reason={exc}"
                    )
                    return 1

                quality_scores.append(float(quality["quality_score"]))
                per_label_frames[label_name] += 1

                sequence_frames.append(feature_17x7)
                sequence_qualities.append(float(quality["quality_score"]))
                sequence_frame_ids.append(frame_idx)

                frame_record = {
                    "video": video_path.name,
                    "frame_index": frame_idx,
                    "timestamp_ms_est": timestamp_ms_est,
                    "label_name": label_name,
                    "label_id": int(label_id),
                    "detector": {
                        "bbox_xyxy": det.get("bbox_xyxy", [0, 0, 0, 0]),
                        "score": float(det.get("score", 0.0)),
                        "source": str(det.get("source", "unknown")),
                        "stage_ms": float(det.get("stage_ms", 0.0)),
                        "warnings": list(det.get("warnings", [])),
                    },
                    "pose_raw17": {
                        "joints": raw17_payload["joints"],
                        "edges": raw17_payload["edges"],
                        "schema": raw17_payload["schema"],
                        "source": str(pose.get("source", "unknown")),
                        "stage_ms": float(pose.get("stage_ms", 0.0)),
                        "warnings": list(pose.get("warnings", [])),
                    },
                    "pose_raw17_normalized": {
                        "joints": raw17_normalized_easy_payload["joints"],
                        "edges": raw17_normalized_easy_payload["edges"],
                        "schema": raw17_normalized_easy_payload["schema"],
                        "metadata": raw17_normalized_easy_payload.get("metadata", {}),
                        "source": str(pose.get("source", "unknown")),
                        "mode": "easy_longest_edge_only",
                        "axes_origin": "unchanged_from_input",
                    },
                    "pose_raw17_normalized_full": {
                        "joints": raw17_normalized_full_payload["joints"],
                        "edges": raw17_normalized_full_payload["edges"],
                        "schema": raw17_normalized_full_payload["schema"],
                        "metadata": raw17_normalized_full_payload.get("metadata", {}),
                        "source": str(pose.get("source", "unknown")),
                        "mode": "full_limb_equalization_plus_longest_edge",
                        "axes_origin": "unchanged_from_input",
                    },
                    "pose_raw17_transformed": frame_payload["pose_raw17_transformed"],
                    "pose_mapped_humanoid": mapped_humanoid,
                    "pose_normalized": pp.get("pose_normalized", {}),
                    "postprocess": pp.get("postprocess", {}),
                    "feature_vector": pp.get("feature_vector", []),
                    "quality": quality,
                }
                fout.write(json.dumps(frame_record, ensure_ascii=False) + "\n")

                if args.save_preview and (frame_idx % 100 == 0 or quality["quality_score"] < 0.5):
                    preview = draw_preview(frame, det, pose, quality)
                    p = preview_dir / f"{video_path.stem}_f{frame_idx:06d}.jpg"
                    cv2.imwrite(str(p), preview)

                if args.verbose and kept % 100 == 0:
                    log(f"  - processed {kept} frames", True)

        cap.release()

        n = len(sequence_frames)
        if n >= args.sequence_len:
            for start in range(0, n - args.sequence_len + 1, args.sequence_step):
                end = start + args.sequence_len
                seq_x = np.stack(sequence_frames[start:end], axis=0).astype(np.float32)
                seq_q = float(np.mean(sequence_qualities[start:end]))
                all_sequences.append(
                    {
                        "X": seq_x,
                        "label_id": int(label_id),
                        "label_name": label_name,
                        "video": video_path.name,
                        "start_frame": int(sequence_frame_ids[start]),
                        "end_frame": int(sequence_frame_ids[end - 1]),
                        "mean_quality": seq_q,
                        "frames_source_path": str(video_jsonl),
                    }
                )
                per_label_sequences[label_name] += 1
        else:
            error_counts["video_too_short_for_sequence"] += 1

    if not all_sequences:
        payload = {
            "ok": False,
            "started_at": start_at,
            "ended_at": now_iso(),
            "error": "no_sequences_generated",
            "error_counts": dict(error_counts),
        }
        stats_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print("[parser] FAIL: no sequences generated")
        return 1

    train_samples, val_samples = stratified_split(all_sequences, args.val_ratio, args.seed)

    train_npz, train_index = save_npz_split("train", train_samples, samples_dir)
    val_npz, val_index = save_npz_split("val", val_samples, samples_dir)

    ok = len(train_samples) > 0 and len(val_samples) > 0

    manifest = {
        "ok": ok,
        "feature_schema_version": "raw17_transformed_xyz_plus_identity_quat_v1",
        "created_at": now_iso(),
        "config": {
            "datasets_dir": str(Path(args.datasets_dir)),
            "output_dir": str(Path(args.output_dir)),
            "det_model": str(args.det_model) if args.det_model else None,
            "pose_model": str(args.pose_model) if args.pose_model else None,
            "stride": int(args.stride),
            "max_frames_per_video": int(args.max_frames_per_video),
            "sequence_len": int(args.sequence_len),
            "sequence_step": int(args.sequence_step),
            "val_ratio": float(args.val_ratio),
            "seed": int(args.seed),
            "min_det_score": float(args.min_det_score),
            "min_joint_conf": float(args.min_joint_conf),
            "min_valid_joints": int(args.min_valid_joints),
            "save_preview": bool(args.save_preview),
        },
        "labels": label_map_in if label_map_in is not None else auto_label_map,
        "artifacts": {
            "videos_dir": str(videos_dir),
            "train_npz": str(train_npz),
            "val_npz": str(val_npz),
            "index_train": str(train_index),
            "index_val": str(val_index),
            "stats": str(stats_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    q_arr = np.asarray(quality_scores, dtype=np.float32) if quality_scores else np.asarray([0.0], dtype=np.float32)
    stats = {
        "ok": ok,
        "started_at": start_at,
        "ended_at": now_iso(),
        "videos_total": len(videos),
        "frames_total": int(sum(per_label_frames.values())),
        "sequences_total": len(all_sequences),
        "train_count": len(train_samples),
        "val_count": len(val_samples),
        "quality": {
            "mean": float(q_arr.mean()),
            "min": float(q_arr.min()),
            "max": float(q_arr.max()),
        },
        "per_label_frames": dict(per_label_frames),
        "per_label_sequences": dict(per_label_sequences),
        "error_counts": dict(error_counts),
        "detector": {
            "model_path": str(detector.model_path) if detector.model_path else None,
            "providers": detector.providers,
            "warnings": detector.warnings,
        },
        "pose_estimator": {
            "model_path": str(estimator.model_path) if estimator.model_path else None,
            "providers": estimator.providers,
            "warnings": estimator.warnings,
        },
        "manifest_path": str(manifest_path),
    }
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print(f"[parser] {'PASS' if ok else 'FAIL'}")
    print(f"[parser] frames={stats['frames_total']} sequences={stats['sequences_total']} train={len(train_samples)} val={len(val_samples)}")
    print(f"[parser] manifest={manifest_path}")
    print(f"[parser] stats={stats_path}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(run())
