from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Deque, Dict, Optional

from fastapi import WebSocket
from pydantic import BaseModel


class StreamState(str, Enum):
    UNPROCESSED = "UNPROCESSED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"


class CameraState(BaseModel):
    client_id: str
    width: int = 0
    height: int = 0
    fps_target: int = 15
    frames_in: int = 0
    frames_processed: int = 0
    frames_out: int = 0
    frames_dropped: int = 0
    owner: bool = False
    connected_at_ms: int
    updated_at_ms: int


@dataclass
class FramePacket:
    jpeg_bytes: bytes
    decoded_frame: Any | None = None


@dataclass
class RenderPacket:
    jpeg_bytes_processed: bytes
    payload_summary: Dict[str, Any]


class CameraStreamManager:
    def __init__(
        self, 
        max_buffer: int = 8,
        limit_fps: float = 30 # render buffer rate.
    ) -> None:
        self.max_buffer = max_buffer
        self.owner_client_id: Optional[str] = None
        self.owner_ws: Optional[WebSocket] = None
        self.buffer_frames: Deque[FramePacket] = deque(maxlen=max_buffer)
        self.render_frames: Deque[RenderPacket] = deque(maxlen=max_buffer)
        self.state_target: Optional[CameraState] = None
        self.lock = asyncio.Lock()
        self.limit_fps = limit_fps

    async def try_claim_owner(self, client_id: str, ws: WebSocket, fps_target: int) -> bool:
        async with self.lock:
            now = int(time.time() * 1000)
            if self.owner_client_id and self.owner_client_id != client_id:
                return False

            self.owner_client_id = client_id
            self.owner_ws = ws
            state = self.state_target
            if state is None:
                state = CameraState(
                    client_id=client_id,
                    fps_target=max(1, int(fps_target)),
                    connected_at_ms=now,
                    updated_at_ms=now,
                    owner=True,
                )
                self.state_target = state
            else:
                state.client_id = client_id
                state.fps_target = max(1, int(fps_target))
                state.owner = True
                state.updated_at_ms = now
            return True

    async def release_owner(self, client_id: str) -> None:
        async with self.lock:
            if self.owner_client_id == client_id:
                self.owner_client_id = None
                self.owner_ws = None
                self.buffer_frames.clear()
                self.render_frames.clear()
            st = self.state_target
            if st and st.client_id == client_id:
                st.owner = False
                st.updated_at_ms = int(time.time() * 1000)

    async def set_fps_target(self, client_id: str, fps_target: int) -> int:
        async with self.lock:
            state = self.state_target
            if not state or state.client_id != client_id:
                return 15
            state.fps_target = max(1, int(fps_target))
            state.updated_at_ms = int(time.time() * 1000)
            return state.fps_target

    async def push_unprocessed(self, client_id: str, packet: FramePacket) -> None:
        async with self.lock:
            state = self.state_target
            if not state or state.client_id != client_id:
                return
            if len(self.buffer_frames) >= self.max_buffer:
                self.buffer_frames.popleft()
                state.frames_dropped += 1
            self.buffer_frames.append(packet)
            state.frames_in += 1
            state.updated_at_ms = int(time.time() * 1000)

    async def pop_unprocessed(self) -> Optional[FramePacket]:
        async with self.lock:
            if not self.buffer_frames:
                return None
            return self.buffer_frames.popleft()

    async def push_render(self, client_id: str, packet: RenderPacket) -> None:
        async with self.lock:
            state = self.state_target
            if not state or state.client_id != client_id:
                return
            if len(self.render_frames) >= self.max_buffer:
                self.render_frames.popleft()
                state.frames_dropped += 1
            self.render_frames.append(packet)
            state.frames_processed += 1
            state.updated_at_ms = int(time.time() * 1000)

    async def pop_render(self) -> Optional[RenderPacket]:
        async with self.lock:
            if not self.render_frames:
                return None
            return self.render_frames.popleft()

    async def mark_out(self, client_id: str) -> None:
        async with self.lock:
            st = self.state_target
            if st and st.client_id == client_id:
                st.frames_out += 1
                st.updated_at_ms = int(time.time() * 1000)

    async def update_frame_shape(self, client_id: str, width: int, height: int) -> None:
        async with self.lock:
            st = self.state_target
            if st and st.client_id == client_id:
                st.width = int(width)
                st.height = int(height)
                st.updated_at_ms = int(time.time() * 1000)

    async def snapshot_state(self, client_id: Optional[str] = None) -> Dict[str, Any]:
        async with self.lock:
            s = None
            if self.state_target and (client_id is None or self.state_target.client_id == client_id):
                s = self.state_target.model_dump()
            return {
                "owner_client_id": self.owner_client_id,
                "buffer_in": len(self.buffer_frames),
                "buffer_out": len(self.render_frames),
                "state": s,
            }

    async def run_processor_loop(
        self,
        client_id: str,
        stop_event: asyncio.Event,
        process_fn: Callable[[FramePacket], Awaitable[Optional[RenderPacket]]],
    ) -> None:
        while not stop_event.is_set():
            packet = await self.pop_unprocessed()
            if packet is None:
                await asyncio.sleep(0.005)
                continue

            render_packet = await process_fn(packet)
            if render_packet is not None:
                await self.push_render(client_id, render_packet)

            state = self.state_target
            if state and state.client_id != client_id:
                state = None
            fps = state.fps_target if state else 15
            await asyncio.sleep(max(0.0, 1.0 / max(fps, 1) * 0.25))

    async def run_sender_loop(self, client_id: str, ws: WebSocket, stop_event: asyncio.Event) -> None:
        last_stats_sent = 0.0
        while not stop_event.is_set():
            packet = await self.pop_render()
            if packet is None:
                now = time.perf_counter()
                if now - last_stats_sent > 0.7:
                    await ws.send_json({"type": "stats", **(await self.snapshot_state(client_id))})
                    last_stats_sent = now
                await asyncio.sleep(0.01)
                continue

            await ws.send_bytes(packet.jpeg_bytes_processed)
            await ws.send_json({
                "type": "stats",
                "summary": packet.payload_summary,
                **(await self.snapshot_state(client_id)),
            })
            await self.mark_out(client_id)
