import csv
import json
import os
import sys
import time

import cv2
import numpy as np
import torch

sys.path.append(os.path.join(os.getcwd(), "workspace", "backend"))
from app.processing.rtmw3d_runtime import RTMW3DRunner

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _ms(t0: float, t1: float) -> float:
    return (t1 - t0) * 1000.0


def _parse_skip_list(raw: str) -> list[int]:
    out = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(max(0, int(part)))
        except ValueError:
            continue
    return out or [0]


def _load_frames(video_path: str, resize_to: tuple[int, int], needed: int) -> list[np.ndarray]:
    cap = cv2.VideoCapture(video_path)
    frames = []
    while len(frames) < needed:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(cv2.resize(frame, resize_to))
    cap.release()
    if not frames:
        raise RuntimeError("Failed to read frame")
    while len(frames) < needed:
        frames.extend(frames[: max(1, needed - len(frames))])
    return frames[:needed]


def benchmark_split(runner: RTMW3DRunner, frames: list[np.ndarray], n: int, skip: int = 0) -> tuple[float, float, float]:
    stride = skip + 1
    cursor = 0
    det_lat = []
    pose_lat = []
    for _ in range(3):
        frame = frames[cursor % len(frames)]
        cursor += stride
        bbox = runner._detect_bbox(frame)
        if bbox is None:
            if runner._onnx_detector_runtime is not None and runner._onnx_detector_runtime.last_error:
                raise RuntimeError(runner._onnx_detector_runtime.last_error)
            raise RuntimeError("det_fail_warmup")
        if runner.use_onnx:
            if runner._infer_onnx(frame, bbox) is None:
                raise RuntimeError("pose_fail_warmup")
        else:
            if runner.infer(frame, bbox_override=bbox) is None:
                raise RuntimeError("pose_fail_warmup")

    for _ in range(n):
        frame = frames[cursor % len(frames)]
        cursor += stride
        t0 = time.perf_counter()
        bbox = runner._detect_bbox(frame)
        t1 = time.perf_counter()
        if bbox is None:
            if runner._onnx_detector_runtime is not None and runner._onnx_detector_runtime.last_error:
                raise RuntimeError(runner._onnx_detector_runtime.last_error)
            raise RuntimeError("det_fail")
        if runner.use_onnx:
            if runner._infer_onnx(frame, bbox) is None:
                raise RuntimeError("pose_fail")
        else:
            if runner.infer(frame, bbox_override=bbox) is None:
                raise RuntimeError("pose_fail")
        t2 = time.perf_counter()
        det_lat.append(_ms(t0, t1))
        pose_lat.append(_ms(t1, t2))

    det_ms = float(np.mean(det_lat))
    pose_ms = float(np.mean(pose_lat))
    total_ms = det_ms + pose_ms
    return det_ms, pose_ms, total_ms


def benchmark_det_only(runner: RTMW3DRunner, frame: np.ndarray, n: int) -> float:
    for _ in range(3):
        if runner._detect_bbox(frame) is None:
            if runner._onnx_detector_runtime is not None and runner._onnx_detector_runtime.last_error:
                raise RuntimeError(runner._onnx_detector_runtime.last_error)
            raise RuntimeError("det_fail_warmup")
    lat = []
    for _ in range(n):
        t0 = time.perf_counter()
        bbox = runner._detect_bbox(frame)
        t1 = time.perf_counter()
        if bbox is None:
            if runner._onnx_detector_runtime is not None and runner._onnx_detector_runtime.last_error:
                raise RuntimeError(runner._onnx_detector_runtime.last_error)
            raise RuntimeError("det_fail")
        lat.append(_ms(t0, t1))
    return float(np.mean(lat))


def benchmark_pose_only(runner: RTMW3DRunner, frame: np.ndarray, n: int) -> float:
    bbox = runner._detect_bbox(frame)
    if bbox is None:
        if runner._onnx_detector_runtime is not None and runner._onnx_detector_runtime.last_error:
            raise RuntimeError(runner._onnx_detector_runtime.last_error)
        raise RuntimeError("det_fail_pose_seed")
    for _ in range(3):
        if runner.infer(frame, bbox_override=bbox) is None:
            raise RuntimeError("pose_fail_warmup")
    lat = []
    for _ in range(n):
        t0 = time.perf_counter()
        if runner.infer(frame, bbox_override=bbox) is None:
            raise RuntimeError("pose_fail")
        t1 = time.perf_counter()
        lat.append(_ms(t0, t1))
    return float(np.mean(lat))


def ensure_benchmark_dir() -> str:
    out = os.path.join("workspace", "backend", "benchmarks")
    os.makedirs(out, exist_ok=True)
    return out


def run():
    print("ULTIMATE FULL ONNX BENCHMARK")
    n = int(os.getenv("ZENFIT_BENCH_N", "12"))
    video = r"docs/squat.mp4"
    skip_list = _parse_skip_list(os.getenv("ZENFIT_SKIP_LIST", "0"))
    print(f"Skip list: {skip_list}")
    max_skip = max(skip_list)
    frames = _load_frames(video, (640, 480), needed=(n + 3) * (max_skip + 1))
    frame = frames[0]

    detectors = ["yolox_tiny_humanart", "yolox_s_humanart", "rtmdet_nano", "rtmdet_tiny", "person_foot_qualcomm"]
    variants = ["fp32", "fp16", "int8"]
    best_only = os.getenv("ZENFIT_BEST_ONLY", "0") == "1"
    env_detectors = os.getenv("ZENFIT_DETECTORS")
    env_det_variants = os.getenv("ZENFIT_DET_VARIANTS")
    env_pose_variants = os.getenv("ZENFIT_POSE_VARIANTS")
    if env_detectors:
        detectors = [x.strip() for x in env_detectors.split(",") if x.strip()]
    det_variants = [x.strip() for x in env_det_variants.split(",")] if env_det_variants else list(variants)
    pose_variants = [x.strip() for x in env_pose_variants.split(",")] if env_pose_variants else list(variants)
    best_combos = {
        ("yolox_tiny_humanart", "fp32", "fp32"),
        ("yolox_tiny_humanart", "fp32", "fp16"),
        ("yolox_s_humanart", "fp32", "fp32"),
        ("yolox_s_humanart", "fp32", "fp16"),
    }
    providers_profiles = {
        "trt_cuda_cpu": ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"],
        "cuda_cpu": ["CUDAExecutionProvider", "CPUExecutionProvider"],
        "cpu": ["CPUExecutionProvider"],
    }
    env_profiles = os.getenv("ZENFIT_PROVIDER_PROFILES")
    if env_profiles:
        keep = {x.strip() for x in env_profiles.split(",") if x.strip()}
        providers_profiles = {k: v for k, v in providers_profiles.items() if k in keep}
        if not providers_profiles:
            providers_profiles = {"cpu": ["CPUExecutionProvider"]}

    rows = []
    for det_model in detectors:
        det_variants_model = list(det_variants)
        if det_model == "person_foot_qualcomm":
            det_variants_model = ["int8"]
        for det_variant in det_variants_model:
            for pose_variant in pose_variants:
                if best_only and (det_model, det_variant, pose_variant) not in best_combos:
                    continue
                for profile_name, providers in providers_profiles.items():
                    for skip in skip_list:
                        print(
                            f"[{det_model}] det={det_variant} pose={pose_variant} providers={profile_name} skip={skip}"
                        )
                        row = {
                            "detector_model": det_model,
                            "detector_variant": det_variant,
                            "pose_variant": pose_variant,
                            "provider_profile": profile_name,
                            "skip": skip,
                            "det_ms": None,
                            "pose_ms": None,
                            "total_ms": None,
                            "fps_split": None,
                            "det_only_ms": None,
                            "det_only_fps": None,
                            "pose_only_ms": None,
                            "pose_only_fps": None,
                            "status": "ok",
                            "reason": "",
                        }
                        try:
                            score_thr = 0.35 if det_model == "person_foot_qualcomm" else 0.05
                            runner = RTMW3DRunner(
                                model_size="l",
                                device="cuda" if torch.cuda.is_available() else "cpu",
                                backend="onnx",
                                track_interval=0,
                                detector_backend="onnx",
                                detector_model=det_model,
                                detector_variant=det_variant,
                                pose_variant=pose_variant,
                                providers_order=providers,
                                onnx_artifacts_dir="workspace/backend/models/onnx",
                                det_score_thr=score_thr,
                                detector_model_path=os.getenv("ZENFIT_DETECTOR_MODEL_PATH") or None,
                            )
                            if not runner.ready:
                                raise RuntimeError(runner.last_error_reason or "runner_not_ready")
                            det_ms, pose_ms, total_ms = benchmark_split(runner, frames, n=n, skip=skip)
                            det_only_ms = benchmark_det_only(runner, frame, n=n)
                            pose_only_ms = benchmark_pose_only(runner, frame, n=n)
                            row["det_ms"] = round(det_ms, 3)
                            row["pose_ms"] = round(pose_ms, 3)
                            row["total_ms"] = round(total_ms, 3)
                            row["fps_split"] = round(1000.0 / total_ms, 3) if total_ms > 0 else 0.0
                            row["det_only_ms"] = round(det_only_ms, 3)
                            row["det_only_fps"] = round(1000.0 / det_only_ms, 3) if det_only_ms > 0 else 0.0
                            row["pose_only_ms"] = round(pose_only_ms, 3)
                            row["pose_only_fps"] = round(1000.0 / pose_only_ms, 3) if pose_only_ms > 0 else 0.0
                        except Exception as exc:
                            row["status"] = "failed"
                            row["reason"] = str(exc)
                        rows.append(row)

    out_dir = ensure_benchmark_dir()
    csv_path = os.path.join(out_dir, "latest_full_onnx.csv")
    json_path = os.path.join(out_dir, "latest_full_onnx.json")
    headers = list(rows[0].keys()) if rows else []

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)

    failed = sum(1 for r in rows if r["status"] != "ok")
    print(f"Done rows={len(rows)} failed={failed}")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    run()
