from __future__ import annotations

import time
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

try:
    import onnxruntime as ort
except Exception:  # pragma: no cover
    ort = None

from .ort_bootstrap import bootstrap_onnxruntime


@dataclass
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float

    def is_valid(self) -> bool:
        return self.x2 > self.x1 and self.y2 > self.y1

    def clip(self, width: int, height: int) -> "BBox":
        w = max(1, int(width))
        h = max(1, int(height))
        return BBox(
            float(np.clip(self.x1, 0, w - 1)),
            float(np.clip(self.y1, 0, h - 1)),
            float(np.clip(self.x2, 0, w - 1)),
            float(np.clip(self.y2, 0, h - 1)),
        )

    def to_list(self) -> List[float]:
        return [self.x1, self.y1, self.x2, self.y2]


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float) -> List[int]:
    if boxes.size == 0:
        return []

    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]

    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]

    keep: List[int] = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)

        inds = np.where(iou <= iou_thresh)[0]
        order = order[inds + 1]
    return keep


class YOLOXDetector:
    def __init__(
        self,
        model_path: Optional[str] = None,
        input_size: int = 640,
        score_threshold: float = 0.25,
        nms_threshold: float = 0.45,
    ) -> None:
        self.input_size = input_size
        self.score_threshold = score_threshold
        self.nms_threshold = nms_threshold
        self.model_path = self._resolve_model_path(model_path)

        self.session = None
        self.input_name = None
        self.input_meta = None
        self.is_fp16 = False
        self.is_uint8 = False
        self.layout = "NCHW"
        self.expects_rgb = True
        self.normalize = True

        self.providers: List[str] = ["CPUExecutionProvider"]
        self.warnings: List[str] = []

        self._init_runtime()

    def _resolve_model_path(self, model_path: Optional[str]) -> Optional[Path]:
        candidates = []
        if model_path:
            candidates.append(Path(model_path))
        candidates.extend(
            [
                Path("speedy_learning/models/yolox_s_humanart_fp32.onnx"),
                Path("workspace/backend/models/onnx/yolox_s_humanart_fp32.onnx"),
                Path("workspace/backend/models/onnx/yolox_tiny_humanart_fp32.onnx"),
                Path("yolox_s_humanart_fp32.onnx"),
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
            self.warnings.append("YOLOX model missing")
            return

        boot = bootstrap_onnxruntime()
        for w in boot.get("warnings", []):
            self.warnings.append(f"ORT bootstrap: {w}")

        cpu_only = os.getenv("ZENFIT_ORT_CPU_ONLY", "0") == "1"
        providers = ["CPUExecutionProvider"] if cpu_only else ["CUDAExecutionProvider", "CPUExecutionProvider"]
        try:
            self.session = ort.InferenceSession(str(self.model_path), providers=providers)
            self.providers = list(self.session.get_providers())
            self.input_meta = self.session.get_inputs()[0]
            self.input_name = self.input_meta.name
            self.is_fp16 = "float16" in self.input_meta.type
            self.is_uint8 = "uint8" in self.input_meta.type

            shape = getattr(self.input_meta, "shape", None)
            if shape and len(shape) == 4:
                d1, d2, d3 = shape[1], shape[2], shape[3]
                if isinstance(d3, int) and d3 in (1, 3):
                    self.layout = "NHWC"
                    h = d1
                    w = d2
                else:
                    self.layout = "NCHW"
                    h = d2
                    w = d3
                if isinstance(h, int) and isinstance(w, int) and h > 0 and w > 0:
                    self.input_size = int(w)

            # HumanArt YOLOX ONNX exports in this repo expect float tensor in [0..255], not [0..1].
            # Keeping raw-scale fixes confidence collapse to ~0.
            model_name = str(self.model_path).lower()
            if "yolox" in model_name:
                self.normalize = False
            else:
                self.normalize = not self.is_uint8
        except Exception as exc:  # pragma: no cover
            self.session = None
            self.input_name = None
            self.providers = ["CPUExecutionProvider"]
            self.warnings.append(f"YOLOX runtime fallback: {exc}")

    def _preprocess(self, image_bgr: np.ndarray) -> Tuple[np.ndarray, float, int, int]:
        h, w = image_bgr.shape[:2]
        scale = min(self.input_size / max(h, 1), self.input_size / max(w, 1))
        nh = int(round(h * scale))
        nw = int(round(w * scale))

        resized = cv2.resize(image_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((self.input_size, self.input_size, 3), 114, dtype=np.uint8)
        top = (self.input_size - nh) // 2
        left = (self.input_size - nw) // 2
        canvas[top:top + nh, left:left + nw] = resized

        image = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB) if self.expects_rgb else canvas

        if self.is_uint8:
            tensor = image.astype(np.uint8)
            if self.layout == "NCHW":
                tensor = tensor.transpose(2, 0, 1)[None, ...]
            else:
                tensor = tensor[None, ...]
            return np.ascontiguousarray(tensor), scale, left, top

        tensor = image.astype(np.float32)
        if self.normalize:
            tensor = tensor / 255.0

        if self.layout == "NCHW":
            tensor = tensor.transpose(2, 0, 1)[None, ...]
        else:
            tensor = tensor[None, ...]

        tensor = tensor.astype(np.float16 if self.is_fp16 else np.float32)
        return np.ascontiguousarray(tensor), scale, left, top

    def _fallback_box(self, image_bgr: np.ndarray) -> Dict:
        h, w = image_bgr.shape[:2]
        pad_w = int(w * 0.2)
        pad_h = int(h * 0.1)
        return {
            "bbox_xyxy": [pad_w, pad_h, w - pad_w, h - pad_h],
            "score": 0.15,
            "class_id": 0,
            "source": "fallback",
        }

    @staticmethod
    def _to_2d(out: np.ndarray) -> Optional[np.ndarray]:
        arr = np.asarray(out)
        if arr.ndim == 3 and arr.shape[0] == 1:
            return arr[0]
        if arr.ndim == 2:
            return arr
        return None

    def _decode_fused_layout(self, out: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        arr = self._to_2d(out)
        if arr is None or arr.shape[1] < 5:
            return np.zeros((0, 4), dtype=np.float32), np.zeros((0,), dtype=np.float32)

        boxes = arr[:, :4].astype(np.float32)
        score_col = 4
        if arr.shape[1] >= 6:
            c4 = arr[:, 4].astype(np.float32)
            c5 = arr[:, 5].astype(np.float32)
            if float(np.max(c4)) <= 1e-6 and float(np.max(c5)) > float(np.max(c4)):
                score_col = 5
            elif float(np.max(c4)) > 1.0 and float(np.max(c5)) <= 1.0:
                score_col = 5

        scores = arr[:, score_col].astype(np.float32)
        if float(np.max(scores)) > 1.0 or float(np.min(scores)) < 0.0:
            scores = _sigmoid(scores)

        # Heuristic layout check: xyxy vs cxcywh
        xyxy = boxes.copy()
        valid_xyxy = np.logical_and(xyxy[:, 2] > xyxy[:, 0], xyxy[:, 3] > xyxy[:, 1])
        xyxy_ratio = float(np.mean(valid_xyxy)) if len(valid_xyxy) else 0.0

        cxcywh = boxes.copy()
        cx = cxcywh[:, 0]
        cy = cxcywh[:, 1]
        bw = np.abs(cxcywh[:, 2])
        bh = np.abs(cxcywh[:, 3])
        cxcywh[:, 0] = cx - bw * 0.5
        cxcywh[:, 1] = cy - bh * 0.5
        cxcywh[:, 2] = cx + bw * 0.5
        cxcywh[:, 3] = cy + bh * 0.5
        valid_cxcywh = np.logical_and(cxcywh[:, 2] > cxcywh[:, 0], cxcywh[:, 3] > cxcywh[:, 1])
        cxcywh_ratio = float(np.mean(valid_cxcywh)) if len(valid_cxcywh) else 0.0

        chosen = xyxy if xyxy_ratio >= cxcywh_ratio else cxcywh
        mask = scores >= self.score_threshold
        return chosen[mask], scores[mask]

    @staticmethod
    def _restore_bbox_from_letterbox(
        box_xyxy: np.ndarray,
        scale: float,
        pad_x: int,
        pad_y: int,
        width: int,
        height: int,
    ) -> BBox:
        x1, y1, x2, y2 = box_xyxy.astype(np.float32)
        x1 = (x1 - pad_x) / max(scale, 1e-6)
        y1 = (y1 - pad_y) / max(scale, 1e-6)
        x2 = (x2 - pad_x) / max(scale, 1e-6)
        y2 = (y2 - pad_y) / max(scale, 1e-6)
        return BBox(float(x1), float(y1), float(x2), float(y2)).clip(width, height)

    def detect(self, image_bgr: np.ndarray) -> Dict:
        t0 = time.perf_counter()
        warnings = list(self.warnings)

        if self.session is None or self.input_name is None:
            fallback = self._fallback_box(image_bgr)
            return {
                **fallback,
                "stage_ms": (time.perf_counter() - t0) * 1000.0,
                "warnings": warnings,
            }

        tensor, scale, left, top = self._preprocess(image_bgr)

        try:
            outputs = self.session.run(None, {self.input_name: tensor})
            boxes, scores = self._decode_fused_layout(outputs[0])
            if boxes.size == 0:
                fallback = self._fallback_box(image_bgr)
                warnings.append("YOLOX: no candidate above threshold")
                return {
                    **fallback,
                    "stage_ms": (time.perf_counter() - t0) * 1000.0,
                    "warnings": warnings,
                }

            keep = _nms(boxes, scores, self.nms_threshold)
            if not keep:
                fallback = self._fallback_box(image_bgr)
                warnings.append("YOLOX: no candidate after NMS")
                return {
                    **fallback,
                    "stage_ms": (time.perf_counter() - t0) * 1000.0,
                    "warnings": warnings,
                }

            h, w = image_bgr.shape[:2]
            best_idx = int(keep[np.argmax(scores[keep])]) if len(keep) > 1 else int(keep[0])
            bbox = self._restore_bbox_from_letterbox(boxes[best_idx], scale, left, top, w, h)
            if not bbox.is_valid():
                fallback = self._fallback_box(image_bgr)
                warnings.append("YOLOX: invalid bbox after restore")
                return {
                    **fallback,
                    "stage_ms": (time.perf_counter() - t0) * 1000.0,
                    "warnings": warnings,
                }

            return {
                "bbox_xyxy": bbox.to_list(),
                "score": float(scores[best_idx]),
                "class_id": 0,
                "source": "onnx",
                "stage_ms": (time.perf_counter() - t0) * 1000.0,
                "warnings": warnings,
            }
        except Exception as exc:  # pragma: no cover
            fallback = self._fallback_box(image_bgr)
            warnings.append(f"YOLOX exception: {exc}")
            return {
                **fallback,
                "stage_ms": (time.perf_counter() - t0) * 1000.0,
                "warnings": warnings,
            }
