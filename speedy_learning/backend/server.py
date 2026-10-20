from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .camera_stream import CameraStreamManager, FramePacket, RenderPacket
from .inference_rtmw3d import RTMW3DEstimator
from .inference_yolox import YOLOXDetector
from .utils_camera import build_camera_state_fallback, decode_jpeg, parse_camera_state_form
from .zenfit_state import Zenfit

import dotenv

ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "server.log"
DEBUG_FRAMES_DIR = LOGS_DIR / "debug_frames"
DEBUG_FRAMES_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Zenfit Labs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/frontend", StaticFiles(directory=ROOT / "frontend"), name="frontend")
app.mount("/docs_static", StaticFiles(directory=ROOT / "docs"), name="docs_static")

dotenv.load_dotenv()

LOG_LEVEL_NAME = os.getenv("ZENFIT_LOG_LEVEL", "INFO").strip().upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_NAME, logging.INFO)
VERBOSE_CAMERA = os.getenv("ZENFIT_VERBOSE_CAMERA", "0").strip().lower() in {"1", "true", "yes", "on"}

detector = YOLOXDetector()
pose_estimator = RTMW3DEstimator()
camera_stream_manager = CameraStreamManager(max_buffer=8)
logger = logging.getLogger("zenfit.server")
logger.setLevel(LOG_LEVEL)
if not logger.handlers:
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(LOG_LEVEL)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(LOG_LEVEL)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False

zenfit = Zenfit(
    csm=camera_stream_manager,
    bbox_detector=detector,
    pose_estimator=pose_estimator,
    logger=logger,
    debug_dir=DEBUG_FRAMES_DIR,
)


# ---------- HTTP routes ----------
@app.get("/")
def viewer_index() -> FileResponse:
    return FileResponse(ROOT / "viewer.html")


@app.get("/viewer.html")
def viewer_file() -> FileResponse:
    return FileResponse(ROOT / "viewer.html")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "providers": zenfit.providers,
        "detector_model": str(zenfit.bbox_detector.model_path) if zenfit.bbox_detector.model_path else None,
        "pose_model": str(zenfit.pose_estimator.model_path) if zenfit.pose_estimator.model_path else None,
        "cwd": str(ROOT),
    }


@app.get("/camera/stream/state")
async def camera_stream_state() -> Dict[str, Any]:
    return await camera_stream_manager.snapshot_state()


@app.post("/process")
async def process(
    image: UploadFile = File(...),
    camera_state: Optional[str] = Form(default=None),
    camera_width: Optional[int] = Form(default=None),
    camera_height: Optional[int] = Form(default=None),
    camera_fps: Optional[float] = Form(default=None),
) -> Dict[str, Any]:
    payload_bytes = await image.read()
    if not payload_bytes:
        raise HTTPException(status_code=400, detail="empty image upload")

    try:
        frame = decode_jpeg(payload_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    fh, fw = frame.shape[:2]
    logger.info("decoded frame shape=%sx%s bytes=%s", fw, fh, len(payload_bytes))
    if VERBOSE_CAMERA:
        logger.info("Camera State (raw): %s", camera_state)
        logger.info("Camera scalar form fields width=%s height=%s fps=%s", camera_width, camera_height, camera_fps)
    state = parse_camera_state_form(camera_state)
    if state is None:
        state = build_camera_state_fallback(
            frame_width=fw,
            frame_height=fh,
            camera_width=camera_width,
            camera_height=camera_height,
            camera_fps=camera_fps,
        )
        if VERBOSE_CAMERA:
            logger.info("Camera State (fallback-built): %s", state.model_dump())
    if VERBOSE_CAMERA:
        logger.info("Camera State (parsed): %s", state.model_dump() if state else None)

    stream_state = await camera_stream_manager.snapshot_state()
    stream_fps_target =  camera_stream_manager.limit_fps
    zenfit.update_camera_state(state, stream_fps_target=stream_fps_target)

    if state:
        logger.info(
            "process camera_state width=%s height=%s fps=%.3f stream_fps_target=%s ratio=%s",
            state.width,
            state.height,
            float(state.fps),
            stream_fps_target,
            zenfit.last_camera_debug.get("ratio_camera_to_stream"),
        )
    else:
        logger.info("process camera_state missing stream_fps_target=%s", stream_fps_target)
    response = zenfit.run_pose(frame)

    response.setdefault("debug", {})
    response["debug"]["camera_state_in"] = state.model_dump() if state else None
    response["debug"]["camera_stream_snapshot"] = stream_state
    response["debug"]["camera_vs_stream"] = zenfit.last_camera_debug
    return response


# ---------- WebSocket stream ----------
@app.websocket("/camera/stream/ws")
async def camera_stream_ws(
    ws: WebSocket,
    client_id: Optional[str] = Query(default=None),
    fps_target: int = Query(default=15, ge=1, le=60),
) -> None:
    await ws.accept()

    cid = (client_id or f"cli_{uuid.uuid4().hex[:8]}").strip()

    claimed = await camera_stream_manager.try_claim_owner(cid, ws, fps_target)
    if not claimed:
        await ws.send_json({"type": "error", "code": "OWNER_LOCKED", "message": "stream owner already active"})
        await ws.close(code=4403)
        return

    await ws.send_json({"type": "hello", "client_id": cid, "owner": True, "fps_target": fps_target})

    stop_event = asyncio.Event()

    async def process_packet(packet: FramePacket) -> Optional[RenderPacket]:
        try:
            frame = decode_jpeg(packet.jpeg_bytes)
            h, w = frame.shape[:2]
            await camera_stream_manager.update_frame_shape(cid, w, h)
            payload = zenfit.run_pose(frame)
            processed_jpeg = zenfit.build_processed_preview(frame, payload)
            live_payload = {
                "meta": payload.get("meta", {}),
                "detector": payload.get("detector", {}),
                "pose_raw17": payload.get("pose_raw17"),
                "pose_raw17_normalized": payload.get("pose_raw17_normalized"),
                "pose_raw17_normalized_full": payload.get("pose_raw17_normalized_full"),
                "pose_raw17_transformed": payload.get("pose_raw17_transformed"),
                "pose_mapped_humanoid": payload.get("pose_mapped_humanoid"),
                "debug": {
                    "warnings": payload.get("debug", {}).get("warnings", []),
                    "axis_consistency": payload.get("debug", {}).get("axis_consistency"),
                },
            }
            summary = {
                "bbox": payload.get("detector", {}).get("bbox_xyxy"),
                "score": payload.get("detector", {}).get("score", 0.0),
                "latency_ms": payload.get("meta", {}).get("latency_ms", 0.0),
                "warnings": payload.get("debug", {}).get("warnings", []),
                "payload": live_payload,
            }
            return RenderPacket(
                jpeg_bytes_processed=processed_jpeg,
                payload_summary=summary,
            )
        except Exception as exc:
            await ws.send_json({"type": "error", "code": "PROCESS_FAIL", "message": str(exc)})
            return None

    async def receiver_loop() -> None:
        try:
            while not stop_event.is_set():
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    break

                b = msg.get("bytes")
                t = msg.get("text")
                if b is not None:
                    packet = FramePacket(jpeg_bytes=b)
                    await camera_stream_manager.push_unprocessed(cid, packet)
                    continue

                if t:
                    try:
                        data = json.loads(t)
                    except json.JSONDecodeError:
                        await ws.send_json({"type": "error", "code": "BAD_JSON", "message": "invalid control json"})
                        continue
                    kind = data.get("type")
                    if kind == "ping":
                        await ws.send_json({"type": "ack", "kind": "ping", "ts": int(time.time() * 1000)})
                    elif kind == "set_fps":
                        new_fps = await camera_stream_manager.set_fps_target(cid, int(data.get("fps_target", fps_target)))
                        await ws.send_json({"type": "ack", "kind": "set_fps", "fps_target": new_fps})
                    elif kind == "stop":
                        stop_event.set()
                        break
                    else:
                        await ws.send_json({"type": "error", "code": "UNKNOWN_CONTROL", "message": str(kind)})
        except WebSocketDisconnect:
            pass
        finally:
            stop_event.set()

    tasks = [
        asyncio.create_task(receiver_loop(), name=f"ws-recv-{cid}"),
        asyncio.create_task(camera_stream_manager.run_processor_loop(cid, stop_event, process_packet), name=f"ws-proc-{cid}"),
        asyncio.create_task(camera_stream_manager.run_sender_loop(cid, ws, stop_event), name=f"ws-send-{cid}"),
    ]

    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        stop_event.set()
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await camera_stream_manager.release_owner(cid)
        try:
            await ws.close()
        except Exception:
            pass
