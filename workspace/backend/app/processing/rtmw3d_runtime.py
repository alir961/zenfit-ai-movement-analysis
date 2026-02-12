import logging
import os
import sys
import warnings
from typing import Optional, List, Dict, Any
import runpy

# Silence noisy dependency warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import numpy as np
import torch
import cv2
import time
import traceback

# 1. Setup paths for custom modules
PROJ_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
RTMP_PATH = os.path.join(PROJ_ROOT, "third_party", "mmpose", "projects", "rtmpose3d")

if os.path.exists(RTMP_PATH):
    if RTMP_PATH not in sys.path:
        sys.path.append(RTMP_PATH)
    try:
        import rtmpose3d
    except ImportError:
        logging.getLogger("zenfit.rtmw3d").warning("Could not import custom rtmpose3d modules from %s", RTMP_PATH)

# Dependencies MMPose
try:
    from mmpose.apis import init_model, inference_topdown
    from mmdet.apis import DetInferencer, inference_detector
    from mmengine.registry import DefaultScope
    HAS_MMPOSE = True
except ImportError:
    HAS_MMPOSE = False

try:
    from mmdet.utils import register_all_modules as mmdet_register_all_modules
except Exception:
    mmdet_register_all_modules = None

# Dependencies ONNX
try:
    import onnxruntime as ort
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False

from ..contracts.events import PoseFrame, PoseJoint, JOINT_NAMES
from .onnx_detector_runtime import OnnxDetectorRuntime

logger = logging.getLogger("zenfit.rtmw3d")
_COCO_WHOLEBODY_NAMES_CACHE: Optional[List[str]] = None


def _load_coco_wholebody_names() -> List[str]:
    global _COCO_WHOLEBODY_NAMES_CACHE
    if _COCO_WHOLEBODY_NAMES_CACHE is not None:
        return _COCO_WHOLEBODY_NAMES_CACHE
    cfg = os.path.join(PROJ_ROOT, "third_party", "mmpose", "configs", "_base_", "datasets", "coco_wholebody.py")
    names: List[str] = []
    try:
        data = runpy.run_path(cfg)
        dataset_info = data.get("dataset_info", {})
        keypoint_info = dataset_info.get("keypoint_info", {})
        for _, v in sorted(keypoint_info.items(), key=lambda kv: int(kv[0])):
            names.append(str(v.get("name", f"kpt_{len(names)}")))
    except Exception:
        names = list(JOINT_NAMES)
    _COCO_WHOLEBODY_NAMES_CACHE = names
    return names

class RTMW3DRunner:
    """
    Robust RTMW3D Wrapper (PyTorch & ONNX).
    Handles model initialization, inference, and conversion to ZenFit internal schema.
    """

    MODEL_CONFIGS = {
        "l": {
            "config": os.path.join(RTMP_PATH, "configs", "rtmw3d-l_8xb64_cocktail14-384x288.py"),
            "checkpoint": os.path.join(PROJ_ROOT, "rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth"),
            "onnx": os.path.join(PROJ_ROOT, "rtmw3d_l_fp16.onnx")
        },
        "x": {
            "config": os.path.join(RTMP_PATH, "configs", "rtmw3d-x_8xb32_cocktail14-384x288.py"),
            "checkpoint": os.path.join(PROJ_ROOT, "rtmw3d-x_8xb64_cocktail14-384x288-b0a0eab7_20240626.pth"),
            "onnx": os.path.join(PROJ_ROOT, "rtmw3d_x.onnx")
        }
    }

    DET_ALIAS = "rtmdet_m_8xb32-300e_coco"
    DEFAULT_PROVIDERS = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    _MMDET_REGISTERED = False

    def __init__(
        self,
        model_size: str = "l",
        device: str = "auto",
        backend: str = "auto",
        track_interval: int = 10,
        debug_timing: bool = False,
        detector: str = "rtmdet",
        det_config: Optional[str] = None,
        det_checkpoint: Optional[str] = None,
        det_score_thr: float = 0.5,
        det_input_size: Optional[tuple[int, int]] = None,
        detector_backend: str = "auto",
        detector_model: str = "rtmdet_tiny",
        detector_variant: str = "fp16",
        pose_variant: str = "fp16",
        providers_order: Optional[list[str]] = None,
        onnx_artifacts_dir: str = "workspace/backend/models/onnx",
        detector_model_path: Optional[str] = None,
    ) -> None:
        self.model_size = model_size.lower().strip()
        self.device = device
        self.backend = (backend or "auto").lower().strip()
        self.ready = False
        self._detector = None
        self._detector_type = (detector or "rtmdet").lower().strip()
        self._det_config = det_config
        self._det_checkpoint = det_checkpoint
        self._det_score_thr = float(det_score_thr)
        self._det_input_size = det_input_size
        self.detector_backend = (detector_backend or "auto").lower().strip()
        self.detector_model = (detector_model or "rtmdet_tiny").lower().strip()
        self.detector_variant = (detector_variant or "fp16").lower().strip()
        self.pose_variant = (pose_variant or "fp16").lower().strip()
        self.providers_order = list(providers_order) if providers_order else list(self.DEFAULT_PROVIDERS)
        self.onnx_artifacts_dir = (
            onnx_artifacts_dir
            if os.path.isabs(onnx_artifacts_dir)
            else os.path.join(PROJ_ROOT, onnx_artifacts_dir)
        )
        self.detector_model_path = None
        if detector_model_path:
            self.detector_model_path = (
                detector_model_path
                if os.path.isabs(detector_model_path)
                else os.path.join(PROJ_ROOT, detector_model_path)
            )
        # Runtime status exposed for benchmarks/diagnostics.
        self.last_error_reason = ""
        # Default person-foot specific threshold if caller kept generic default.
        if self.detector_model == "person_foot_qualcomm" and float(det_score_thr) == 0.5:
            self._det_score_thr = 0.35
        self._bbox_expand = self._default_bbox_expand()
        self._pose_model = None
        self._ort_session = None
        self._input_name = None
        self.use_onnx = False
        self.debug_timing = bool(debug_timing)
        self._mp_pose = None
        self._mp_instance = None
        self._onnx_detector_runtime: Optional[OnnxDetectorRuntime] = None
        self._pose_provider: Optional[str] = None
        
        # Tracking state
        self._last_bbox = None
        self._track_count = 0
        self._track_interval = max(0, int(track_interval)) # Run heavy detector every N frames

        if not HAS_MMPOSE:
            logger.error("MMPose or MMDetection not installed. RTMW3D runner will not work.")
            return

        if self.device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Normalization constants (ImageNet defaults)
        self._mean_t = torch.tensor([123.675, 116.28, 103.53], device=self.device).view(1, 3, 1, 1)
        self._std_t = torch.tensor([58.395, 57.12, 57.375], device=self.device).view(1, 3, 1, 1)

        # Initialize Detector
        if not self._init_detector():
            return

        cfg_entry = self.MODEL_CONFIGS.get(self.model_size, self.MODEL_CONFIGS["l"])

        # Try ONNX First if available and HAS_ONNX
        onnx_path = self._resolve_pose_onnx_path(cfg_entry)
        if self.backend == "onnx":
            if HAS_ONNX and onnx_path and os.path.exists(onnx_path):
                self._init_onnx(onnx_path)
            else:
                logger.error("ONNX backend requested but model not available: %s", onnx_path)
            return

        if self.backend == "pytorch":
            self._init_pytorch(cfg_entry)
            return

        if HAS_ONNX and onnx_path and os.path.exists(onnx_path):
            self._init_onnx(onnx_path)
            if self.ready:
                return

        # Fallback to PyTorch
        self._init_pytorch(cfg_entry)

    def _resolve_pose_onnx_path(self, cfg_entry: dict) -> str:
        if self.model_size != "l":
            return cfg_entry.get("onnx")
        artifact = os.path.join(self.onnx_artifacts_dir, f"rtmw3d_l_{self.pose_variant}.onnx")
        if os.path.exists(artifact):
            return artifact
        if self.pose_variant == "fp16":
            return cfg_entry.get("onnx")
        fallback = os.path.join(PROJ_ROOT, f"rtmw3d_l_{self.pose_variant}.onnx")
        if os.path.exists(fallback):
            return fallback
        return cfg_entry.get("onnx")

    def _init_onnx(self, onnx_path: str):
        try:
            logger.info("Loading ONNX model from %s...", onnx_path)
            providers = self._resolve_providers()
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess_options.enable_mem_pattern = True
            sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            # Keep ORT warnings quiet in normal runtime.
            sess_options.log_severity_level = 3
            self._ort_session = ort.InferenceSession(onnx_path, sess_options=sess_options, providers=providers)
            self._input_name = self._ort_session.get_inputs()[0].name
            self._input_type = self._ort_session.get_inputs()[0].type
            self._is_fp16 = "float16" in self._input_type
            providers_in_use = self._ort_session.get_providers()
            self._pose_provider = providers_in_use[0] if providers_in_use else None
            
            self.use_onnx = True
            self.ready = True
            logger.info(
                "ONNX Runtime initialized. Input: %s Provider: %s",
                self._input_type,
                self._pose_provider or "unknown",
            )
        except Exception as e:
            logger.error("ONNX init failed: %s. Falling back to PyTorch.", e)
            self.use_onnx = False

    def _resolve_providers(self) -> list[str]:
        available = set(ort.get_available_providers()) if HAS_ONNX else set()
        filtered = [p for p in self.providers_order if p in available]
        if not filtered:
            filtered = ["CPUExecutionProvider"]
        if self.device != "cuda":
            filtered = [p for p in filtered if p == "CPUExecutionProvider"] or ["CPUExecutionProvider"]
        return filtered

    def _resolve_detector_onnx_path(self) -> str:
        if self.detector_model_path:
            return self.detector_model_path
        if self.detector_model == "person_foot_qualcomm":
            return os.path.join(self.onnx_artifacts_dir, "person_foot_detection.onnx")
        filename = f"{self.detector_model}_{self.detector_variant}.onnx"
        return os.path.join(self.onnx_artifacts_dir, filename)

    def _default_detector_input_size(self) -> tuple[int, int]:
        if self.detector_model == "person_foot_qualcomm":
            return (640, 480)
        if self.detector_model == "rtmdet_nano":
            return (320, 320)
        if self.detector_model == "yolox_tiny_humanart":
            return (416, 416)
        return (640, 640)

    def _default_bbox_expand(self) -> tuple[float, float, float]:
        if self.detector_model == "person_foot_qualcomm":
            return (0.10, 0.25, 0.05)
        return (0.0, 0.0, 0.0)

    def _expand_bbox(self, bbox: np.ndarray, frame_shape: tuple[int, int, int]) -> np.ndarray:
        ax, by, gy = self._bbox_expand
        if ax == 0.0 and by == 0.0 and gy == 0.0:
            return bbox.astype(np.float32)
        x1, y1, x2, y2 = [float(v) for v in bbox]
        w = max(1.0, x2 - x1)
        h = max(1.0, y2 - y1)
        x1 -= ax * w
        x2 += ax * w
        y1 -= by * h
        y2 += gy * h
        fw = float(frame_shape[1] - 1)
        fh = float(frame_shape[0] - 1)
        x1 = max(0.0, min(fw, x1))
        y1 = max(0.0, min(fh, y1))
        x2 = max(0.0, min(fw, x2))
        y2 = max(0.0, min(fh, y2))
        if x2 <= x1 or y2 <= y1:
            return bbox.astype(np.float32)
        return np.array([x1, y1, x2, y2], dtype=np.float32)

    def _init_detector(self) -> bool:
        det_type = self._detector_type
        try:
            if not self.__class__._MMDET_REGISTERED:
                if mmdet_register_all_modules is not None:
                    try:
                        mmdet_register_all_modules(init_default_scope=True)
                    except Exception:
                        pass
                self.__class__._MMDET_REGISTERED = True

            if self.detector_backend in ("auto", "onnx"):
                onnx_path = self._resolve_detector_onnx_path()
                candidate_paths = [onnx_path]
                if self.detector_variant == "fp16" and self.detector_model != "person_foot_qualcomm":
                    fp32_fallback = os.path.join(
                        self.onnx_artifacts_dir,
                        f"{self.detector_model}_fp32.onnx",
                    )
                    if fp32_fallback not in candidate_paths:
                        candidate_paths.append(fp32_fallback)
                selected_path = next((p for p in candidate_paths if os.path.exists(p)), None)
                if selected_path:
                    try:
                        profile = {
                            "expects_rgb": True,
                            # YOLOX HumanArt ONNX exports in this repo expect float input
                            # without /255 normalization, while RTMDet expects normalized input.
                            "normalize": (
                                False
                                if self.detector_model in ("yolox_tiny_humanart", "yolox_s_humanart")
                                else self.detector_model != "person_foot_qualcomm"
                            ),
                            "decoder": "qualcomm_dense_v1" if self.detector_model == "person_foot_qualcomm" else "generic",
                        }
                        self._onnx_detector_runtime = OnnxDetectorRuntime(
                            model_path=selected_path,
                            providers=self._resolve_providers(),
                            score_thr=self._det_score_thr,
                            input_size=self._det_input_size or self._default_detector_input_size(),
                            person_class_id=(
                                0
                                if self.detector_model in ("person_foot_qualcomm", "yolox_tiny_humanart", "yolox_s_humanart")
                                else None
                            ),
                            nms_iou_thr=0.45,
                            model_profile=profile,
                        )
                        effective_variant = self.detector_variant
                        if selected_path != onnx_path:
                            effective_variant = "fp32"
                            self.last_error_reason = (
                                f"detector_fp16_fallback_to_fp32:{onnx_path}"
                            )
                            logger.warning(
                                "Detector ONNX variant %s unavailable/invalid, fallback to fp32.",
                                self.detector_variant,
                            )
                            self.detector_variant = "fp32"
                        logger.info(
                            "Initialized ONNX detector %s (%s) provider=%s",
                            self.detector_model,
                            effective_variant,
                            self._onnx_detector_runtime.active_providers[0]
                            if self._onnx_detector_runtime.active_providers
                            else "unknown",
                        )
                        self.last_error_reason = ""
                        return True
                    except Exception as exc:
                        logger.error("ONNX detector init failed: %s", exc)
                        if self.detector_variant == "fp16":
                            self.last_error_reason = f"detector_fp16_invalid:{exc}"
                        else:
                            self.last_error_reason = str(exc)
                        if self.detector_backend == "onnx":
                            return False
                elif self.detector_backend == "onnx":
                    logger.error("ONNX detector model missing: %s", onnx_path)
                    self.last_error_reason = (
                        "missing_local_source"
                        if self.detector_model == "person_foot_qualcomm"
                        else f"missing_detector_onnx:{onnx_path}"
                    )
                    return False

            if self.detector_backend == "onnx":
                return False

            if det_type == "mediapipe":
                try:
                    import mediapipe as mp
                except Exception:
                    logger.error("mediapipe_not_installed")
                    return False
                self._mp_pose = mp.solutions.pose
                self._mp_instance = self._mp_pose.Pose(
                    static_image_mode=True,
                    model_complexity=0,
                    enable_segmentation=False,
                    min_detection_confidence=0.5,
                )
                logger.info("Initialized MediaPipe Pose for bbox.")
                return True

            if det_type == "mmdeploy":
                try:
                    import mmdeploy
                    _ = mmdeploy  # avoid lint
                except Exception:
                    logger.error("mmdeploy_not_installed")
                    return False
                logger.error("mmdeploy backend requested but not implemented yet.")
                return False

            if det_type in ("yolox_tiny", "yolox_s"):
                from mmdet.apis import init_detector
                def _resolve_yolox_paths(which: str) -> tuple[str, str]:
                    if which == "yolox_tiny":
                        cfg_path = os.path.join(
                            PROJ_ROOT,
                            "third_party",
                            "mmpose",
                            "projects",
                            "rtmpose",
                            "yolox",
                            "humanart",
                            "yolox_tiny_8xb8-300e_humanart.py",
                        )
                        ckpt_path = os.path.join(
                            PROJ_ROOT,
                            "yolox_tiny_8xb8-300e_humanart-6f3252f9.pth",
                        )
                    else:
                        cfg_path = os.path.join(
                            PROJ_ROOT,
                            "third_party",
                            "mmpose",
                            "projects",
                            "rtmpose",
                            "yolox",
                            "humanart",
                            "yolox_s_8xb8-300e_humanart.py",
                        )
                        ckpt_path = os.path.join(
                            PROJ_ROOT,
                            "yolox_s_8xb8-300e_humanart-3ef259a7.pth",
                        )
                    return cfg_path, ckpt_path

                cfg, ckpt = _resolve_yolox_paths(det_type)
                cfg = self._det_config or cfg
                ckpt = self._det_checkpoint or ckpt
                if os.path.exists(cfg) and os.path.exists(ckpt):
                    logger.info("Initializing detector %s...", det_type)
                    self._detector = init_detector(cfg, ckpt, device=self.device)
                    return True

                if det_type == "yolox_tiny" and self._det_config is None and self._det_checkpoint is None:
                    logger.warning("YOLOX tiny missing, falling back to yolox_s...")
                    cfg, ckpt = _resolve_yolox_paths("yolox_s")
                    if not os.path.exists(cfg):
                        logger.error("Detector config not found: %s", cfg)
                        return False
                    if not os.path.exists(ckpt):
                        logger.error("Detector checkpoint not found: %s", ckpt)
                        return False
                    self._detector_type = "yolox_s"
                    logger.info("Initializing detector yolox_s...")
                    self._detector = init_detector(cfg, ckpt, device=self.device)
                    return True

                if not os.path.exists(cfg):
                    logger.error("Detector config not found: %s", cfg)
                if not os.path.exists(ckpt):
                    logger.error("Detector checkpoint not found: %s", ckpt)
                return False

            if self.detector_model in ("yolox_tiny_humanart", "yolox_s_humanart"):
                from mmdet.apis import init_detector
                det_name = "yolox_tiny" if "tiny" in self.detector_model else "yolox_s"
                self._detector_type = det_name
                self._det_config = self._det_config or os.path.join(
                    PROJ_ROOT,
                    "third_party",
                    "mmpose",
                    "projects",
                    "rtmpose",
                    "yolox",
                    "humanart",
                    "yolox_tiny_8xb8-300e_humanart.py" if det_name == "yolox_tiny" else "yolox_s_8xb8-300e_humanart.py",
                )
                self._det_checkpoint = self._det_checkpoint or os.path.join(
                    PROJ_ROOT,
                    "yolox_tiny_8xb8-300e_humanart-6f3252f9.pth"
                    if det_name == "yolox_tiny"
                    else "yolox_s_8xb8-300e_humanart-3ef259a7.pth",
                )
                if not os.path.exists(self._det_config) or not os.path.exists(self._det_checkpoint):
                    logger.error("YOLOX detector files missing cfg=%s ckpt=%s", self._det_config, self._det_checkpoint)
                    return False
                logger.info("Initializing detector %s...", self._detector_type)
                self._detector = init_detector(self._det_config, self._det_checkpoint, device=self.device)
                return True

            if self.detector_model in ("rtmdet_nano", "rtmdet_tiny"):
                from mmdet.apis import DetInferencer
                alias = "rtmdet_tiny_8xb32-300e_coco"
                logger.info("Initializing detector %s...", alias)
                det_inf = DetInferencer(alias, device=self.device)
                self._detector = det_inf.model
                return True

            # Default: RTMDet via DetInferencer alias
            from mmdet.apis import DetInferencer
            logger.info("Initializing detector %s...", self.DET_ALIAS)
            det_inf = DetInferencer(self.DET_ALIAS, device=self.device)
            self._detector = det_inf.model
            return True
        except Exception as e:
            logger.error("Failed to load detector: %s", e)
            self.last_error_reason = str(e)
            return False

    def _detect_bbox(self, frame_bgr: np.ndarray) -> Optional[np.ndarray]:
        if self._onnx_detector_runtime is not None:
            bbox = self._onnx_detector_runtime.detect_one(frame_bgr)
            if bbox is None and self._onnx_detector_runtime.last_error:
                self.last_error_reason = self._onnx_detector_runtime.last_error
            return bbox

        if self._detector is None and self._detector_type not in ("mediapipe", "mmdeploy"):
            return None

        # Optional resize override
        frame = frame_bgr
        orig_h, orig_w = frame.shape[:2]
        if self._det_input_size:
            frame = cv2.resize(frame, self._det_input_size)

        if self._detector_type == "mediapipe":
            if self._mp_instance is None:
                return None
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._mp_instance.process(rgb)
            if not results.pose_landmarks:
                return None
            xs = [lm.x for lm in results.pose_landmarks.landmark]
            ys = [lm.y for lm in results.pose_landmarks.landmark]
            h, w = frame.shape[:2]
            x1 = max(0, int(min(xs) * w))
            y1 = max(0, int(min(ys) * h))
            x2 = min(w, int(max(xs) * w))
            y2 = min(h, int(max(ys) * h))
            if self._det_input_size:
                scale_x = float(orig_w) / float(w)
                scale_y = float(orig_h) / float(h)
                x1 = int(x1 * scale_x)
                y1 = int(y1 * scale_y)
                x2 = int(x2 * scale_x)
                y2 = int(y2 * scale_y)
            if x2 <= x1 or y2 <= y1:
                return None
            return np.array([x1, y1, x2, y2], dtype=np.float32)

        if self._detector_type == "mmdeploy":
            return None

        with DefaultScope.overwrite_default_scope('mmdet'):
            det_results = inference_detector(self._detector, frame)

        pred = det_results.pred_instances
        scores = pred.scores
        bboxes = pred.bboxes
        if scores is None or bboxes is None:
            return None
        mask = scores > self._det_score_thr
        if not torch.any(mask):
            return None
        masked_scores = scores[mask]
        best_local = torch.argmax(masked_scores)
        best_idx = torch.nonzero(mask, as_tuple=False)[best_local].item()
        bbox = bboxes[best_idx].detach().cpu().numpy()
        if self._det_input_size:
            scale_x = float(orig_w) / float(frame.shape[1])
            scale_y = float(orig_h) / float(frame.shape[0])
            bbox = np.array(
                [bbox[0] * scale_x, bbox[1] * scale_y, bbox[2] * scale_x, bbox[3] * scale_y],
                dtype=np.float32,
            )
        return bbox

    def _init_pytorch(self, cfg_entry: dict):
        try:
            logger.info("Initializing PyTorch pose model from %s...", cfg_entry["config"])
            
            if not os.path.exists(cfg_entry["config"]):
                raise FileNotFoundError(f"Config file not found: {cfg_entry['config']}")
            if not os.path.exists(cfg_entry["checkpoint"]):
                raise FileNotFoundError(f"Checkpoint file not found: {cfg_entry['checkpoint']}")

            self._pose_model = init_model(cfg_entry["config"], cfg_entry["checkpoint"], device=self.device)
            self.ready = True
            logger.info("RTMW3D runner initialized with size %s on %s", self.model_size, self.device)
        except Exception as exc:
            logger.error("RTMW3D runner failed to initialize: %s", exc)
            self.ready = False

    def infer(
        self,
        frame_bgr: np.ndarray,
        input_size: Optional[tuple[int, int]] = None,
        bbox_override: Optional[np.ndarray] = None,
    ) -> Optional[PoseFrame]:
        has_detector = self._detector is not None or self._onnx_detector_runtime is not None or self._detector_type in ("mediapipe", "mmdeploy")
        if not self.ready or not has_detector:
            return None

        try:
            h_img, w_img = frame_bgr.shape[:2]
            t0 = time.perf_counter()
            
            # --- Detection Logic with Tracking ---
            det_ms = 0.0
            if bbox_override is not None:
                target_bbox = np.array(bbox_override, dtype=np.float32)
                if target_bbox.ndim == 1:
                    target_bbox = target_bbox[None, :]
            elif self._last_bbox is not None and self._track_count < self._track_interval:
                # Reuse last valid bbox
                target_bbox = self._last_bbox
                self._track_count += 1
            else:
                # 1. Run Detection
                bbox = self._detect_bbox(frame_bgr)
                t_det_done = time.perf_counter()
                det_ms = (t_det_done - t0) * 1000
                if bbox is None:
                    self._last_bbox = None
                    self._track_count = 0
                    return None
                bbox = self._expand_bbox(np.array(bbox, dtype=np.float32), frame_bgr.shape)
                target_bbox = np.array([bbox], dtype=np.float32)
                self._last_bbox = target_bbox
                self._track_count = 0
            if bbox_override is not None:
                target_bbox[0] = self._expand_bbox(target_bbox[0], frame_bgr.shape)

            # 2. Pose Inference
            if self.use_onnx:
                res = self._infer_onnx(frame_bgr, target_bbox[0])
            else:
                with torch.inference_mode():
                    res = self._infer_pytorch(frame_bgr, target_bbox)
            
            t_total = (time.perf_counter() - t0) * 1000
            det_ms = (t_det_done - t0) * 1000 if 't_det_done' in locals() else 0.0
            
            if self.debug_timing:
                print(
                    f"DEBUG | {self.model_size} | Det: {det_ms:.1f}ms | Pose: {t_total-det_ms:.1f}ms | Total: {t_total:.1f}ms",
                    flush=True,
                )
            
            return res

        except Exception as e:
            logger.error("Inference RTMW3D failed: %s", e)
            traceback.print_exc()
            return None

    def _infer_pytorch(self, frame, bboxes):
        pose_results = inference_topdown(self._pose_model, frame, bboxes=bboxes)
        if not pose_results: return None

        p0 = pose_results[0]
        inst = p0.pred_instances
        
        kpts_3d = inst.keypoints[0] # (N, 3) Meters? Actually for RTMW3D usually raw coordinates, need check
        # NOTE: RTMW3D PyTorch output usually includes pixels in keypoints? 
        # Actually RTMW3D output usually [x, y, z] relative to root?
        
        # Let's trust standard API for now as it worked in labs.py
        kpts_2d = inst.transformed_keypoints[0] # (N, 2) Pixels
        kpt_scores = inst.keypoint_scores[0]
        
        return self._pack_results(kpts_3d, kpts_2d, kpt_scores, frame.shape)

    def _infer_onnx(self, frame, bbox):
        try:
            t0 = time.perf_counter()
            x1, y1, x2, y2 = bbox
            input_w, input_h = 288, 384
            
            # 1. CPU pre-processing (avoid GPU->CPU sync overhead)
            w, h = x2 - x1, y2 - y1
            pad_x = max(0, int(w * 0.1))
            pad_y = max(0, int(h * 0.1))
            x1 = max(0, int(x1 - pad_x))
            y1 = max(0, int(y1 - pad_y))
            x2 = min(frame.shape[1], int(x2 + pad_x))
            y2 = min(frame.shape[0], int(y2 + pad_y))

            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                return None

            # BGR -> RGB, resize, HWC -> CHW, normalize
            crop = crop[:, :, ::-1]
            resized = cv2.resize(crop, (input_w, input_h), interpolation=cv2.INTER_LINEAR)
            inp = resized.astype(np.float32)
            inp = (inp - np.array([123.675, 116.28, 103.53], dtype=np.float32)) / np.array([58.395, 57.12, 57.375], dtype=np.float32)
            inp = inp.transpose(2, 0, 1)[None, ...]

            if self._is_fp16:
                inp = inp.astype(np.float16)

            inp_numpy = np.ascontiguousarray(inp)
            
            t_pre = (time.perf_counter() - t0) * 1000
            
            # Run ONNX
            t_onnx_0 = time.perf_counter()
            outputs = self._ort_session.run(None, {self._input_name: inp_numpy})
            t_onnx_1 = (time.perf_counter() - t_onnx_0) * 1000
            
            simcc_x, simcc_y = outputs[0], outputs[1]
            simcc_z = outputs[2] if len(outputs) > 2 else None

            # Decode SimCC
            loc_x = np.argmax(simcc_x[0], axis=1)
            loc_y = np.argmax(simcc_y[0], axis=1)
            if simcc_z is not None:
                loc_z = np.argmax(simcc_z[0], axis=1)
            else:
                loc_z = np.zeros_like(loc_x)
            
            kpts_x = loc_x / 2.0
            kpts_y = loc_y / 2.0
            kpts_z = loc_z / 2.0
            
            # Map back
            scale_x = (x2 - x1) / float(input_w)
            scale_y = (y2 - y1) / float(input_h)
            
            orig_x = kpts_x * scale_x + x1
            orig_y = kpts_y * scale_y + y1

            # RTMW3D z decoding: map SimCC z-bin to relative depth and scale
            # by bbox size so x/y/z are in comparable visualization units.
            z_rel = (kpts_z / (input_w / 2.0) - 1.0) * 2.1744869
            z_scale = max(1.0, 0.5 * max(float(x2 - x1), float(y2 - y1)))
            z_pix = z_rel.astype(np.float32) * float(z_scale)
            
            scores_x = np.max(simcc_x[0], axis=1)
            scores_y = np.max(simcc_y[0], axis=1)
            if simcc_z is not None:
                scores_z = np.max(simcc_z[0], axis=1)
                kpt_scores = np.minimum(np.minimum(scores_x, scores_y), scores_z)
            else:
                kpt_scores = np.minimum(scores_x, scores_y)
            
            kpts_2d = np.stack([orig_x, orig_y], axis=1)
            kpts_3d = np.stack([orig_x, orig_y, z_pix], axis=1)
            
            # Detailed debug for bottleneck analysis
            # print(f"DEBUG | Det: {det_ms:.1f}ms | Pre: {t_pre:.1f}ms | ONNX: {t_onnx_1:.1f}ms")
            
            return self._pack_results(kpts_3d, kpts_2d, kpt_scores, frame.shape)
            
        except Exception as e:
            logger.error(f"ONNX Inference Error: {e}")
            traceback.print_exc()
            return None


    def _pack_results(self, kpts_3d, kpts_2d, scores, img_shape):
        h_img, w_img = img_shape[:2]
        num_kpts = kpts_3d.shape[0]
        joint_names = _load_coco_wholebody_names()
        if len(joint_names) < num_kpts:
            joint_names = list(joint_names) + [f"kpt_{i}" for i in range(len(joint_names), num_kpts)]

        joints: List[PoseJoint] = []
        for index in range(num_kpts):
            name = joint_names[index] if index < len(joint_names) else f"kpt_{index}"
            
            x3d, y3d, z3d = kpts_3d[index]
            px, py = kpts_2d[index]
            c = float(scores[index]) if scores is not None else 0.0
            
            joints.append({
                "name": str(name), 
                "x": float(x3d),
                "y": float(y3d),
                "z": float(z3d),
                "c": c,
                "px": float(px / w_img),
                "py": float(py / h_img)
            })

        return {
            "t": 0.0, 
            "space": "camera",
            "joints": joints,
        }
