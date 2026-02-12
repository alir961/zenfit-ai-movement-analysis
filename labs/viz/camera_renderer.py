from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

import cv2
import numpy as np

from labs.types import PoseEstimate


ColorBGR = Tuple[int, int, int]
Link = Tuple[str, str]


class CameraRenderer:
    def __init__(
        self,
        skeleton_links: Iterable[Link],
        core_names: Iterable[str] | None = None,
        keypoint_colors: Dict[str, ColorBGR] | None = None,
        link_colors: Dict[Link, ColorBGR] | None = None,
    ) -> None:
        self.skeleton_links = list(skeleton_links)
        self.core_names = set(core_names or [])
        self.keypoint_colors = dict(keypoint_colors or {})
        self.link_colors = dict(link_colors or {})

    @staticmethod
    def _dim_color(color: ColorBGR, gain: float = 0.45) -> ColorBGR:
        g = float(np.clip(gain, 0.0, 1.0))
        return (int(color[0] * g), int(color[1] * g), int(color[2] * g))

    @staticmethod
    def _fallback_joint_color(name: str) -> ColorBGR:
        n = (name or "").lower()
        if "left" in n:
            return (80, 220, 80)
        if "right" in n:
            return (80, 80, 240)
        if any(x in n for x in ("nose", "eye", "ear", "head", "face")):
            return (255, 180, 40)
        return (0, 230, 230)

    def _joint_color(self, name: str) -> ColorBGR:
        if name in self.keypoint_colors:
            return self.keypoint_colors[name]
        return self._fallback_joint_color(name)

    def _link_color(self, a: str, b: str) -> ColorBGR:
        if (a, b) in self.link_colors:
            return self.link_colors[(a, b)]
        if (b, a) in self.link_colors:
            return self.link_colors[(b, a)]
        if "left" in a or "left" in b:
            return (80, 220, 80)
        if "right" in a or "right" in b:
            return (80, 80, 240)
        return (200, 200, 200)

    def _draw_joints_and_links(
        self,
        out: np.ndarray,
        joints: List[dict],
        draw_min_conf: float,
        show_noncore_points: bool = True,
    ) -> tuple[int, int]:
        h, w = out.shape[:2]
        min_conf = float(np.clip(draw_min_conf, 0.0, 1.0))
        soft_conf = max(0.01, min(0.08, min_conf * 0.5))
        jmap = {}
        drawn_points = 0
        for j in joints:
            name = str(j.get("name", ""))
            c = float(j.get("c", 0.0))
            px = float(np.clip(j.get("px", 0.0), 0.0, 1.0))
            py = float(np.clip(j.get("py", 0.0), 0.0, 1.0))
            jmap[name] = (px, py, c)
            is_core = (not self.core_names) or (name in self.core_names)
            if (not is_core) and (not show_noncore_points):
                continue
            if c < soft_conf:
                continue
            color = self._joint_color(name)
            radius = 3 if is_core else 1
            if c >= min_conf and is_core:
                radius = 3
            if c < min_conf:
                color = self._dim_color(color, 0.35)
            cv2.circle(out, (int(px * w), int(py * h)), radius, color, -1, cv2.LINE_AA)
            drawn_points += 1

        drawn_links = 0
        for a, b in self.skeleton_links:
            pa = jmap.get(a)
            pb = jmap.get(b)
            if pa is None or pb is None:
                continue
            c = min(float(pa[2]), float(pb[2]))
            if c < soft_conf:
                continue
            color = self._link_color(a, b)
            thickness = 2 if c >= min_conf else 1
            if c < min_conf:
                color = self._dim_color(color, 0.40)
            p1 = (int(pa[0] * w), int(pa[1] * h))
            p2 = (int(pb[0] * w), int(pb[1] * h))
            cv2.line(out, p1, p2, color, thickness, cv2.LINE_AA)
            drawn_links += 1
        return drawn_points, drawn_links

    def _draw_bbox(self, out: np.ndarray, bbox_xyxy: tuple[float, float, float, float] | None) -> None:
        if bbox_xyxy is None:
            return
        h, w = out.shape[:2]
        try:
            x1, y1, x2, y2 = [float(v) for v in bbox_xyxy]
        except Exception:
            return
        x1 = int(np.clip(x1, 0, w - 1))
        y1 = int(np.clip(y1, 0, h - 1))
        x2 = int(np.clip(x2, 0, w - 1))
        y2 = int(np.clip(y2, 0, h - 1))
        if x2 <= x1 or y2 <= y1:
            return
        cv2.rectangle(out, (x1, y1), (x2, y2), (40, 255, 90), 2, cv2.LINE_AA)

    def render(
        self,
        frame: np.ndarray,
        estimate: PoseEstimate,
        perf_text: str = "",
        draw_min_conf: float = 0.10,
        rig_name: str = "coco133",
        show_noncore_points: bool = True,
    ) -> np.ndarray:
        out = frame.copy()
        joints = [j.__dict__ for j in estimate.joints]
        drawn_pts, drawn_links = self._draw_joints_and_links(
            out,
            joints,
            draw_min_conf,
            show_noncore_points=show_noncore_points,
        )
        self._draw_bbox(out, estimate.bbox_xyxy)

        h, w = out.shape[:2]
        panel_w = min(360, max(260, int(w * 0.34)))
        x0 = max(0, w - panel_w)
        overlay = out.copy()
        cv2.rectangle(overlay, (x0, 0), (w, h), (18, 18, 18), -1)
        cv2.addWeighted(overlay, 0.60, out, 0.40, 0.0, out)

        y = 28

        def put(text: str, color=(220, 220, 220), scale=0.52, thick=1):
            nonlocal y
            cv2.putText(out, text, (x0 + 14, y), cv2.FONT_HERSHEY_DUPLEX, scale, color, thick, cv2.LINE_AA)
            y += int(24 * max(1.0, scale))

        put("ZENFIT LABS V3", (0, 255, 255), 0.64, 2)
        put(f"source: {estimate.source} age={estimate.measurement_age_frames}")
        put(perf_text, (170, 170, 170), 0.46, 1)
        put(
            f"queue_ms={estimate.queue_delay_ms:.1f} yaw={estimate.canonical_yaw_deg:.1f}deg",
            (170, 170, 170),
            0.46,
            1,
        )
        put(f"rig={rig_name} points={drawn_pts}/{len(joints)} links={drawn_links}/{len(self.skeleton_links)}")
        put(f"quality={estimate.quality.score:.2f} conf={estimate.quality.median_confidence:.2f}")
        put(f"height={estimate.scale.height_estimate_cm:.1f}cm")
        lo, hi = estimate.scale.confidence_interval_cm
        put(f"CI95=[{lo:.1f}, {hi:.1f}]cm")

        if estimate.scale.quality_flags:
            put("flags:", (0, 180, 255))
            for flag in estimate.scale.quality_flags[:6]:
                put(f"- {flag}", (0, 180, 255), 0.45, 1)

        return out

    def render_raw_points(
        self,
        frame: np.ndarray,
        joints: List[dict],
        perf_text: str = "",
        status_text: str = "",
        conf_thr: float = 0.0,
        bbox_xyxy: tuple[float, float, float, float] | None = None,
        rig_name: str = "coco133",
        show_noncore_points: bool = True,
    ) -> np.ndarray:
        out = frame.copy()
        parsed: List[dict] = []
        for j in joints:
            try:
                if hasattr(j, "px"):
                    parsed.append(
                        {
                            "name": str(getattr(j, "name", "")),
                            "px": float(getattr(j, "px", 0.0)),
                            "py": float(getattr(j, "py", 0.0)),
                            "c": float(getattr(j, "c", 0.0)),
                        }
                    )
                else:
                    parsed.append(
                        {
                            "name": str(j.get("name", "")),
                            "px": float(j.get("px", 0.0)),
                            "py": float(j.get("py", 0.0)),
                            "c": float(j.get("c", 0.0)),
                        }
                    )
            except Exception:
                continue

        draw_thr = max(0.0, float(conf_thr))
        drawn_pts, drawn_links = self._draw_joints_and_links(
            out,
            parsed,
            draw_thr,
            show_noncore_points=show_noncore_points,
        )
        self._draw_bbox(out, bbox_xyxy)

        h, w = out.shape[:2]
        panel_w = min(360, max(260, int(w * 0.42)))
        x0 = max(0, w - panel_w)
        overlay = out.copy()
        cv2.rectangle(overlay, (x0, 0), (w, h), (18, 18, 18), -1)
        cv2.addWeighted(overlay, 0.60, out, 0.40, 0.0, out)

        y = 28

        def put(text: str, color=(220, 220, 220), scale=0.52, thick=1):
            nonlocal y
            cv2.putText(out, text, (x0 + 14, y), cv2.FONT_HERSHEY_DUPLEX, scale, color, thick, cv2.LINE_AA)
            y += int(24 * max(1.0, scale))

        put("ZENFIT LABS MANDATORY", (0, 255, 255), 0.62, 2)
        put(perf_text, (170, 170, 170), 0.46, 1)
        put(f"rig={rig_name} points={drawn_pts}/{len(parsed)} links={drawn_links}/{len(self.skeleton_links)}")
        put(f"draw_min_conf={draw_thr:.2f}", (170, 170, 170), 0.44, 1)
        if status_text:
            put(status_text, (0, 180, 255), 0.45, 1)
        return out
