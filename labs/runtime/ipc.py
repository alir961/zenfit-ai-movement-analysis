from __future__ import annotations

import queue
import uuid
from multiprocessing import shared_memory
from typing import Any, Iterable, List, Tuple

import numpy as np

from labs.types import SharedMemorySpec


def queue_put_drop_oldest(q, item: Any) -> int:
    dropped = 0
    while True:
        try:
            q.put_nowait(item)
            return dropped
        except queue.Full:
            try:
                q.get_nowait()
                dropped += 1
            except queue.Empty:
                return dropped


class SharedFrameWriter:
    def __init__(self, frame_shape: Tuple[int, int, int], dtype: np.dtype = np.uint8, slots: int = 4) -> None:
        self.frame_shape = tuple(frame_shape)
        self.dtype = np.dtype(dtype)
        self.slots = max(2, int(slots))
        self._shm_blocks: List[shared_memory.SharedMemory] = []
        self._arrays: List[np.ndarray] = []

        nbytes = int(np.prod(self.frame_shape) * self.dtype.itemsize)
        for _ in range(self.slots):
            name = f"zenfit_labs_{uuid.uuid4().hex[:16]}"
            shm = shared_memory.SharedMemory(name=name, create=True, size=nbytes)
            arr = np.ndarray(self.frame_shape, dtype=self.dtype, buffer=shm.buf)
            self._shm_blocks.append(shm)
            self._arrays.append(arr)

    @property
    def spec(self) -> SharedMemorySpec:
        return SharedMemorySpec(
            names=[x.name for x in self._shm_blocks],
            frame_shape=self.frame_shape,
            dtype=str(self.dtype),
        )

    def write(self, slot_idx: int, frame: np.ndarray) -> None:
        slot = int(slot_idx) % self.slots
        np.copyto(self._arrays[slot], frame, casting="no")

    def close(self) -> None:
        for shm in self._shm_blocks:
            try:
                shm.close()
            except FileNotFoundError:
                pass

    def unlink(self) -> None:
        for shm in self._shm_blocks:
            try:
                shm.unlink()
            except FileNotFoundError:
                pass


class SharedFrameReader:
    def __init__(self, spec: SharedMemorySpec) -> None:
        self.spec = spec
        self.frame_shape = tuple(spec.frame_shape)
        self.dtype = np.dtype(spec.dtype)
        self._shm_blocks = [shared_memory.SharedMemory(name=n) for n in spec.names]
        self._arrays = [np.ndarray(self.frame_shape, dtype=self.dtype, buffer=shm.buf) for shm in self._shm_blocks]

    def read_copy(self, slot_idx: int) -> np.ndarray:
        slot = int(slot_idx) % len(self._arrays)
        return self._arrays[slot].copy()

    def close(self) -> None:
        for shm in self._shm_blocks:
            try:
                shm.close()
            except FileNotFoundError:
                pass
