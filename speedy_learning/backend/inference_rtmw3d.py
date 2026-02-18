from __future__ import annotations

import time
import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

try:
    import onnxruntime as ort
except Exception:  # pragma: no cover
    ort = None

from .skeleton_map import COCO17_NAMES
from .ort_bootstrap import bootstrap_onnxruntime


def _safe_bbox(box: List[float], width: int, height: int) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    x1 = int(np.clip(x1, 0, width - 1))
    y1 = int(np.clip(y1, 0, height - 1))
    x2 = int(np.clip(x2, x1 + 1, width))
    y2 = int(np.clip(y2, y1 + 1, height))
    return x1, y1, x2, y2


class RTMW3DEstimator:
    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path = self._resolve_model_path(model_path)
        self.session = None
        self.input_name = None
        self.input_hw = (384, 288)
        self.providers: List[str] = ["CPUExecutionProvider"]
        self.warnings: List[str] = []

        self._init_runtime()

    def _resolve_model_path(self, model_path: Optional[str]) -> Optional[Path]:
        candidates = []
        if model_path:
            candidates.append(Path(model_path))
        candidates.extend(
            [
                Path("speedy_learning/models/rtmw3d_l_fp32.onnx"),
                Path("workspace/backend/models/onnx/rtmw3d_l_fp32.onnx"),
                Path("workspace/backend/models/onnx/rtmw3d_l_fp16.onnx"),
                Path("rtmw3d_l.onnx"),
            ]
        )
        for p in candidates:
            rp = p.resolve()
            if rp.exists():
                return rp
        return None

    def _init_runtime(self) -> None:
        if ort is None:
            self.warnings.append("onnxruntime unavailable")
            return
        if self.model_path is None:
            self.warnings.append("RTMW3D model missing")
            return

        boot = bootstrap_onnxruntime()
        for w in boot.get("warnings", []):
            self.warnings.append(f"ORT bootstrap: {w}")

        cpu_only = os.getenv("ZENFIT_ORT_CPU_ONLY", "0") == "1"
        providers = ["CPUExecutionProvider"] if cpu_only else ["CUDAExecutionProvider", "CPUExecutionProvider"]
        try:
            self.session = ort.InferenceSession(str(self.model_path), providers=providers)
            self.providers = list(self.session.get_providers())
            inp = self.session.get_inputs()[0]
            self.input_name = inp.name
            shape = inp.shape
            h = shape[2] if len(shape) > 2 and isinstance(shape[2], int) else 384
            w = shape[3] if len(shape) > 3 and isinstance(shape[3], int) else 288
            self.input_hw = (int(h), int(w))
        except Exception as exc:  # pragma: no cover
            self.session = None
            self.input_name = None
            self.providers = ["CPUExecutionProvider"]
            self.warnings.append(f"RTMW3D runtime fallback: {exc}")

    def _fallback_pose(self, box: Tuple[int, int, int, int]) -> Dict:
        x1, y1, x2, y2 = box
        w = max(float(x2 - x1), 1.0)
        h = max(float(y2 - y1), 1.0)

        template = np.array(
            [
                [0.50, 0.08, 0.00],
                [0.46, 0.07, -0.01],
                [0.54, 0.07, -0.01],
                [0.42, 0.08, -0.02],
                [0.58, 0.08, -0.02],
                [0.40, 0.20, 0.00],
                [0.60, 0.20, 0.00],
                [0.33, 0.36, 0.01],
                [0.67, 0.36, 0.01],
                [0.27, 0.53, 0.02],
                [0.73, 0.53, 0.02],
                [0.44, 0.42, 0.00],
                [0.56, 0.42, 0.00],
                [0.43, 0.62, 0.00],
                [0.57, 0.62, 0.00],
                [0.42, 0.84, 0.02],
                [0.58, 0.84, 0.02],
            ],
            dtype=np.float32,
        )

        joints = []
        for i, _ in enumerate(COCO17_NAMES):
            px = x1 + template[i, 0] * w
            py = y1 + template[i, 1] * h
            pz = template[i, 2] * h
            joints.append([float(px), float(py), float(pz), 0.35])

        return {
            "joints": joints,
            "source": "fallback",
        }

    def _preprocess_crop(self, image_bgr: np.ndarray, bbox: Tuple[int, int, int, int]) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
        h, w = image_bgr.shape[:2]
        x1, y1, x2, y2 = bbox
        bw = x2 - x1
        bh = y2 - y1

        pad = int(max(bw, bh) * 0.15)
        crop = _safe_bbox([x1 - pad, y1 - pad, x2 + pad, y2 + pad], w, h)
        cx1, cy1, cx2, cy2 = crop
        roi = image_bgr[cy1:cy2, cx1:cx2]

        in_h, in_w = self.input_hw
        resized = cv2.resize(roi, (in_w, in_h), interpolation=cv2.INTER_LINEAR)
        x = resized.astype(np.float32)
        # Equivalent to ((rgb/255)-mean)/std but numerically closer to reference runtime.
        x = x[:, :, ::-1]
        x = (x - np.array([123.675, 116.28, 103.53], dtype=np.float32)) / np.array([58.395, 57.12, 57.375], dtype=np.float32)
        x = np.transpose(x, (2, 0, 1))[None, ...]
        return np.ascontiguousarray(x.astype(np.float32)), crop

    def _decode_simcc_outputs(self, outputs: Sequence[np.ndarray], crop: Tuple[int, int, int, int]) -> Optional[Dict]:
        if len(outputs) < 2:
            return None
        simcc_x = np.asarray(outputs[0])
        simcc_y = np.asarray(outputs[1])
        simcc_z = np.asarray(outputs[2]) if len(outputs) > 2 else None
        if simcc_x.ndim != 3 or simcc_y.ndim != 3:
            return None
        if simcc_x.shape[0] != 1 or simcc_y.shape[0] != 1:
            return None
        if simcc_x.shape[1] < 17 or simcc_y.shape[1] < 17:
            return None

        cx1, cy1, cx2, cy2 = crop
        box_w = max(float(cx2 - cx1), 1.0)
        box_h = max(float(cy2 - cy1), 1.0)
        in_h, in_w = self.input_hw

        x_logits = simcc_x[0, :17]
        y_logits = simcc_y[0, :17]
        z_logits = simcc_z[0, :17] if simcc_z is not None and simcc_z.ndim == 3 and simcc_z.shape[0] == 1 else None

        loc_x = np.argmax(x_logits, axis=1).astype(np.float32)
        loc_y = np.argmax(y_logits, axis=1).astype(np.float32)
        loc_z = np.argmax(z_logits, axis=1).astype(np.float32) if z_logits is not None else np.zeros_like(loc_x)

        # split ratio = 2.0 for this export family
        kx = loc_x / 2.0
        ky = loc_y / 2.0
        kz = loc_z / 2.0

        sx = box_w / float(in_w)
        sy = box_h / float(in_h)
        px = kx * sx + float(cx1)
        py = ky * sy + float(cy1)

        z_rel = (kz / (float(in_w) / 2.0) - 1.0) * 2.1744869
        z_scale = max(1.0, 0.5 * max(box_w, box_h))
        pz = z_rel.astype(np.float32) * float(z_scale)

        scores_x = np.max(x_logits, axis=1).astype(np.float32)
        scores_y = np.max(y_logits, axis=1).astype(np.float32)
        if z_logits is not None:
            scores_z = np.max(z_logits, axis=1).astype(np.float32)
            conf = np.minimum(np.minimum(scores_x, scores_y), scores_z)
        else:
            conf = np.minimum(scores_x, scores_y)

        joints = []
        for i in range(17):
            c = float(conf[i])
            if c > 1.0 or c < 0.0:
                c = 1.0 / (1.0 + np.exp(-c))
            joints.append([float(px[i]), float(py[i]), float(pz[i]), float(c)])

        return {
            "joints": joints,
            "source": "onnx",
        }

    def _decode_output_fallback(self, output: np.ndarray, crop: Tuple[int, int, int, int]) -> Dict:
        cx1, cy1, cx2, cy2 = crop
        cw = max(float(cx2 - cx1), 1.0)
        ch = max(float(cy2 - cy1), 1.0)

        points = None
        conf = None
        arr = np.asarray(output)

        if arr.ndim == 3 and arr.shape[1] >= 17 and arr.shape[2] >= 3:
            points = arr[0, :17, :3].astype(np.float32)
            conf = arr[0, :17, 3].astype(np.float32) if arr.shape[2] > 3 else np.ones(17, dtype=np.float32) * 0.6
        elif arr.ndim == 2 and arr.shape[0] >= 17 and arr.shape[1] >= 3:
            points = arr[:17, :3].astype(np.float32)
            conf = arr[:17, 3].astype(np.float32) if arr.shape[1] > 3 else np.ones(17, dtype=np.float32) * 0.6
        elif arr.ndim == 4 and arr.shape[1] >= 17:
            heatmaps = arr[0, :17]
            hh, ww = heatmaps.shape[-2], heatmaps.shape[-1]
            points = np.zeros((17, 3), dtype=np.float32)
            conf = np.zeros((17,), dtype=np.float32)
            for i in range(17):
                hm = heatmaps[i]
                idx = int(np.argmax(hm))
                yy = idx // ww
                xx = idx % ww
                points[i, 0] = (xx / max(ww - 1, 1))
                points[i, 1] = (yy / max(hh - 1, 1))
                points[i, 2] = 0.0
                conf[i] = float(np.max(hm))

        if points is None:
            return self._fallback_pose(crop)

        max_abs = float(np.max(np.abs(points[:, :2])))
        if max_abs <= 2.5:
            points[:, 0] = cx1 + points[:, 0] * cw
            points[:, 1] = cy1 + points[:, 1] * ch
            points[:, 2] = points[:, 2] * ch
        else:
            in_h, in_w = self.input_hw
            points[:, 0] = cx1 + (points[:, 0] / max(in_w, 1)) * cw
            points[:, 1] = cy1 + (points[:, 1] / max(in_h, 1)) * ch
            points[:, 2] = (points[:, 2] / max(in_h, 1)) * ch

        joints = []
        for i in range(17):
            c = float(conf[i]) if conf is not None else 0.6
            if c > 1.0 or c < 0.0:
                c = 1.0 / (1.0 + np.exp(-c))
            joints.append([float(points[i, 0]), float(points[i, 1]), float(points[i, 2]), float(c)])

        return {"joints": joints, "source": "onnx"}

    def predict(self, image_bgr: np.ndarray, bbox_xyxy: List[float]) -> Dict:
        t0 = time.perf_counter()
        warnings = list(self.warnings)

        h, w = image_bgr.shape[:2]
        bbox = _safe_bbox(bbox_xyxy, w, h)

        if self.session is None or self.input_name is None:
            fallback = self._fallback_pose(bbox)
            return {
                **fallback,
                "stage_ms": (time.perf_counter() - t0) * 1000.0,
                "warnings": warnings,
            }

        try:
            x, crop = self._preprocess_crop(image_bgr, bbox)
            outputs = self.session.run(None, {self.input_name: x})
            decoded = self._decode_simcc_outputs(outputs, crop)
            if decoded is None:
                decoded = self._decode_output_fallback(outputs[0], crop)
            decoded["stage_ms"] = (time.perf_counter() - t0) * 1000.0
            decoded["warnings"] = warnings
            return decoded
        except Exception as exc:  # pragma: no cover
            warnings.append(f"RTMW3D exception: {exc}")
            fallback = self._fallback_pose(bbox)
            return {
                **fallback,
                "stage_ms": (time.perf_counter() - t0) * 1000.0,
                "warnings": warnings,
            }
