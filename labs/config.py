from __future__ import annotations

from typing import Dict, List, Tuple

from .types import LabsConfig, PresetConfig
from .rig_profile import get_rig_profile


DEFAULT_SKELETON_LINKS: List[Tuple[str, str]] = list(get_rig_profile("body17").skeleton_links)


PRESETS: Dict[str, PresetConfig] = {
    "yolox_s_fp32_fp32_cuda_skip3": PresetConfig(
        name="yolox_s_fp32_fp32_cuda_skip3",
        backend="onnx",
        detector_backend="onnx",
        detector_model="yolox_s_humanart",
        detector_variant="fp32",
        pose_variant="fp32",
        providers_order=["CUDAExecutionProvider", "CPUExecutionProvider"],
        track_interval=0,
        skip_fixed=3,
    ),
    "rtmdet_m_fp32_fp32_cuda_skip3": PresetConfig(
        name="rtmdet_m_fp32_fp32_cuda_skip3",
        backend="onnx",
        detector_backend="auto",
        detector_model="rtmdet_m",
        detector_variant="fp32",
        pose_variant="fp32",
        providers_order=["CUDAExecutionProvider", "CPUExecutionProvider"],
        track_interval=0,
        skip_fixed=3,
    )
}


def get_preset(name: str) -> PresetConfig:
    if name in PRESETS:
        return PRESETS[name]
    return PRESETS["yolox_s_fp32_fp32_cuda_skip3"]


def make_labs_config(
    video_path: str,
    preset_name: str,
    skip_mode: str,
    skip_fixed: int,
    pyplot: bool,
    ipc: str,
    scale_mode: str,
    calib_file: str | None,
    benchmark_labs: bool,
    max_frames: int | None,
    show_ui: bool,
    rig_profile: str = "coco133",
    plot_space: str = "canonical",
    draw_min_conf: float = 0.05,
    stale_policy: str = "graceful",
    max_stale_frames: int = 45,
    canonical_lock: bool = True,
    camera_links: str = "body17",
    noncore_mode: str = "hold",
    pyplot_rig: str = "body17",
    show_noncore_points: bool = True,
) -> LabsConfig:
    preset = get_preset(preset_name)
    rig = rig_profile if rig_profile in ("body17", "coco133") else "coco133"
    pspace = plot_space if plot_space in ("raw", "canonical", "both") else "canonical"
    stale = stale_policy if stale_policy in ("strict", "graceful") else "graceful"
    cam_links = camera_links if camera_links in ("body17", "coco133") else "body17"
    noncore = noncore_mode if noncore_mode in ("hold", "predict", "drop") else "hold"
    py_rig = pyplot_rig if pyplot_rig in ("body17", "coco133") else "body17"
    return LabsConfig(
        video_path=video_path,
        preset=preset,
        skip_mode=skip_mode if skip_mode in ("fixed", "adaptive") else "fixed",
        skip_fixed=max(0, int(skip_fixed)),
        pyplot=bool(pyplot),
        ipc="shm_queue",
        scale_mode=scale_mode if scale_mode in ("calibrated", "uncalibrated") else "uncalibrated",
        calib_file=calib_file,
        benchmark_labs=bool(benchmark_labs),
        max_frames=max_frames,
        show_ui=bool(show_ui),
        rig_profile=rig,
        plot_space=pspace,
        draw_min_conf=max(0.0, min(1.0, float(draw_min_conf))),
        stale_policy=stale,
        max_stale_frames=max(0, int(max_stale_frames)),
        canonical_lock=bool(canonical_lock),
        camera_links=cam_links,
        noncore_mode=noncore,
        pyplot_rig=py_rig,
        show_noncore_points=bool(show_noncore_points),
    )
