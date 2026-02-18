from __future__ import annotations

import argparse
import json
import logging
import random
import traceback
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from backend.camera_stream import CameraStreamManager
from backend.inference_rtmw3d import RTMW3DEstimator
from backend.inference_yolox import YOLOXDetector
from backend.zenfit_state import Zenfit


@dataclass
class FrameResult:
    video: str
    frame_index: int
    status: str
    reasons: list[str]
    det_source: str
    pose_source: str
    det_score: float
    mean_joint_conf: float
    valid_joint_count: int
    det_stage_ms: float
    pose_stage_ms: float
    warnings: list[str]
    image_path: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Strict ONNX test runner for YOLOXDetector + RTMW3DEstimator"
    )
    parser.add_argument("--datasets-dir", default="datasets", help="Directory with .mp4 files")
    parser.add_argument(
        "--output-dir",
        default="speedy_learning/runs/test_report",
        help="Output report directory",
    )
    parser.add_argument("--samples-per-video", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-det-score", type=float, default=0.1)
    parser.add_argument("--min-joint-conf", type=float, default=0.1)
    parser.add_argument("--min-valid-joints", type=int, default=17)
    parser.add_argument("--max-fail-ratio", type=float, default=0.05)
    parser.add_argument("--det-model", default=None)
    parser.add_argument("--pose-model", default=None)
    parser.add_argument("--save-ok-images", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "min": None, "max": None}
    arr = np.array(values, dtype=np.float64)
    return {
        "mean": float(arr.mean()),
        "min": float(arr.min()),
        "max": float(arr.max()),
    }


def _validate_bbox(bbox_xyxy: Any, width: int, height: int) -> tuple[bool, list[str], tuple[int, int, int, int]]:
    reasons: list[str] = []
    if not isinstance(bbox_xyxy, (list, tuple)) or len(bbox_xyxy) != 4:
        reasons.append("bbox_format_invalid")
        return False, reasons, (0, 0, 0, 0)

    x1, y1, x2, y2 = [_safe_float(v, np.nan) for v in bbox_xyxy]
    if any(np.isnan([x1, y1, x2, y2])):
        reasons.append("bbox_nan")
        return False, reasons, (0, 0, 0, 0)

    if not (x2 > x1 and y2 > y1):
        reasons.append("bbox_non_positive_area")

    if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
        reasons.append("bbox_out_of_bounds")

    return len(reasons) == 0, reasons, (int(x1), int(y1), int(x2), int(y2))


def _extract_joint_conf(joints: Any) -> tuple[bool, list[str], list[float]]:
    reasons: list[str] = []
    confs: list[float] = []

    if not isinstance(joints, list):
        reasons.append("pose_joints_not_list")
        return False, reasons, confs

    if len(joints) != 17:
        reasons.append("pose_joint_count_not_17")
        return False, reasons, confs

    for idx, joint in enumerate(joints):
        if not isinstance(joint, dict):
            reasons.append(f"joint_{idx}_format_invalid")
            continue
        conf = _safe_float(joint.get("confidence", np.nan), np.nan)
        if np.isnan(conf):
            reasons.append(f"joint_{idx}_conf_nan")
            continue
        confs.append(conf)

    return len(reasons) == 0, reasons, confs


def _draw_overlay(
    frame_bgr: np.ndarray,
    det: dict[str, Any],
    pose: dict[str, Any],
    status: str,
    reasons: list[str],
) -> np.ndarray:
    out = frame_bgr.copy()
    h, w = out.shape[:2]

    bbox = det.get("bbox_xyxy", [0, 0, 0, 0])
    ok_bbox, _, (x1, y1, x2, y2) = _validate_bbox(bbox, w, h)
    color = (0, 220, 0) if ok_bbox else (0, 0, 255)
    cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)

    det_score = _safe_float(det.get("score", 0.0), 0.0)
    det_stage_ms = _safe_float(det.get("stage_ms", 0.0), 0.0)
    pose_stage_ms = _safe_float(pose.get("stage_ms", 0.0), 0.0)

    joints = pose.get("joints", []) if isinstance(pose.get("joints", []), list) else []
    edges = pose.get("edges", []) if isinstance(pose.get("edges", []), list) else []
    for edge in edges:
        a = int(edge.get("a", -1))
        b = int(edge.get("b", -1))
        if a < len(joints) and b < len(joints):
            ja = joints[a]
            jb = joints[b]
            if isinstance(ja, dict) and isinstance(jb, dict):
                cv2.line(
                    out,
                    (int(_safe_float(ja.get("x", 0.0), 0.0)), int(_safe_float(ja.get("y", 0.0), 0.0))),
                    (int(_safe_float(jb.get("x", 0.0), 0.0)), int(_safe_float(jb.get("y", 0.0), 0.0))),
                    (0, 180, 255),
                    1,
                )
    for joint in joints:
        if isinstance(joint, dict):
            x = int(_safe_float(joint.get("x", 0.0), 0.0))
            y = int(_safe_float(joint.get("y", 0.0), 0.0))
            c = _safe_float(joint.get("confidence", 0.0), 0.0)
            point_color = (0, 255, 0) if c >= 0.35 else (0, 64, 255)
            cv2.circle(out, (x, y), 2, point_color, -1)

    status_color = (0, 220, 0) if status == "PASS" else (0, 0, 255)
    cv2.putText(out, f"{status}", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2, cv2.LINE_AA)
    cv2.putText(
        out,
        f"det_score={det_score:.3f} det_ms={det_stage_ms:.1f} pose_ms={pose_stage_ms:.1f}",
        (10, 46),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    if reasons:
        cv2.putText(
            out,
            "reasons=" + ",".join(reasons[:4]),
            (10, 68),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 200, 255),
            1,
            cv2.LINE_AA,
        )
    return out


def _log(msg: str, verbose: bool = True) -> None:
    if verbose:
        print(msg)


def _sample_frame_indices(frame_count: int, sample_count: int, rng: random.Random) -> list[int]:
    n = min(sample_count, frame_count)
    if n <= 0:
        return []
    return sorted(rng.sample(range(frame_count), n))


def run() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger = logging.getLogger("speedy_learning.run_test")
    rng = random.Random(args.seed)

    datasets_dir = Path(args.datasets_dir)
    output_dir = Path(args.output_dir)
    images_fail_dir = output_dir / "images" / "fail"
    images_pass_dir = output_dir / "images" / "pass"

    output_dir.mkdir(parents=True, exist_ok=True)
    images_fail_dir.mkdir(parents=True, exist_ok=True)
    images_pass_dir.mkdir(parents=True, exist_ok=True)

    start_ts = datetime.now(timezone.utc).isoformat()

    hard_errors: list[str] = []
    error_types: Counter[str] = Counter()
    frame_results: list[FrameResult] = []
    det_scores: list[float] = []
    mean_confs: list[float] = []

    _log("[run_test] Initializing detector/pose estimator...", True)
    detector = YOLOXDetector(model_path=args.det_model)
    estimator = RTMW3DEstimator(model_path=args.pose_model)
    zenfit = Zenfit(
        csm=CameraStreamManager(max_buffer=8),
        bbox_detector=detector,
        pose_estimator=estimator,
        logger=logger,
        debug_dir=Path("speedy_learning/logs/debug_frames"),
    )

    if detector.model_path is None:
        hard_errors.append("detector_model_missing")
    if estimator.model_path is None:
        hard_errors.append("pose_model_missing")
    if detector.session is None or detector.input_name is None:
        hard_errors.append("detector_onnx_not_ready")
    if estimator.session is None or estimator.input_name is None:
        hard_errors.append("pose_onnx_not_ready")

    if hard_errors:
        for err in hard_errors:
            error_types[err] += 1
        summary = {
            "ok": False,
            "reason": "init_precheck_failed",
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
            "started_at": start_ts,
            "ended_at": datetime.now(timezone.utc).isoformat(),
        }
        (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (output_dir / "report.txt").write_text(
            "RUN_TEST FAILED (precheck)\n"
            + f"hard_errors={hard_errors}\n"
            + f"detector_warnings={detector.warnings}\n"
            + f"pose_warnings={estimator.warnings}\n",
            encoding="utf-8",
        )
        print("[run_test] FAIL: strict ONNX precheck failed")
        for err in hard_errors:
            print(f"  - {err}")
        return 1

    videos = sorted(datasets_dir.glob("*.mp4"))
    if not videos:
        error_types["dataset_no_mp4"] += 1
        summary = {
            "ok": False,
            "reason": "dataset_no_mp4",
            "datasets_dir": str(datasets_dir),
            "started_at": start_ts,
            "ended_at": datetime.now(timezone.utc).isoformat(),
        }
        (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (output_dir / "report.txt").write_text(
            "RUN_TEST FAILED\nNo .mp4 files found\n",
            encoding="utf-8",
        )
        print("[run_test] FAIL: no .mp4 files found")
        return 1

    _log(f"[run_test] Found {len(videos)} video(s) in {datasets_dir}", True)

    for video_path in videos:
        _log(f"[run_test] Video: {video_path.name}", True)
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            error_types["video_open_failed"] += 1
            hard_errors.append(f"video_open_failed:{video_path.name}")
            _log("  - FAIL: cannot open video", True)
            continue

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_count <= 0:
            error_types["video_frame_count_invalid"] += 1
            hard_errors.append(f"video_frame_count_invalid:{video_path.name}")
            _log("  - FAIL: invalid frame count", True)
            cap.release()
            continue

        indices = _sample_frame_indices(frame_count, args.samples_per_video, rng)
        _log(f"  - sampled frames: {indices}", args.verbose)

        for idx in indices:
            reasons: list[str] = []
            det: dict[str, Any] = {}
            pose: dict[str, Any] = {}
            status = "PASS"
            image_path: str | None = None

            try:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ok, frame = cap.read()
                if not ok or frame is None:
                    reasons.append("frame_read_failed")
                    error_types["frame_read_failed"] += 1
                    status = "FAIL"
                    out = np.zeros((240, 320, 3), dtype=np.uint8)
                    cv2.putText(out, f"FAIL frame read: {video_path.name}:{idx}", (8, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1, cv2.LINE_AA)
                    save_path = images_fail_dir / f"{video_path.stem}_f{idx:06d}_fail.jpg"
                    cv2.imwrite(str(save_path), out)
                    image_path = str(save_path)
                    frame_results.append(
                        FrameResult(
                            video=video_path.name,
                            frame_index=idx,
                            status=status,
                            reasons=reasons,
                            det_source="unknown",
                            pose_source="unknown",
                            det_score=0.0,
                            mean_joint_conf=0.0,
                            valid_joint_count=0,
                            det_stage_ms=0.0,
                            pose_stage_ms=0.0,
                            warnings=[],
                            image_path=image_path,
                        )
                    )
                    continue

                h, w = frame.shape[:2]
                payload = zenfit.run_pose(frame)
                det = payload.get("detector", {})
                pose = payload.get("pose_raw17", {})

                det_source = str(det.get("source", "unknown"))
                pose_source = str(pose.get("source", "unknown"))
                det_score = _safe_float(det.get("score", 0.0), 0.0)
                det_stage_ms = _safe_float(payload.get("debug", {}).get("stage_timings_ms", {}).get("detector_ms", 0.0), 0.0)
                pose_stage_ms = _safe_float(payload.get("debug", {}).get("stage_timings_ms", {}).get("pose_ms", 0.0), 0.0)

                if det_source != "onnx":
                    reasons.append("det_source_not_onnx")
                    error_types["det_source_not_onnx"] += 1
                    hard_errors.append(f"fallback_detected:{video_path.name}:{idx}")

                if pose_source != "onnx":
                    reasons.append("pose_source_not_onnx")
                    error_types["pose_source_not_onnx"] += 1
                    hard_errors.append(f"fallback_detected:{video_path.name}:{idx}")

                bbox_ok, bbox_reasons, _ = _validate_bbox(det.get("bbox_xyxy", [0, 0, 0, 0]), w, h)
                if not bbox_ok:
                    reasons.extend(bbox_reasons)
                    for r in bbox_reasons:
                        error_types[r] += 1

                if det_score < args.min_det_score:
                    reasons.append("det_score_below_threshold")
                    error_types["det_score_below_threshold"] += 1

                joints_ok, joint_reasons, confs = _extract_joint_conf(pose.get("joints", []))
                if not joints_ok:
                    reasons.extend(joint_reasons)
                    for r in joint_reasons:
                        error_types[r] += 1

                if str(pose.get("schema", "")) != "Raw17SkeletonV2":
                    reasons.append("pose_schema_not_raw17_v2")
                    error_types["pose_schema_not_raw17_v2"] += 1

                mean_conf = float(np.mean(confs)) if confs else 0.0
                valid_count = int(sum(c >= args.min_joint_conf for c in confs)) if confs else 0

                if mean_conf < args.min_joint_conf:
                    reasons.append("mean_joint_conf_below_threshold")
                    error_types["mean_joint_conf_below_threshold"] += 1

                if valid_count < args.min_valid_joints:
                    reasons.append("valid_joint_count_below_threshold")
                    error_types["valid_joint_count_below_threshold"] += 1

                if reasons:
                    status = "FAIL"

                if status == "PASS":
                    det_scores.append(det_score)
                    mean_confs.append(mean_conf)

                out = _draw_overlay(frame, det, pose, status, reasons)
                should_save = status == "FAIL" or args.save_ok_images
                if should_save:
                    subdir = images_fail_dir if status == "FAIL" else images_pass_dir
                    suffix = "fail" if status == "FAIL" else "pass"
                    save_path = subdir / f"{video_path.stem}_f{idx:06d}_{suffix}.jpg"
                    cv2.imwrite(str(save_path), out)
                    image_path = str(save_path)

                if args.verbose:
                    print(
                        f"    frame {idx}: {status} "
                        f"(det={det_score:.3f}, mean_conf={mean_conf:.3f}, valid={valid_count}/17)"
                    )
                    if reasons:
                        print(f"      reasons={reasons}")

                frame_results.append(
                    FrameResult(
                        video=video_path.name,
                        frame_index=idx,
                        status=status,
                        reasons=reasons,
                        det_source=det_source,
                        pose_source=pose_source,
                        det_score=det_score,
                        mean_joint_conf=mean_conf,
                        valid_joint_count=valid_count,
                        det_stage_ms=det_stage_ms,
                        pose_stage_ms=pose_stage_ms,
                        warnings=list(payload.get("debug", {}).get("warnings", [])),
                        image_path=image_path,
                    )
                )
            except Exception:
                status = "FAIL"
                reasons = ["runtime_exception"]
                error_types["runtime_exception"] += 1
                hard_errors.append(f"runtime_exception:{video_path.name}:{idx}")

                tb = traceback.format_exc()
                if args.verbose:
                    print(tb)

                frame_results.append(
                    FrameResult(
                        video=video_path.name,
                        frame_index=idx,
                        status=status,
                        reasons=reasons,
                        det_source=str(det.get("source", "unknown")) if isinstance(det, dict) else "unknown",
                        pose_source=str(pose.get("source", "unknown")) if isinstance(pose, dict) else "unknown",
                        det_score=_safe_float(det.get("score", 0.0), 0.0) if isinstance(det, dict) else 0.0,
                        mean_joint_conf=0.0,
                        valid_joint_count=0,
                        det_stage_ms=_safe_float(det.get("stage_ms", 0.0), 0.0) if isinstance(det, dict) else 0.0,
                        pose_stage_ms=_safe_float(pose.get("stage_ms", 0.0), 0.0) if isinstance(pose, dict) else 0.0,
                        warnings=[tb],
                        image_path=None,
                    )
                )

        cap.release()

    total_frames = len(frame_results)
    fail_count = sum(1 for r in frame_results if r.status == "FAIL")
    pass_count = total_frames - fail_count
    fail_ratio = float(fail_count / total_frames) if total_frames > 0 else 1.0

    has_hard_errors = len(hard_errors) > 0
    ok = (fail_ratio <= args.max_fail_ratio) and (not has_hard_errors) and (total_frames > 0)

    det_score_values = [r.det_score for r in frame_results]
    conf_values = [r.mean_joint_conf for r in frame_results]

    summary: dict[str, Any] = {
        "ok": ok,
        "strict_onnx": True,
        "config": {
            "datasets_dir": str(datasets_dir),
            "output_dir": str(output_dir),
            "samples_per_video": args.samples_per_video,
            "seed": args.seed,
            "min_det_score": args.min_det_score,
            "min_joint_conf": args.min_joint_conf,
            "min_valid_joints": args.min_valid_joints,
            "max_fail_ratio": args.max_fail_ratio,
            "det_model": str(args.det_model) if args.det_model else None,
            "pose_model": str(args.pose_model) if args.pose_model else None,
            "save_ok_images": bool(args.save_ok_images),
        },
        "detector": {
            "model_path": str(detector.model_path) if detector.model_path else None,
            "providers": zenfit.bbox_detector.providers,
            "warnings": detector.warnings,
        },
        "pose_estimator": {
            "model_path": str(estimator.model_path) if estimator.model_path else None,
            "providers": zenfit.pose_estimator.providers,
            "warnings": estimator.warnings,
        },
        "metrics": {
            "videos_total": len(videos),
            "frames_total": total_frames,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "fail_ratio": fail_ratio,
            "det_score": _stats(det_score_values),
            "det_score_pass_only": _stats(det_scores),
            "mean_joint_conf": _stats(conf_values),
            "mean_joint_conf_pass_only": _stats(mean_confs),
        },
        "error_types": dict(error_types),
        "hard_errors": hard_errors,
        "frame_results": [r.__dict__ for r in frame_results],
        "started_at": start_ts,
        "ended_at": datetime.now(timezone.utc).isoformat(),
    }

    summary_path = output_dir / "summary.json"
    report_path = output_dir / "report.txt"

    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report_lines = [
        f"RUN_TEST {'PASS' if ok else 'FAIL'}",
        "",
        f"videos_total={len(videos)}",
        f"frames_total={total_frames}",
        f"pass_count={pass_count}",
        f"fail_count={fail_count}",
        f"fail_ratio={fail_ratio:.4f} (max={args.max_fail_ratio:.4f})",
        f"hard_errors_count={len(hard_errors)}",
        f"detector_providers={detector.providers}",
        f"pose_providers={estimator.providers}",
        f"summary_json={summary_path}",
        "",
        "Error types:",
    ]
    if error_types:
        for name, count in error_types.most_common():
            report_lines.append(f"- {name}: {count}")
    else:
        report_lines.append("- none")

    if hard_errors:
        report_lines.append("")
        report_lines.append("Hard errors:")
        for err in hard_errors[:100]:
            report_lines.append(f"- {err}")

    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"[run_test] {'PASS' if ok else 'FAIL'}")
    print(f"[run_test] videos={len(videos)} frames={total_frames} fails={fail_count} fail_ratio={fail_ratio:.4f}")
    print(f"[run_test] report={report_path}")
    print(f"[run_test] summary={summary_path}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(run())
