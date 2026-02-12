from __future__ import annotations

import os
import queue
import sys
import time
import traceback
import warnings
import logging
from multiprocessing import Queue
from typing import Any, Dict, Optional

from labs.rig_profile import get_coco133_names
from labs.runtime.ipc import SharedFrameReader
from labs.types import PoseJointState, PoseMeasurement, PresetConfig, SharedMemorySpec
import numpy as np

warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.getLogger("mmengine").setLevel(logging.ERROR)
logging.getLogger("mmdet").setLevel(logging.ERROR)


def _ensure_backend_import() -> None:
    backend_path = os.path.join(os.getcwd(), "workspace", "backend")
    if backend_path not in sys.path:
        sys.path.append(backend_path)
    try:
        from mmdet.utils import register_all_modules as _register_all
        _register_all(init_default_scope=True)
    except Exception:
        pass
    try:
        from mmengine.registry import DefaultScope
        try:
            DefaultScope.get_current_instance()
        except Exception:
            DefaultScope.get_instance("mmdet", scope_name="mmdet")
    except Exception:
        pass


def _build_runner(preset: PresetConfig):
    _ensure_backend_import()
    from app.processing.rtmw3d_runtime import RTMW3DRunner

    return RTMW3DRunner(
        model_size="l",
        device="auto",
        backend=preset.backend,
        track_interval=preset.track_interval,
        detector_backend=preset.detector_backend,
        detector_model=preset.detector_model,
        detector_variant=preset.detector_variant,
        pose_variant=preset.pose_variant,
        providers_order=preset.providers_order,
        onnx_artifacts_dir="workspace/backend/models/onnx",
    )


def _build_fallback_detector(preset: PresetConfig):
    _ensure_backend_import()
    from app.processing.onnx_detector_runtime import OnnxDetectorRuntime

    model_path = os.path.join(os.getcwd(), "workspace", "backend", "models", "onnx", "person_foot_detection.onnx")
    if not os.path.exists(model_path):
        return None
    profile = {
        "expects_rgb": True,
        "normalize": False,
        "decoder": "qualcomm_dense_v1",
    }
    return OnnxDetectorRuntime(
        model_path=model_path,
        providers=list(preset.providers_order),
        score_thr=0.35,
        input_size=(640, 480),
        person_class_id=0,
        nms_iou_thr=0.45,
        model_profile=profile,
    )


def _bbox_is_sane(bbox, shape) -> bool:
    if bbox is None:
        return False
    if len(bbox) != 4:
        return False
    h, w = shape[:2]
    x1, y1, x2, y2 = [float(v) for v in bbox]
    if x2 <= x1 or y2 <= y1:
        return False
    bw = x2 - x1
    bh = y2 - y1
    area = bw * bh
    ratio = area / max(1.0, float(w * h))
    if ratio < 0.03 or ratio > 0.98:
        return False
    if bw < 40 or bh < 80:
        return False
    return True


_COCO133_NAMES = get_coco133_names()


def _joint_name(raw_name: str, idx: int) -> str:
    name = str(raw_name or "").strip()
    if name and not name.startswith("kpt_"):
        return name
    if name.startswith("kpt_"):
        try:
            idx = int(name.split("_", 1)[1])
        except Exception:
            pass
    if 0 <= idx < len(_COCO133_NAMES):
        return str(_COCO133_NAMES[idx])
    return name or f"kpt_{idx}"


def _joints_from_pose(pose: Dict[str, Any]) -> list[PoseJointState]:
    out: list[PoseJointState] = []
    for idx, j in enumerate(pose.get("joints", [])):
        name = _joint_name(str(j.get("name", "")), idx)
        out.append(
            PoseJointState(
                name=name,
                x=float(j.get("x", 0.0)),
                y=float(j.get("y", 0.0)),
                z=float(j.get("z", 0.0)),
                c=float(j.get("c", 0.0)),
                px=float(j.get("px", 0.0)),
                py=float(j.get("py", 0.0)),
            )
        )
    return out


def inference_worker_main(
    command_queue: Queue,
    result_queue: Queue,
    preset: PresetConfig,
    shm_spec: SharedMemorySpec,
    mandatory_mode: bool = False,
) -> None:
    reader = None
    runner = None
    fallback_detector = None
    try:
        reader = SharedFrameReader(shm_spec)
        runner = _build_runner(preset)
        fallback_detector = _build_fallback_detector(preset)
        if not runner.ready:
            result_queue.put_nowait(
                {
                    "type": "worker_error",
                    "reason": runner.last_error_reason or "runner_not_ready",
                }
            )
            return
        # Warmup before signaling ready to avoid long first-frame latency.
        try:
            dummy = np.zeros(tuple(shm_spec.frame_shape), dtype=np.uint8)
            wbbox = runner._detect_bbox(dummy)
            if not _bbox_is_sane(wbbox, dummy.shape) and fallback_detector is not None:
                fb = fallback_detector.detect_one(dummy)
                if _bbox_is_sane(fb, dummy.shape):
                    wbbox = fb
            if _bbox_is_sane(wbbox, dummy.shape):
                _ = runner.infer(dummy, bbox_override=wbbox)
            else:
                _ = runner.infer(dummy)
        except Exception:
            pass

        result_queue.put_nowait({"type": "worker_ready"})

        while True:
            try:
                msg = command_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if not isinstance(msg, dict):
                continue
            if msg.get("type") == "stop":
                break
            if msg.get("type") != "frame":
                continue

            frame_idx = int(msg["frame_idx"])
            timestamp_s = float(msg["timestamp_s"])
            enqueue_ts = float(msg.get("enqueue_ts", time.perf_counter()))
            slot_idx = int(msg["slot_idx"])

            frame = reader.read_copy(slot_idx)
            t0 = time.perf_counter()
            bbox = runner._detect_bbox(frame)
            if not _bbox_is_sane(bbox, frame.shape) and fallback_detector is not None:
                fbbox = fallback_detector.detect_one(frame)
                if _bbox_is_sane(fbbox, frame.shape):
                    bbox = fbbox
            pose = runner.infer(frame, bbox_override=bbox) if _bbox_is_sane(bbox, frame.shape) else None
            infer_ms = (time.perf_counter() - t0) * 1000.0
            queue_delay_ms = (time.perf_counter() - enqueue_ts) * 1000.0

            if pose is None:
                meas = PoseMeasurement(
                    frame_idx=frame_idx,
                    timestamp_s=timestamp_s,
                    joints=[],
                    infer_ms=infer_ms,
                    queue_delay_ms=queue_delay_ms,
                    bbox_xyxy=tuple(float(v) for v in bbox) if _bbox_is_sane(bbox, frame.shape) else None,
                    status="failed",
                    reason=runner.last_error_reason or "bbox_invalid_or_infer_none",
                )
            else:
                meas = PoseMeasurement(
                    frame_idx=frame_idx,
                    timestamp_s=timestamp_s,
                    joints=_joints_from_pose(pose),
                    infer_ms=infer_ms,
                    queue_delay_ms=queue_delay_ms,
                    bbox_xyxy=tuple(float(v) for v in bbox) if _bbox_is_sane(bbox, frame.shape) else None,
                    status="ok",
                    reason="",
                )
            try:
                result_queue.put_nowait({"type": "measurement", "payload": meas})
            except queue.Full:
                pass
    except Exception as exc:
        result_queue.put_nowait({"type": "worker_error", "reason": f"{exc}"})
        traceback.print_exc()
    finally:
        if reader is not None:
            reader.close()
