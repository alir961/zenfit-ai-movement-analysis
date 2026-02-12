from __future__ import annotations

import os


ARTIFACTS_DIR_DEFAULT = os.path.join("workspace", "backend", "models", "onnx")


def build_manifest(project_root: str) -> dict:
    # Official ONNX links are used when clearly available; otherwise local/export paths are used.
    return {
        "pose": {
            "rtmw3d_l": {
                "fp32": {
                    "filename": "rtmw3d_l_fp32.onnx",
                    "local_source": os.path.join(project_root, "rtmw3d_l.onnx"),
                    "download_url": None,
                },
                "fp16": {
                    "filename": "rtmw3d_l_fp16.onnx",
                    "local_source": os.path.join(project_root, "rtmw3d_l_fp16.onnx"),
                    "download_url": None,
                },
                "int8": {
                    "filename": "rtmw3d_l_int8.onnx",
                    "local_source": os.path.join(project_root, "rtmw3d_l_int8.onnx"),
                    "download_url": None,
                    "derived_from": "fp32",
                },
            }
        },
        "detector": {
            "yolox_tiny_humanart": {
                "fp32": {
                    "filename": "yolox_tiny_humanart_fp32.onnx",
                    "local_source": os.path.join(project_root, "workspace", "backend", "models", "onnx", "yolox_tiny_humanart_fp32.onnx"),
                    "download_url": None,
                    "export": {
                        "kind": "yolox",
                        "config": os.path.join(
                            project_root,
                            "third_party",
                            "mmpose",
                            "projects",
                            "rtmpose",
                            "yolox",
                            "humanart",
                            "yolox_tiny_8xb8-300e_humanart.py",
                        ),
                        "checkpoint": os.path.join(
                            project_root,
                            "workspace",
                            "backend",
                            "models",
                            "onnx",
                            "yolox_tiny_8xb8-300e_humanart-6f3252f9.pth",
                        ),
                        "input_size": [416, 416],
                    },
                },
                "fp16": {"filename": "yolox_tiny_humanart_fp16.onnx", "derived_from": "fp32"},
                "int8": {"filename": "yolox_tiny_humanart_int8.onnx", "derived_from": "fp32"},
            },
            "yolox_s_humanart": {
                "fp32": {
                    "filename": "yolox_s_humanart_fp32.onnx",
                    "local_source": os.path.join(project_root, "workspace", "backend", "models", "onnx", "yolox_s_humanart_fp32.onnx"),
                    "download_url": None,
                    "export": {
                        "kind": "yolox",
                        "config": os.path.join(
                            project_root,
                            "third_party",
                            "mmpose",
                            "projects",
                            "rtmpose",
                            "yolox",
                            "humanart",
                            "yolox_s_8xb8-300e_humanart.py",
                        ),
                        "checkpoint": os.path.join(
                            project_root,
                            "workspace",
                            "backend",
                            "models",
                            "onnx",
                            "yolox_s_8xb8-300e_humanart-3ef259a7.pth",
                        ),
                        "input_size": [640, 640],
                    },
                },
                "fp16": {"filename": "yolox_s_humanart_fp16.onnx", "derived_from": "fp32"},
                "int8": {"filename": "yolox_s_humanart_int8.onnx", "derived_from": "fp32"},
            },
            "rtmdet_nano": {
                "fp32": {
                    "filename": "rtmdet_nano_fp32.onnx",
                    "local_source": os.path.join(project_root, "workspace", "backend", "models", "onnx", "rtmdet_nano_fp32.onnx"),
                    "download_url": None,
                    "export": {
                        "config": os.path.join(
                            project_root,
                            "third_party",
                            "mmpose",
                            "projects",
                            "rtmpose",
                            "rtmdet",
                            "person",
                            "rtmdet_nano_320-8xb32_coco-person.py",
                        ),
                        "checkpoint": "https://download.openmmlab.com/mmpose/v1/projects/rtmpose/rtmdet_nano_8xb32-100e_coco-obj365-person-05d8511e.pth",
                    },
                },
                "fp16": {"filename": "rtmdet_nano_fp16.onnx", "derived_from": "fp32"},
                "int8": {"filename": "rtmdet_nano_int8.onnx", "derived_from": "fp32"},
            },
            "rtmdet_tiny": {
                "fp32": {
                    "filename": "rtmdet_tiny_fp32.onnx",
                    "local_source": os.path.join(project_root, "workspace", "backend", "models", "onnx", "rtmdet_tiny_fp32.onnx"),
                    "download_url": None,
                    "export": {
                        "kind": "rtmdet",
                        "config": os.path.join(
                            project_root,
                            "third_party",
                            "mmpose",
                            "demo",
                            "mmdetection_cfg",
                            "rtmdet_tiny_8xb32-300e_coco.py",
                        ),
                        "checkpoint": os.path.join(
                            project_root,
                            "workspace",
                            "backend",
                            "models",
                            "onnx",
                            "rtmdet_tiny_8xb32-300e_humanart-7da5554e.pth",
                        ),
                    },
                },
                "fp16": {"filename": "rtmdet_tiny_fp16.onnx", "derived_from": "fp32"},
                "int8": {"filename": "rtmdet_tiny_int8.onnx", "derived_from": "fp32"},
            },
            "person_foot_qualcomm": {
                "int8": {
                    "filename": "person_foot_detection.onnx",
                    "local_source": os.path.join(
                        project_root,
                        "workspace",
                        "backend",
                        "models",
                        "onnx",
                        "person_foot_detection.onnx",
                    ),
                    "download_url": None,
                }
            },
        },
    }
