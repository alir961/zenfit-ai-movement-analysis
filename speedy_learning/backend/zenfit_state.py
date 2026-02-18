from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import numpy as np
from pydantic import BaseModel

from .camera_stream import CameraStreamManager
from .gaussian_stats import OnlineGaussian
from .inference_rtmw3d import RTMW3DEstimator
from .inference_yolox import YOLOXDetector
from .math_types import Vec3
from .postprocess import process_pose
from .skeleton_generic import GenericSkeleton
from .skeleton_map import map_raw17_to_humanoid


class CameraState(BaseModel):
    width: int
    height: int
    fps: float = 0.0
    device_id: Optional[str] = None
    label: Optional[str] = None

    model_config = {
        "extra": "allow",
    }


class Zenfit:
    csm: CameraStreamManager

    def __init__(
        self,
        *,
        csm: CameraStreamManager,
        bbox_detector: YOLOXDetector,
        pose_estimator: RTMW3DEstimator,
        logger: Any,
        debug_dir: Path,
    ):
        self.csm = csm
        self.bbox_detector = bbox_detector
        self.pose_estimator = pose_estimator
        self.logger = logger
        self.debug_dir = debug_dir
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.debug_enabled = os.getenv("ZENFIT_DEBUG_STAGES", "1").strip().lower() in {"1", "true", "yes", "on"}
        self.last_camera_state: Optional[CameraState] = None
        self.last_camera_debug: Dict[str, Any] = {}
        self._gaussian_by_dim: Dict[int, OnlineGaussian] = {}

    def _log_debug(self, message: str, *args: Any) -> None:
        try:
            if self.logger and hasattr(self.logger, "debug"):
                self.logger.debug(message, *args)
        except Exception:
            pass

    def _log_info(self, message: str, *args: Any) -> None:
        try:
            if self.logger and hasattr(self.logger, "info"):
                self.logger.info(message, *args)
        except Exception:
            pass

    def _log_warning(self, message: str, *args: Any) -> None:
        try:
            if self.logger and hasattr(self.logger, "warning"):
                self.logger.warning(message, *args)
        except Exception:
            pass

    def update_camera_state(self, state: Optional[CameraState], stream_fps_target: Optional[int] = None) -> None:
        self.last_camera_state = state
        self.last_camera_debug = {
            "camera_state": state.model_dump() if state else None,
            "stream_fps_target": stream_fps_target,
            "ratio_camera_to_stream": (
                float(state.fps) / float(stream_fps_target)
                if state and state.fps and stream_fps_target and stream_fps_target > 0
                else None
            ),
        }
        self._log_debug(
            "camera_state updated: state=%s stream_fps_target=%s ratio=%s",
            self.last_camera_debug.get("camera_state"),
            stream_fps_target,
            self.last_camera_debug.get("ratio_camera_to_stream"),
        )

    @property
    def providers(self) -> list[str]:
        return sorted(set(self.bbox_detector.providers + self.pose_estimator.providers))

    def _get_gaussian_for_dim(self, feature_dim: int) -> OnlineGaussian:
        g = self._gaussian_by_dim.get(feature_dim)
        if g and g.dimension == feature_dim:
            return g
        g = OnlineGaussian(dimension=feature_dim)
        self._gaussian_by_dim[feature_dim] = g
        return g

    def _save_stage_image(self, name: str, image_bgr: np.ndarray) -> None:
        if not self.debug_enabled:
            return
        out_path = self.debug_dir / f"last_{name}.jpg"
        cv2.imwrite(str(out_path), image_bgr)

    def _save_stage_plot3d(self, name: str, joints: list[Dict[str, Any]], edges: list[Dict[str, Any]], show: bool = True) -> None:
        if not self.debug_enabled:
            return
        try:
            import matplotlib
            matplotlib.use("Agg", force=True)
            import matplotlib.pyplot as plt
        except Exception as exc:
            self._log_warning("3d plot skipped (%s): %s", name, exc)
            return

        fig = None
        try:
            fig = plt.figure(figsize=(6, 6))
            ax = fig.add_subplot(111, projection="3d")

            xs = [float(j.get("x", 0.0)) for j in joints]
            ys = [float(j.get("y", 0.0)) for j in joints]
            zs = [float(j.get("z", 0.0)) for j in joints]
            if xs:
                ax.scatter(xs, ys, zs, s=14, c="lime", depthshade=True)

            for e in edges:
                a = int(e["a"]) if isinstance(e, dict) and "a" in e else -1
                b = int(e["b"]) if isinstance(e, dict) and "b" in e else -1
                if a < 0 or b < 0 or a >= len(joints) or b >= len(joints):
                    continue
                ja = joints[a]
                jb = joints[b]
                ax.plot(
                    [float(ja.get("x", 0.0)), float(jb.get("x", 0.0))],
                    [float(ja.get("y", 0.0)), float(jb.get("y", 0.0))],
                    [float(ja.get("z", 0.0)), float(jb.get("z", 0.0))],
                    color="orange",
                    linewidth=1.0,
                )

            ax.set_title(name)
            ax.set_xlabel("X")
            ax.set_ylabel("Y")
            ax.set_zlabel("Z")

            if xs:
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)
                min_z, max_z = min(zs), max(zs)
                cx = 0.5 * (min_x + max_x)
                cy = 0.5 * (min_y + max_y)
                cz = 0.5 * (min_z + max_z)
                span = max(max_x - min_x, max_y - min_y, max_z - min_z, 1e-3)
                half = 0.5 * span
                ax.set_xlim(cx - half, cx + half)
                ax.set_ylim(cy - half, cy + half)
                ax.set_zlim(cz - half, cz + half)

            out_path = self.debug_dir / f"last_{name}.png"
            fig.savefig(str(out_path), dpi=150, bbox_inches="tight")
        except Exception as exc:
            self._log_warning("3d plot save failed (%s): %s", name, exc)
        finally:
            if fig is not None:
                plt.close(fig)

    def _map_and_postprocess(self, raw17_joints: list[Dict[str, Any]]) -> tuple[Dict[str, Any], Dict[str, Any], Optional[str]]:
        try:
            mapped_humanoid = map_raw17_to_humanoid(raw17_joints)
            map_warning = None
        except Exception as exc:
            mapped_humanoid = {"joints": [], "edges": []}
            map_warning = f"map_failed: {exc}"

        if mapped_humanoid.get("joints"):
            pp = process_pose(raw17_joints, mapped_humanoid)
        else:
            pp = {
                "pose_normalized": {
                    "scale_basis": "max_ik_length",
                    "ik_max_length": 1.0,
                    "joints_raw17": raw17_joints,
                    "joints_mapped_humanoid": [],
                },
                "postprocess": {
                    "upper_anchor": "none",
                    "ik_max_length": 1.0,
                    "regularization": {
                        "targets": {},
                        "limb_lengths_pre": {},
                        "limb_lengths_post": {},
                    },
                    "surface_vector": [0.0, 0.0, 1.0],
                    "surface_ref": [1.0, 0.0, 1.0],
                    "surface_alignment": 0.0,
                    "yaw_deg": 0.0,
                    "joint_angles_deg": {},
                },
                "feature_vector": [0.0],
            }
        return mapped_humanoid, pp, map_warning

    def _axis_consistency(self, raw17_joints: list[Dict[str, Any]]) -> Dict[str, Any]:
        by_idx = {int(j.get("index", i)): j for i, j in enumerate(raw17_joints)}
        notes: list[str] = []
        required = [5, 6, 11, 12]
        if any(i not in by_idx for i in required):
            notes.append("missing anchors for handedness check (5,6,11,12)")
            return {"handedness_ok": None, "det_sign": None, "notes": notes}

        def _v(i: int) -> np.ndarray:
            j = by_idx[i]
            return np.array([float(j.get("x", 0.0)), float(j.get("y", 0.0)), float(j.get("z", 0.0))], dtype=np.float64)

        ls = _v(5)
        rs = _v(6)
        lh = _v(11)
        rh = _v(12)
        shoulder = rs - ls
        hip = rh - lh
        up = ((ls + rs) * 0.5) - ((lh + rh) * 0.5)
        sx = np.linalg.norm(shoulder)
        sy = np.linalg.norm(hip)
        sz = np.linalg.norm(up)
        if sx < 1e-8 or sy < 1e-8 or sz < 1e-8:
            notes.append("degenerate anchor vectors")
            return {"handedness_ok": None, "det_sign": None, "notes": notes}

        x = shoulder / sx
        y = up / sz
        z = np.cross(x, y)
        nz = np.linalg.norm(z)
        if nz < 1e-8:
            notes.append("near-collinear anchor basis")
            return {"handedness_ok": None, "det_sign": None, "notes": notes}
        z = z / nz
        det_sign = float(np.linalg.det(np.stack([x, y, z], axis=1)))
        return {
            "handedness_ok": bool(det_sign > 0.0),
            "det_sign": det_sign,
            "notes": notes,
        }

    def run_pose(self, frame_bgr: np.ndarray) -> Dict[str, Any]:
        stage_t: Dict[str, float] = {}
        t0 = time.perf_counter()
        h, w = frame_bgr.shape[:2]
        self._log_debug("run_pose start: frame_shape=%sx%s", w, h)

        self._save_stage_image("input", frame_bgr)

        # WORK
        t_det = time.perf_counter()
        det = self.bbox_detector.detect(frame_bgr)
        stage_t["detector_ms"] = (time.perf_counter() - t_det) * 1000.0
        self._log_debug("detector output: %s", det)

        bbox_preview = frame_bgr.copy()
        bbox = det.get("bbox_xyxy", [0, 0, 0, 0])
        x1 = int(np.clip(float(bbox[0]), 0, w - 1))
        y1 = int(np.clip(float(bbox[1]), 0, h - 1))
        x2 = int(np.clip(float(bbox[2]), x1 + 1, w))
        y2 = int(np.clip(float(bbox[3]), y1 + 1, h))
        cv2.rectangle(bbox_preview, (x1, y1), (x2, y2), (0, 255, 255), 2)
        
        self._save_stage_image("bbox", bbox_preview)

        t_pose = time.perf_counter()
        pose = self.pose_estimator.predict(frame_bgr, det["bbox_xyxy"])
        stage_t["pose_ms"] = (time.perf_counter() - t_pose) * 1000.0
        self._log_debug("pose output: joints=%s source=%s", pose, pose.get("source", "unknown"))

        t_map = time.perf_counter()
        raw17_skeleton = GenericSkeleton.from_coco17_points(pose.get("joints", []))
        raw17_payload = raw17_skeleton.to_payload()
        raw17_joints = raw17_payload["joints"]
        
        raw17_preview = bbox_preview.copy()
        for e in raw17_payload["edges"]:
            a, b = int(e["a"]), int(e["b"])
            if a < len(raw17_joints) and b < len(raw17_joints):
                pa = raw17_joints[a]
                pb = raw17_joints[b]
                cv2.line(raw17_preview, (int(pa["x"]), int(pa["y"])), (int(pb["x"]), int(pb["y"])), (0, 180, 255), 1)
        for j in raw17_joints:
            cv2.circle(raw17_preview, (int(j["x"]), int(j["y"])), 2, (0, 255, 0), -1)
        self._save_stage_image("raw17", raw17_preview)

        # WORK !
        # Easy normalize: scale only by longest edge (no directional/IK reshaping).
        raw17_normalized_easy = GenericSkeleton.easy_normalize_skeleton(raw17_skeleton)
        raw17_normalized_easy_payload = raw17_normalized_easy.to_payload()
        # Full normalize kept for comparison/debug.
        raw17_normalized_full = GenericSkeleton.normalize_skeleton(raw17_skeleton)
        raw17_normalized_full_payload = raw17_normalized_full.to_payload()
        
        # TODO done: Apply translate and rotation that must create new skeleton
        # 1) recenter to back_center, 2) rotate around X by 180deg, immutable path.
        raw17_transformed = GenericSkeleton.with_axis_rotation(
            raw17_normalized_full.recenter_to_back_center(),
            axis=Vec3(1.0, 0.0, 0.0),
            angle_rad=float(np.deg2rad(180.0)),
            pivot=Vec3(0.0, 0.0, 0.0),
        )
        raw17_transformed_payload = raw17_transformed.to_payload()
        edge_quat_raw = raw17_skeleton.edge_quaternion_map()
        edge_quat_easy = raw17_normalized_easy.edge_quaternion_map()
        edge_quat_full = raw17_normalized_full.edge_quaternion_map()
        edge_quat_delta_easy = GenericSkeleton.compare_edge_quaternions(raw17_skeleton, raw17_normalized_easy)
        edge_quat_delta_full = GenericSkeleton.compare_edge_quaternions(raw17_skeleton, raw17_normalized_full)
        # axis_consistency = self._axis_consistency(raw17_joints)
        self._save_stage_plot3d("raw17_3d", raw17_payload["joints"], raw17_payload["edges"])
        self._save_stage_plot3d(
            "raw17_easy_normalized_3d",
            raw17_normalized_easy_payload["joints"],
            raw17_normalized_easy_payload["edges"],
        )
        self._save_stage_plot3d(
            "raw17_normalized_3d",
            raw17_normalized_full_payload["joints"],
            raw17_normalized_full_payload["edges"],
        )
        self._save_stage_plot3d(
            "raw17_transformed_3d",
            raw17_transformed_payload["joints"],
            raw17_transformed_payload["edges"],
        )
        
        # mapped_humanoid, pp, map_warning = self._map_and_postprocess(raw17_joints)
        # stage_t["mapping_post_ms"] = (time.perf_counter() - t_map) * 1000.0

        confidence = float(np.mean([j.get("confidence", 0.0) for j in raw17_joints])) if raw17_joints else 0.0
        # feature_vector = pp.get("feature_vector", [0.0])
        # t_gauss = time.perf_counter()
        # gaussian = self._get_gaussian_for_dim(len(feature_vector))
        # gaussian.update(feature_vector, confidence=confidence)
        # gaussian_snapshot = gaussian.snapshot()
        # stage_t["gaussian_ms"] = (time.perf_counter() - t_gauss) * 1000.0

        response: Dict[str, Any] = {
            "meta": {
                "latency_ms": (time.perf_counter() - t0) * 1000.0,
                "providers": self.providers,
            },
            "detector": {
                "bbox_xyxy": det["bbox_xyxy"],
                "score": det.get("score", 0.0),
                "class_id": det.get("class_id", 0),
                "source": det.get("source", "unknown"),
            },
            "pose_raw17": {
                "joints": raw17_joints,
                "edges": raw17_payload["edges"],
                "schema": raw17_payload["schema"],
                "source": pose.get("source", "unknown"),
            },
            "pose_raw17_normalized": {
                "joints": raw17_normalized_easy_payload["joints"],
                "edges": raw17_normalized_easy_payload["edges"],
                "schema": raw17_normalized_easy_payload["schema"],
                "metadata": raw17_normalized_easy_payload.get("metadata", {}),
                "source": pose.get("source", "unknown"),
                "mode": "easy_longest_edge_only",
                "axes_origin": "unchanged_from_input",
            },
            "pose_raw17_normalized_full": {
                "joints": raw17_normalized_full_payload["joints"],
                "edges": raw17_normalized_full_payload["edges"],
                "schema": raw17_normalized_full_payload["schema"],
                "metadata": raw17_normalized_full_payload.get("metadata", {}),
                "source": pose.get("source", "unknown"),
                "mode": "full_limb_equalization_plus_longest_edge",
                "axes_origin": "unchanged_from_input",
            },
            "pose_raw17_transformed": {
                "joints": raw17_transformed_payload["joints"],
                "edges": raw17_transformed_payload["edges"],
                "schema": raw17_transformed_payload["schema"],
                "metadata": raw17_transformed_payload.get("metadata", {}),
                "source": pose.get("source", "unknown"),
                "mode": "recenter_back_center_then_rotate_x_180deg",
                "axes_origin": "unchanged_from_input",
            },
            # "pose_mapped_humanoid": mapped_humanoid,
            # "pose_normalized": pp["pose_normalized"],
            # "postprocess": pp["postprocess"],
            # "gaussian": gaussian_snapshot,
            "debug": {
                "edge_quaternions_raw": edge_quat_raw,
                "edge_quaternions_easy": edge_quat_easy,
                "edge_quaternions_full": edge_quat_full,
                "edge_quat_delta_easy_vs_raw": edge_quat_delta_easy,
                "edge_quat_delta_full_vs_raw": edge_quat_delta_full,
                # "axis_consistency": axis_consistency,
                "stage_timings_ms": {
                    **stage_t,
                    "detector_internal_ms": det.get("stage_ms", 0.0),
                    "pose_internal_ms": pose.get("stage_ms", 0.0),
                },
                "warnings": [
                    *det.get("warnings", []),
                    *pose.get("warnings", []),
                    # *([map_warning] if map_warning else []),
                ],
                "image_shape": [int(h), int(w)],
                "confidence_mean_raw17": confidence,
            },
            # "pose_mapped_humanoid": mapped_humanoid,
            # "pose_normalized": pp["pose_normalized"],
            # "postprocess": pp["postprocess"],
            # "gaussian": gaussian_snapshot,
            # "debug": {
            #     "warnings": [
            #         *det.get("warnings", []),
            #         *pose.get("warnings", []),
            #         *([map_warning] if map_warning else []),
            #     ],
            #     "stage_timings_ms": {
            #         **stage_t,
            #         "detector_internal_ms": det.get("stage_ms", 0.0),
            #         "pose_internal_ms": pose.get("stage_ms", 0.0),
            #     },
            #     "image_shape": [int(h), int(w)],
            #     "confidence_mean_raw17": confidence,
            # },
        }
        self._log_info(
            "run_pose done: det_source=%s pose_source=%s joints=%s latency_ms=%.2f",
            det.get("source", "unknown"),
            pose.get("source", "unknown"),
            len(raw17_joints),
            float(response["meta"]["latency_ms"]),
        )
        warnings = response.get("debug", {}).get("warnings", [])
        if warnings:
            self._log_warning("run_pose warnings: %s", warnings)
        self._save_stage_image("processed", self._compose_processed_preview(frame_bgr, response))
        return response

    def _compose_processed_preview(self, frame_bgr: np.ndarray, payload: Dict[str, Any]) -> np.ndarray:
        out = frame_bgr.copy()
        h, w = out.shape[:2]
        bbox = payload.get("detector", {}).get("bbox_xyxy", [0, 0, 0, 0])
        x1 = int(np.clip(float(bbox[0]), 0, w - 1))
        y1 = int(np.clip(float(bbox[1]), 0, h - 1))
        x2 = int(np.clip(float(bbox[2]), x1 + 1, w))
        y2 = int(np.clip(float(bbox[3]), y1 + 1, h))
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 255), 2)

        joints = payload.get("pose_raw17", {}).get("joints", [])
        edges = payload.get("pose_raw17", {}).get("edges", [])
        for e in edges:
            a, b = int(e["a"]), int(e["b"])
            if a < len(joints) and b < len(joints):
                pa = joints[a]
                pb = joints[b]
                cv2.line(out, (int(pa["x"]), int(pa["y"])), (int(pb["x"]), int(pb["y"])), (0, 180, 255), 1)
        for j in joints:
            cv2.circle(out, (int(j["x"]), int(j["y"])), 2, (0, 255, 0), -1)

        latency = payload.get("meta", {}).get("latency_ms", 0.0)
        conf = payload.get("debug", {}).get("confidence_mean_raw17", 0.0)
        cv2.putText(
            out,
            f"lat:{latency:.1f}ms conf:{conf:.2f}",
            (12, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        return out

    def build_processed_preview(self, frame_bgr: np.ndarray, payload: Dict[str, Any]) -> bytes:
        out = self._compose_processed_preview(frame_bgr, payload)
        self._save_stage_image("processed", out)
        ok, enc = cv2.imencode(".jpg", out, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            raise ValueError("failed to encode processed preview")
        return bytes(enc.tobytes())
