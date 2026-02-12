from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import asdict, dataclass
from typing import List


@dataclass
class BenchRow:
    frame_idx: int
    source: str
    loop_ms: float
    infer_ms: float
    queue_delay_ms: float
    dropped_requests: int
    core17_visible_ratio: float
    noncore_visible_ratio: float
    noncore_age_frames: int


class LabsBenchmark:
    def __init__(self) -> None:
        self.rows: List[BenchRow] = []
        self.t0 = time.perf_counter()
        self.frames_display = 0
        self.frames_infer = 0
        self.infer_events = 0
        self.infer_sum_ms = 0.0
        self.queue_sum_ms = 0.0

    def on_frame(
        self,
        frame_idx: int,
        source: str,
        loop_ms: float,
        infer_ms: float,
        queue_delay_ms: float,
        dropped_requests: int,
        core17_visible_ratio: float = 0.0,
        noncore_visible_ratio: float = 0.0,
        noncore_age_frames: int = 0,
    ) -> None:
        self.frames_display += 1
        if source == "measured":
            self.frames_infer += 1
        self.rows.append(
            BenchRow(
                frame_idx=int(frame_idx),
                source=str(source),
                loop_ms=float(loop_ms),
                infer_ms=float(infer_ms),
                queue_delay_ms=float(queue_delay_ms),
                dropped_requests=int(dropped_requests),
                core17_visible_ratio=float(core17_visible_ratio),
                noncore_visible_ratio=float(noncore_visible_ratio),
                noncore_age_frames=int(noncore_age_frames),
            )
        )

    def on_inference_event(self, infer_ms: float, queue_delay_ms: float) -> None:
        self.infer_events += 1
        self.infer_sum_ms += float(infer_ms)
        self.queue_sum_ms += float(queue_delay_ms)

    def summary(self) -> dict:
        elapsed = max(1e-6, time.perf_counter() - self.t0)
        fps_display = self.frames_display / elapsed
        fps_infer = self.infer_events / elapsed
        loop_ms = [r.loop_ms for r in self.rows] or [0.0]
        infer_ms = (self.infer_sum_ms / self.infer_events) if self.infer_events > 0 else 0.0
        q_ms = (self.queue_sum_ms / self.infer_events) if self.infer_events > 0 else 0.0
        dropped = sum(r.dropped_requests for r in self.rows)
        core_vis = float(sum(r.core17_visible_ratio for r in self.rows) / max(1, len(self.rows)))
        noncore_vis = float(sum(r.noncore_visible_ratio for r in self.rows) / max(1, len(self.rows)))
        noncore_age = float(sum(r.noncore_age_frames for r in self.rows) / max(1, len(self.rows)))
        return {
            "fps_display": round(float(fps_display), 3),
            "fps_infer": round(float(fps_infer), 3),
            "latency_ms": round(float(sum(loop_ms) / len(loop_ms)), 3),
            "queue_delay_ms": round(float(q_ms), 3),
            "infer_ms": round(float(infer_ms), 3),
            "dropped_requests": int(dropped),
            "frames": int(self.frames_display),
            "core17_visible_ratio": round(core_vis, 3),
            "noncore_visible_ratio": round(noncore_vis, 3),
            "noncore_age_frames": round(noncore_age, 3),
        }

    def export(self, out_dir: str = "workspace/backend/benchmarks") -> tuple[str, str]:
        os.makedirs(out_dir, exist_ok=True)
        csv_path = os.path.join(out_dir, "labs_runtime_latest.csv")
        json_path = os.path.join(out_dir, "labs_runtime_latest.json")

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(asdict(self.rows[0]).keys()) if self.rows else [
                "frame_idx", "source", "loop_ms", "infer_ms", "queue_delay_ms", "dropped_requests",
                "core17_visible_ratio", "noncore_visible_ratio", "noncore_age_frames",
            ])
            writer.writeheader()
            for row in self.rows:
                writer.writerow(asdict(row))

        payload = {
            "summary": self.summary(),
            "rows": [asdict(x) for x in self.rows],
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return csv_path, json_path
