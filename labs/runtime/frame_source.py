from __future__ import annotations

import cv2


class VideoFrameSource:
    def __init__(self, video_path: str) -> None:
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise RuntimeError(f"video_open_failed:{video_path}")
        self.fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 30.0)
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    def read(self):
        ok, frame = self.cap.read()
        if not ok:
            return None
        frame_idx = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
        ts = frame_idx / self.fps if self.fps > 0 else 0.0
        return frame_idx, ts, frame

    def release(self) -> None:
        self.cap.release()
