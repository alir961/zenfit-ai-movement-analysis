import csv
import json
import os
import sys
import time

import cv2
import torch

sys.path.append(os.path.join(os.getcwd(), "workspace", "backend"))

try:
    from app.processing.rtmw3d_runtime import RTMW3DRunner
except ImportError:
    print("Error: Could not import RTMW3DRunner. Run this script from the project root.")
    sys.exit(1)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

VIDEO_PATH = r"docs/squat.mp4"
MODEL_SIZE = "l"


def _parse_skip_list(raw: str) -> list[int]:
    values = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            values.append(max(0, int(item)))
        except ValueError:
            continue
    return values or [0, 1, 3, 5]


def _provider_profiles() -> dict[str, list[str]]:
    profiles = {
        "trt_cuda_cpu": ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"],
        "cuda_cpu": ["CUDAExecutionProvider", "CPUExecutionProvider"],
        "cpu": ["CPUExecutionProvider"],
    }
    env_profiles = os.getenv("ZENFIT_PROVIDER_PROFILES", "cuda_cpu,cpu")
    keep = {x.strip() for x in env_profiles.split(",") if x.strip()}
    filtered = {k: v for k, v in profiles.items() if k in keep}
    return filtered or {"cpu": ["CPUExecutionProvider"]}


def _combo_profiles() -> list[dict]:
    # best = fastest stable combos observed in latest matrix
    best = [
        {"detector_model": "yolox_tiny_humanart", "detector_variant": "fp32", "pose_variant": "fp16"},
        {"detector_model": "yolox_tiny_humanart", "detector_variant": "fp32", "pose_variant": "fp32"},
        {"detector_model": "yolox_s_humanart", "detector_variant": "fp32", "pose_variant": "fp16"},
        {"detector_model": "yolox_s_humanart", "detector_variant": "fp32", "pose_variant": "fp32"},
    ]
    mode = os.getenv("ZENFIT_BENCH_PROFILES", "best").strip().lower()
    if mode == "best":
        return best
    if mode == "single":
        return [best[0]]
    return best


def _run_one(
    runner: RTMW3DRunner,
    skip: int,
    resize_to: tuple[int, int] | None,
) -> tuple[float, float, float, int, int]:
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        raise RuntimeError(f"video_open_failed:{VIDEO_PATH}")

    total_infer = 0.0
    frames_inferred = 0
    frames_read = 0
    skip_counter = 0
    t0 = time.perf_counter()

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames_read += 1
        if skip_counter > 0:
            skip_counter -= 1
            continue
        skip_counter = skip

        if resize_to is not None:
            frame = cv2.resize(frame, resize_to)

        ti0 = time.perf_counter()
        out = runner.infer(frame)
        ti1 = time.perf_counter()
        if out is None:
            continue
        total_infer += (ti1 - ti0)
        frames_inferred += 1

    cap.release()
    elapsed = time.perf_counter() - t0
    if frames_inferred <= 0:
        raise RuntimeError("no_valid_inference")
    fps = frames_read / elapsed if elapsed > 0 else 0.0
    fps_infer = frames_inferred / elapsed if elapsed > 0 else 0.0
    latency_ms = (total_infer / frames_inferred) * 1000.0
    return fps, fps_infer, latency_ms, frames_inferred, frames_read


def _ensure_benchmark_dir() -> str:
    out = os.path.join("workspace", "backend", "benchmarks")
    os.makedirs(out, exist_ok=True)
    return out


def run_benchmark():
    print(f"RTMW3D Matrix Benchmark ({MODEL_SIZE.upper()})")
    if torch.cuda.is_available():
        print(f"CUDA Available: {torch.cuda.get_device_name(0)}")
        torch.backends.cudnn.benchmark = True
    else:
        print("CUDA NOT DETECTED. Using CPU.")

    skip_list = _parse_skip_list(os.getenv("ZENFIT_SKIP_LIST", "0,1,3,5"))
    providers = _provider_profiles()
    combos = _combo_profiles()
    resize_to = None
    resize_env = os.getenv("ZENFIT_RESIZE")
    if resize_env:
        parts = [p.strip() for p in resize_env.split(",")]
        if len(parts) == 2:
            try:
                resize_to = (int(parts[0]), int(parts[1]))
            except ValueError:
                resize_to = None

    rows = []
    for combo in combos:
        for provider_name, provider_order in providers.items():
            for skip in skip_list:
                row = {
                    "detector_model": combo["detector_model"],
                    "detector_variant": combo["detector_variant"],
                    "pose_variant": combo["pose_variant"],
                    "provider_profile": provider_name,
                    "skip": skip,
                    "fps": None,
                    "fps_infer": None,
                    "latency_ms": None,
                    "frames_inferred": None,
                    "frames_read": None,
                    "status": "ok",
                    "reason": "",
                }
                print(
                    f"[{combo['detector_model']}] det={combo['detector_variant']} "
                    f"pose={combo['pose_variant']} providers={provider_name} skip={skip}"
                )
                try:
                    runner = RTMW3DRunner(
                        model_size=MODEL_SIZE,
                        device="cuda" if torch.cuda.is_available() else "cpu",
                        backend="onnx",
                        track_interval=0,
                        detector_backend="onnx",
                        detector_model=combo["detector_model"],
                        detector_variant=combo["detector_variant"],
                        pose_variant=combo["pose_variant"],
                        providers_order=provider_order,
                        onnx_artifacts_dir="workspace/backend/models/onnx",
                        detector_model_path=os.getenv("ZENFIT_DETECTOR_MODEL_PATH") or None,
                    )
                    if not runner.ready:
                        raise RuntimeError(runner.last_error_reason or "runner_not_ready")

                    fps, fps_infer, latency_ms, frames_inferred, frames_read = _run_one(
                        runner=runner,
                        skip=skip,
                        resize_to=resize_to,
                    )
                    row["fps"] = round(fps, 3)
                    row["fps_infer"] = round(fps_infer, 3)
                    row["latency_ms"] = round(latency_ms, 3)
                    row["frames_inferred"] = frames_inferred
                    row["frames_read"] = frames_read
                except Exception as exc:
                    row["status"] = "failed"
                    row["reason"] = str(exc)
                rows.append(row)

    out_dir = _ensure_benchmark_dir()
    csv_path = os.path.join(out_dir, "latest_rtmw3d_matrix.csv")
    json_path = os.path.join(out_dir, "latest_rtmw3d_matrix.json")
    headers = list(rows[0].keys()) if rows else []
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)

    failed = sum(1 for x in rows if x["status"] != "ok")
    print(f"Done rows={len(rows)} failed={failed}")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    if torch.cuda.is_available():
        print(f"Peak GPU Memory: {torch.cuda.max_memory_allocated() / 1024**2:.2f} MB")


if __name__ == "__main__":
    run_benchmark()
