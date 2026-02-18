from __future__ import annotations

import json
from typing import Optional

import cv2
import numpy as np
from fastapi import HTTPException
from pydantic import ValidationError

from .zenfit_state import CameraState


def decode_jpeg(jpeg_bytes: bytes) -> np.ndarray:
    np_buf = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    frame = cv2.imdecode(np_buf, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("invalid image bytes")
    return frame


def parse_camera_state_form(camera_state_raw: Optional[str]) -> Optional[CameraState]:
    if not camera_state_raw:
        return None
    try:
        payload = json.loads(camera_state_raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid camera_state JSON: {exc.msg}") from exc
    try:
        return CameraState.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=f"invalid camera_state payload: {exc.errors()}") from exc


def build_camera_state_fallback(
    *,
    frame_width: int,
    frame_height: int,
    camera_width: Optional[int],
    camera_height: Optional[int],
    camera_fps: Optional[float],
) -> CameraState:
    return CameraState(
        width=int(camera_width if camera_width and camera_width > 0 else frame_width),
        height=int(camera_height if camera_height and camera_height > 0 else frame_height),
        fps=float(camera_fps if camera_fps and camera_fps > 0 else 0.0),
        label="fallback_from_form_or_frame",
    )
