from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any, Dict

import numpy as np
import socketio
import os
import cv2

from .contracts import events
from .processing.rtmw3d_runtime import RTMW3DRunner
from .processing.normalize import normalize_pose
from .processing.metrics import compute_metrics
from .processing.classify import ExerciseClassifier

logger = logging.getLogger("zenfit.socket")

_cors_raw = os.getenv("ZENFIT_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").strip()
_cors_origins = "*" if _cors_raw == "*" else [o.strip() for o in _cors_raw.split(",") if o.strip()]

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=_cors_origins)
app = socketio.ASGIApp(sio)

_det_input_size = None
_det_input_raw = os.getenv("ZENFIT_DET_INPUT_SIZE")
if _det_input_raw:
    try:
        parts = [int(p.strip()) for p in _det_input_raw.split(",") if p.strip()]
        if len(parts) == 2:
            _det_input_size = (parts[0], parts[1])
    except Exception:
        _det_input_size = None

_providers_raw = os.getenv("ZENFIT_ORT_PROVIDERS", "").strip()
_providers = [p.strip() for p in _providers_raw.split(",") if p.strip()] or None

runner = RTMW3DRunner(
    model_size=os.getenv("ZENFIT_MODEL_SIZE", "l"),
    device=os.getenv("ZENFIT_DEVICE", "auto"),
    detector=os.getenv("ZENFIT_DETECTOR", "rtmdet"),
    det_config=os.getenv("ZENFIT_DET_CONFIG") or None,
    det_checkpoint=os.getenv("ZENFIT_DET_CHECKPOINT") or None,
    det_score_thr=float(os.getenv("ZENFIT_DET_SCORE_THR", "0.5")),
    det_input_size=_det_input_size,
    detector_backend=os.getenv("ZENFIT_DETECTOR_BACKEND", "auto"),
    detector_model=os.getenv("ZENFIT_DETECTOR_MODEL", "rtmdet_tiny"),
    detector_variant=os.getenv("ZENFIT_DETECTOR_VARIANT", "fp16"),
    pose_variant=os.getenv("ZENFIT_POSE_VARIANT", "fp16"),
    providers_order=_providers,
    onnx_artifacts_dir=os.getenv("ZENFIT_ONNX_ARTIFACTS_DIR", "workspace/backend/models/onnx"),
    detector_model_path=os.getenv("ZENFIT_DETECTOR_MODEL_PATH") or None,
)
classifiers: Dict[str, ExerciseClassifier] = {}
# Inference is CPU/GPU bound: run it off the event loop, one frame at a time.
_infer_lock = asyncio.Lock()


def _decode_image(payload: Dict[str, Any]) -> np.ndarray | None:
    image = payload.get("image")

    if image is None:
        return None

    if isinstance(image, (bytes, bytearray)):
        image_bytes = bytes(image)
    elif isinstance(image, str) and image.startswith("data:image"):
        _, b64_data = image.split(",", 1)
        image_bytes = base64.b64decode(b64_data)
    else:
        return None

    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    return frame


@sio.event
async def connect(sid: str, environ: Dict[str, Any]) -> None:
    classifiers[sid] = ExerciseClassifier()
    logger.info("client connected %s", sid)


@sio.event
async def disconnect(sid: str) -> None:
    classifiers.pop(sid, None)
    logger.info("client disconnected %s", sid)


@sio.on(events.POSE_INPUT)
async def handle_pose_input(sid: str, data: Dict[str, Any]) -> None:
    errors: list[str] = []
    raw_frame = None
    normalized_frame = None
    metrics = None
    params = None

    if not runner.ready:
        errors.append("rtmw3d_not_ready")
    else:
        frame = _decode_image(data)
        if frame is None:
            errors.append("image_decode_failed")
        else:
            width = data.get("width")
            height = data.get("height")
            size = (int(width), int(height)) if isinstance(width, (int, float)) and isinstance(height, (int, float)) else None
            if _infer_lock.locked():
                # Drop the frame instead of queueing it: queued frames only add latency.
                return
            async with _infer_lock:
                raw_frame = await asyncio.to_thread(runner.infer, frame, size)
            if raw_frame is None:
                errors.append("pose_inference_failed")
            else:
                raw_frame["t"] = float(data.get("timestamp", raw_frame.get("t", 0.0)))

    if raw_frame is not None:
        normalized_frame, params = normalize_pose(raw_frame)
        metrics = compute_metrics(normalized_frame)

    classifier = classifiers.get(sid) or ExerciseClassifier()
    classifiers[sid] = classifier
    classifier.set_exercise(data.get("exercise"))

    exercise_state = classifier.update(normalized_frame)

    if normalized_frame is not None and params is not None:
        await sio.emit(events.POSE_NORMALIZED, {"frame": normalized_frame, "params": params}, to=sid)

    if metrics is not None:
        await sio.emit(events.POSE_METRICS, {"metrics": metrics}, to=sid)

    await sio.emit(events.EXERCISE_STATE, {"state": exercise_state}, to=sid)

    await sio.emit(
        events.DEBUG_STATE,
        {
            "raw": raw_frame,
            "normalized": normalized_frame,
            "params": params,
            "metrics": metrics,
            "errors": errors,
        },
        to=sid,
    )
