from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import queue
import time
import warnings
from typing import Dict, Optional, Tuple

import cv2

warnings.filterwarnings("ignore", category=DeprecationWarning)

from labs.benchmark.labs_benchmark import LabsBenchmark
from labs.config import make_labs_config
from labs.estimation.fusion import PoseFusionEngine
from labs.rig_profile import get_rig_profile
from labs.estimation.scale_solver import load_calibration_cm_per_unit
from labs.runtime.frame_source import VideoFrameSource
from labs.runtime.inference_worker import inference_worker_main
from labs.runtime.ipc import SharedFrameWriter, queue_put_drop_oldest
from labs.runtime.scheduler import AdaptiveState, FrameScheduler
from labs.viz.camera_renderer import CameraRenderer
from labs.viz.pyplot_animator import run_pyplot_process


def _parse_bool_flag(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _parse_size(value: str | None) -> tuple[int, int] | None:
    if value is None:
        return None
    raw = str(value).strip().lower()
    if raw in ("", "none", "native"):
        return None
    sep = "," if "," in raw else "x"
    parts = [x.strip() for x in raw.split(sep)]
    if len(parts) != 2:
        return None
    try:
        w = max(1, int(parts[0]))
        h = max(1, int(parts[1]))
        return (w, h)
    except ValueError:
        return None


def _drain_result_queue(
    result_queue,
    fusion: PoseFusionEngine | None,
    infer_map: Dict[int, Tuple[float, float, str, str]],
    infer_stats: Dict[str, float],
    raw_measurements: Dict[int, object] | None = None,
    benchmark: LabsBenchmark | None = None,
) -> tuple[Optional[str], int]:
    worker_error = None
    completed_requests = 0
    while True:
        try:
            msg = result_queue.get_nowait()
        except queue.Empty:
            break

        if not isinstance(msg, dict):
            continue
        typ = msg.get("type")
        if typ == "worker_ready":
            infer_stats["ready"] = 1.0
            continue
        if typ == "worker_error":
            worker_error = str(msg.get("reason", "unknown_worker_error"))
            continue
        if typ != "measurement":
            continue
        completed_requests += 1
        meas = msg.get("payload")
        if meas is None:
            continue
        if fusion is not None:
            fusion.ingest_measurement(meas)
        if raw_measurements is not None:
            raw_measurements[int(meas.frame_idx)] = meas
        infer_map[int(meas.frame_idx)] = (
            float(meas.infer_ms),
            float(meas.queue_delay_ms),
            str(meas.status),
            str(meas.reason),
        )
        if str(meas.status) == "ok" and getattr(meas, "joints", None):
            infer_stats["count"] = float(infer_stats.get("count", 0.0) + 1.0)
            infer_stats["last_infer_ms"] = float(meas.infer_ms)
            infer_stats["last_queue_ms"] = float(meas.queue_delay_ms)
            if benchmark is not None:
                benchmark.on_inference_event(float(meas.infer_ms), float(meas.queue_delay_ms))
    return worker_error, completed_requests


def run_labs(args: argparse.Namespace) -> int:
    mandatory_mode = bool(getattr(args, "mandatory", False))
    cfg = make_labs_config(
        video_path=args.video,
        preset_name=args.preset,
        skip_mode=args.skip_mode,
        skip_fixed=args.skip_fixed,
        pyplot=False if mandatory_mode else _parse_bool_flag(args.pyplot),
        ipc=args.ipc,
        scale_mode=args.scale_mode,
        calib_file=args.calib_file,
        benchmark_labs=args.benchmark_labs,
        max_frames=args.max_frames,
        show_ui=(not args.benchmark_labs) if args.show_ui is None else _parse_bool_flag(args.show_ui),
        rig_profile=args.rig_profile,
        plot_space=args.plot_space,
        draw_min_conf=args.draw_min_conf,
        stale_policy=args.stale_policy,
        max_stale_frames=args.max_stale_frames,
        canonical_lock=_parse_bool_flag(args.canonical_lock),
        camera_links=args.camera_links,
        noncore_mode=args.noncore_mode,
        pyplot_rig=args.pyplot_rig,
        show_noncore_points=_parse_bool_flag(args.show_noncore_points),
    )

    frame_source = VideoFrameSource(cfg.video_path)
    first = frame_source.read()
    if first is None:
        print("No frame in video")
        frame_source.release()
        return 1
    _, _, first_frame = first
    runtime_size = _parse_size(args.runtime_size)
    if runtime_size is not None:
        first_frame = cv2.resize(first_frame, runtime_size, interpolation=cv2.INTER_LINEAR)

    scheduler = FrameScheduler(mode=cfg.skip_mode, skip_fixed=cfg.skip_fixed)
    adaptive_state = AdaptiveState()

    rig_profile = get_rig_profile(cfg.rig_profile)
    body17_profile = get_rig_profile("body17")
    camera_profile = get_rig_profile(cfg.camera_links)
    pyplot_profile = get_rig_profile(cfg.pyplot_rig)
    constraint_profile = get_rig_profile("body17")
    fusion: PoseFusionEngine | None = None
    if not mandatory_mode:
        cm_per_unit = load_calibration_cm_per_unit(cfg.calib_file)
        fusion = PoseFusionEngine(
            bone_pairs=constraint_profile.skeleton_links,
            scale_mode=cfg.scale_mode,
            cm_per_unit=cm_per_unit,
            stale_policy=cfg.stale_policy,
            max_stale_frames=cfg.max_stale_frames,
            canonical_lock=cfg.canonical_lock,
            noncore_mode=cfg.noncore_mode,
        )
    renderer = CameraRenderer(
        camera_profile.skeleton_links,
        core_names=body17_profile.keypoint_names,
        keypoint_colors=rig_profile.keypoint_colors,
        link_colors=camera_profile.link_colors,
    )
    benchmark = LabsBenchmark() if cfg.benchmark_labs else None

    frame_shape = tuple(first_frame.shape)
    writer = SharedFrameWriter(frame_shape=frame_shape, slots=cfg.shared_slots)

    command_queue = mp.Queue(maxsize=cfg.queue_size)
    result_queue = mp.Queue(maxsize=cfg.queue_size)
    worker = mp.Process(
        target=inference_worker_main,
        args=(command_queue, result_queue, cfg.preset, writer.spec, mandatory_mode),
        daemon=True,
    )
    worker.start()

    plot_queue = None
    plot_proc = None
    if cfg.pyplot and (not mandatory_mode):
        plot_queue = mp.Queue(maxsize=4)
        plot_proc = mp.Process(
            target=run_pyplot_process,
            args=(
                plot_queue,
                pyplot_profile.skeleton_links,
                body17_profile.keypoint_names,
                rig_profile.keypoint_colors,
                pyplot_profile.link_colors,
                cfg.plot_interval_ms,
                cfg.plot_space,
                cfg.draw_min_conf,
                cfg.show_noncore_points,
            ),
            daemon=True,
        )
        plot_proc.start()

    paused = False
    infer_map: Dict[int, Tuple[float, float, str, str]] = {}
    raw_measurements: Dict[int, object] = {}
    last_raw_joints: list = []
    last_raw_bbox: tuple[float, float, float, float] | None = None
    mandatory_last_status = ""
    dropped_requests_total = 0
    backpressure_skip_total = 0
    inflight_requests = 0
    infer_stats: Dict[str, float] = {"count": 0.0, "last_infer_ms": 0.0, "last_queue_ms": 0.0, "ready": 0.0}
    displayed = 0
    started = 0.0
    last_perf_text = ""
    worker_error = None
    frame_period_s = 1.0 / max(1.0, float(getattr(frame_source, "fps", 30.0) or 30.0))
    global_frame_idx = -1
    core_name_set = set(body17_profile.keypoint_names)

    ready_deadline = time.perf_counter() + max(5.0, float(getattr(args, "worker_ready_timeout", 60.0)))
    while infer_stats.get("ready", 0.0) < 1.0 and time.perf_counter() < ready_deadline:
        drained_error, _ = _drain_result_queue(
            result_queue,
            fusion,
            infer_map,
            infer_stats,
            raw_measurements=raw_measurements,
            benchmark=benchmark,
        )
        if drained_error:
            worker_error = drained_error
            break
        time.sleep(0.01)
    if infer_stats.get("ready", 0.0) < 1.0 and worker_error is None:
        worker_error = "worker_ready_timeout"
    started = time.perf_counter()
    if benchmark is not None:
        benchmark.t0 = started

    pending_frame = first_frame

    try:
        while True:
            loop_t0 = time.perf_counter()

            drained_error, completed_now = _drain_result_queue(
                result_queue,
                fusion,
                infer_map,
                infer_stats,
                raw_measurements=raw_measurements,
                benchmark=benchmark,
            )
            inflight_requests = max(0, int(inflight_requests - completed_now))
            if drained_error:
                worker_error = drained_error

            if pending_frame is None:
                item = frame_source.read()
                if item is None:
                    if bool(getattr(args, "loop", False)):
                        try:
                            frame_source.release()
                        except Exception:
                            pass
                        frame_source = VideoFrameSource(cfg.video_path)
                        frame_period_s = 1.0 / max(1.0, float(getattr(frame_source, "fps", 30.0) or 30.0))
                        item = frame_source.read()
                        if item is None:
                            break
                    else:
                        break
                _, _, frame = item
            else:
                frame = pending_frame
                pending_frame = None

            global_frame_idx += 1
            frame_idx = int(global_frame_idx)
            ts = frame_idx * frame_period_s

            if runtime_size is not None and (frame.shape[1], frame.shape[0]) != runtime_size:
                frame = cv2.resize(frame, runtime_size, interpolation=cv2.INTER_LINEAR)

            if cfg.max_frames is not None and displayed >= cfg.max_frames:
                break

            if not paused:
                should_infer = scheduler.should_infer(frame_idx, adaptive_state)
                dropped_delta = 0
                if should_infer:
                    if inflight_requests < max(1, int(cfg.max_inflight_requests)):
                        slot_idx = frame_idx % cfg.shared_slots
                        writer.write(slot_idx, frame)
                        dropped_delta = queue_put_drop_oldest(
                            command_queue,
                            {
                                "type": "frame",
                                "frame_idx": int(frame_idx),
                                "timestamp_s": float(ts),
                                "slot_idx": int(slot_idx),
                                "enqueue_ts": time.perf_counter(),
                            },
                        )
                        inflight_requests = min(int(cfg.queue_size), inflight_requests + 1)
                        dropped_requests_total += dropped_delta
                    else:
                        backpressure_skip_total += 1
                infer_ms, q_ms, st, reason = infer_map.pop(frame_idx, (0.0, 0.0, "", ""))
                display_infer_ms = float(infer_stats.get("last_infer_ms", 0.0))
                display_q_ms = float(infer_stats.get("last_queue_ms", 0.0))
                if infer_ms > 0.0:
                    adaptive_state.infer_ms = float(infer_ms)
                else:
                    infer_ms = 0.0
                    q_ms = 0.0

                if mandatory_mode:
                    meas = None
                    ready_keys = [k for k in raw_measurements.keys() if k <= frame_idx]
                    if ready_keys:
                        latest_key = max(ready_keys)
                        meas = raw_measurements.pop(latest_key, None)
                        for k in ready_keys:
                            if k != latest_key:
                                raw_measurements.pop(k, None)
                    if meas is not None and str(getattr(meas, "status", "")) == "ok" and getattr(meas, "joints", None):
                        last_raw_joints = list(getattr(meas, "joints", []))
                        last_raw_bbox = getattr(meas, "bbox_xyxy", None)
                        state_source = "measured"
                        mandatory_last_status = ""
                    else:
                        state_source = "hold" if last_raw_joints else "none"
                        if meas is not None and str(getattr(meas, "status", "")) != "ok":
                            mandatory_last_status = str(getattr(meas, "reason", "") or "infer_failed")
                            maybe_bbox = getattr(meas, "bbox_xyxy", None)
                            if maybe_bbox is not None:
                                last_raw_bbox = maybe_bbox
                else:
                    assert fusion is not None
                    estimate = fusion.estimate_for_frame(frame_idx, ts, frame.shape)
                    adaptive_state.motion_score = estimate.quality.motion_score
                    adaptive_state.confidence_score = estimate.quality.median_confidence
            else:
                dropped_delta = 0
                infer_ms = 0.0
                q_ms = 0.0
                st, reason = "", ""
                display_infer_ms = float(infer_stats.get("last_infer_ms", 0.0))
                display_q_ms = float(infer_stats.get("last_queue_ms", 0.0))
                if mandatory_mode:
                    state_source = "pause_hold" if last_raw_joints else "none"
                else:
                    assert fusion is not None
                    estimate = fusion.estimate_for_frame(frame_idx, ts, frame.shape)

            elapsed = max(1e-6, time.perf_counter() - started)
            displayed += 1
            fps_display = displayed / elapsed
            fps_infer = float(infer_stats.get("count", 0.0)) / elapsed
            last_perf_text = (
                f"fps={fps_display:.1f} infer_ms={display_infer_ms:.1f} queue_ms={display_q_ms:.1f} "
                f"drop={dropped_requests_total} bp_skip={backpressure_skip_total}"
            )

            if mandatory_mode:
                status_text = mandatory_last_status
                if st and st != "ok":
                    status_text = reason or st
                vis = renderer.render_raw_points(
                    frame,
                    last_raw_joints,
                    perf_text=last_perf_text,
                    status_text=status_text,
                    conf_thr=float(cfg.draw_min_conf),
                    bbox_xyxy=last_raw_bbox,
                    rig_name=cfg.camera_links,
                    show_noncore_points=cfg.show_noncore_points,
                )
            else:
                vis = renderer.render(
                    frame,
                    estimate,
                    perf_text=last_perf_text,
                    draw_min_conf=float(cfg.draw_min_conf),
                    rig_name=cfg.camera_links,
                    show_noncore_points=cfg.show_noncore_points,
                )
            if worker_error:
                cv2.putText(vis, f"worker_error: {worker_error}", (20, 28), cv2.FONT_HERSHEY_DUPLEX, 0.6, (0, 0, 255), 1)

            if cfg.show_ui:
                cv2.imshow("ZenFit Labs V3", vis)

            if (not mandatory_mode) and plot_queue is not None:
                payload = {
                    "type": "state",
                    "payload": {
                        "frame_idx": frame_idx,
                        "source": estimate.source,
                        "quality": estimate.quality.score,
                        "flags": estimate.scale.quality_flags,
                        "raw_joints": [j.__dict__ for j in estimate.joints],
                        "fused_body17_joints": [j.__dict__ for j in estimate.fused_body17_joints],
                        "canonical_joints": [j.__dict__ for j in estimate.normalized_joints],
                        "measurement_age_frames": int(estimate.measurement_age_frames),
                        "noncore_age_frames": int(estimate.noncore_age_frames),
                        "queue_delay_ms": float(estimate.queue_delay_ms),
                        "canonical_yaw_deg": float(estimate.canonical_yaw_deg),
                    },
                }
                queue_put_drop_oldest(plot_queue, payload)

            loop_ms = (time.perf_counter() - loop_t0) * 1000.0
            if benchmark is not None:
                core_vis = 0.0
                noncore_vis = 0.0
                noncore_age = 0
                if not mandatory_mode:
                    core_confs = [j.c for j in estimate.fused_body17_joints if j.name in core_name_set]
                    if core_confs:
                        core_vis = float(sum(c >= cfg.draw_min_conf for c in core_confs) / len(core_confs))
                    noncore = [j for j in estimate.joints if j.name not in core_name_set]
                    if noncore:
                        noncore_vis = float(sum(j.c >= cfg.draw_min_conf for j in noncore) / len(noncore))
                    noncore_age = int(estimate.noncore_age_frames)
                benchmark.on_frame(
                    frame_idx=frame_idx,
                    source=state_source if mandatory_mode else estimate.source,
                    loop_ms=loop_ms,
                    infer_ms=infer_ms,
                    queue_delay_ms=q_ms,
                    dropped_requests=dropped_delta,
                    core17_visible_ratio=core_vis,
                    noncore_visible_ratio=noncore_vis,
                    noncore_age_frames=noncore_age,
                )

            if cfg.show_ui:
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key == ord(" "):
                    paused = not paused

            # Pace playback for local video files so visual flow matches source FPS.
            if cfg.show_ui and (not cfg.benchmark_labs):
                elapsed_loop = time.perf_counter() - loop_t0
                remaining = frame_period_s - elapsed_loop
                if remaining > 0:
                    time.sleep(remaining)

    finally:
        try:
            command_queue.put_nowait({"type": "stop"})
        except Exception:
            pass
        if plot_queue is not None:
            try:
                plot_queue.put_nowait({"type": "stop"})
            except Exception:
                pass

        if worker.is_alive():
            worker.join(timeout=1.5)
            if worker.is_alive():
                worker.terminate()
        if plot_proc is not None and plot_proc.is_alive():
            plot_proc.join(timeout=1.0)
            if plot_proc.is_alive():
                plot_proc.terminate()

        writer.close()
        writer.unlink()
        frame_source.release()
        cv2.destroyAllWindows()

    if benchmark is not None:
        csv_path, json_path = benchmark.export()
        print("Benchmark summary:", benchmark.summary())
        print("CSV:", csv_path)
        print("JSON:", json_path)

    if worker_error:
        print("Worker error:", worker_error)
        return 2

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ZenFit Labs V3")
    parser.add_argument("--video", type=str, default=r"docs/squat.mp4")
    parser.add_argument("--preset", type=str, default="yolox_s_fp32_fp32_cuda_skip3")
    parser.add_argument("--skip-mode", type=str, default="fixed", choices=["fixed", "adaptive"])
    parser.add_argument("--skip-fixed", type=int, default=3)
    parser.add_argument("--rig-profile", type=str, default="coco133", choices=["body17", "coco133"])
    parser.add_argument("--plot-space", type=str, default="canonical", choices=["raw", "canonical", "both"])
    parser.add_argument("--draw-min-conf", type=float, default=0.05)
    parser.add_argument("--stale-policy", type=str, default="graceful", choices=["strict", "graceful"])
    parser.add_argument("--max-stale-frames", type=int, default=45)
    parser.add_argument("--canonical-lock", type=str, default="on", choices=["on", "off"])
    parser.add_argument("--camera-links", type=str, default="body17", choices=["body17", "coco133"])
    parser.add_argument("--noncore-mode", type=str, default="hold", choices=["hold", "predict", "drop"])
    parser.add_argument("--pyplot-rig", type=str, default="body17", choices=["body17", "coco133"])
    parser.add_argument("--show-noncore-points", type=str, default="on", choices=["on", "off"])
    parser.add_argument("--pyplot", type=str, default="on", choices=["on", "off"])
    parser.add_argument("--ipc", type=str, default="shm_queue", choices=["shm_queue"])
    parser.add_argument("--scale-mode", type=str, default="uncalibrated", choices=["calibrated", "uncalibrated"])
    parser.add_argument("--calib-file", type=str, default=None)
    parser.add_argument("--benchmark-labs", action="store_true")
    parser.add_argument("--mandatory", action="store_true")
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--runtime-size", type=str, default="640,480")
    parser.add_argument("--show-ui", type=str, default=None, choices=["on", "off"])
    parser.add_argument("--worker-ready-timeout", type=float, default=60.0)
    parser.add_argument("--loop", action="store_true")
    return parser


if __name__ == "__main__":
    try:
        if mp.get_start_method(allow_none=True) != "spawn":
            mp.set_start_method("spawn", force=True)
    except RuntimeError:
        pass

    args = build_parser().parse_args()
    if not os.path.exists(args.video):
        print(f"Video not found: {args.video}")
        raise SystemExit(1)

    raise SystemExit(run_labs(args))
