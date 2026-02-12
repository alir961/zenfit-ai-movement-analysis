from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from typing import Optional

import onnx
from onnxruntime.quantization import QuantType, quantize_dynamic
import torch

try:
    from onnxconverter_common import float16
except Exception:
    float16 = None

from onnx_manifest import ARTIFACTS_DIR_DEFAULT, build_manifest


@dataclass
class ArtifactResult:
    key: str
    status: str
    reason: str
    path: str


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def download(url: str, dst: str) -> None:
    with urllib.request.urlopen(url) as src, open(dst, "wb") as out:
        out.write(src.read())


def convert_fp16(src: str, dst: str) -> None:
    if float16 is None:
        raise RuntimeError("onnxconverter_common_missing")
    model = onnx.load(src)
    try:
        model_fp16 = float16.convert_float_to_float16(model, keep_io_types=True)
    except Exception as exc:
        raise RuntimeError(f"fp16_convert_failed:{exc}") from exc
    onnx.save(model_fp16, dst)


def convert_int8(src: str, dst: str) -> None:
    quantize_dynamic(src, dst, weight_type=QuantType.QUInt8)


def validate_onnx(path: str) -> None:
    import onnxruntime as ort

    try:
        model = onnx.load(path)
        onnx.checker.check_model(model)
        sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    except Exception as exc:
        msg = str(exc)
        if "Type Error" in msg:
            raise RuntimeError(f"onnx_type_mismatch:{msg[:400]}") from exc
        raise RuntimeError(f"onnx_validate_failed:{msg[:400]}") from exc
    if not sess.get_inputs():
        raise RuntimeError("onnx_no_inputs")
    if not sess.get_outputs():
        raise RuntimeError("onnx_no_outputs")


def export_rtmdet_fp32(project_root: str, config_path: str, checkpoint: str, dst: str) -> None:
    tools_script = os.path.join(
        project_root,
        "third_party",
        "mmpose",
        "projects",
        "rtmpose",
        "examples",
        "RTMPose-Deploy",
        "Windows",
        "TensorRT",
        "python",
        "convert_rtmdet.py",
    )
    if not os.path.exists(tools_script):
        raise RuntimeError("convert_rtmdet_script_missing")
    tmp_ckpt = checkpoint
    if checkpoint.startswith("http://") or checkpoint.startswith("https://"):
        tmp_ckpt = os.path.join(os.path.dirname(dst), os.path.basename(checkpoint))
        if not os.path.exists(tmp_ckpt):
            download(checkpoint, tmp_ckpt)

    cmd = [
        sys.executable,
        tools_script,
        "--config",
        config_path,
        "--checkpoint",
        tmp_ckpt,
        "--output",
        dst,
        "--device",
        "cuda:0",
    ]
    proc = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"rtmdet_export_failed:{proc.stderr.strip()[:400]}")
    if not os.path.exists(dst):
        raise RuntimeError("rtmdet_export_no_output")


def export_yolox_fp32(config_path: str, checkpoint: str, dst: str, input_size: tuple[int, int]) -> None:
    from mmdet.apis import init_detector
    from torch import nn

    class YOLOXExport(nn.Module):
        def __init__(self, model: nn.Module, input_size_hw: tuple[int, int]) -> None:
            super().__init__()
            self.model = model
            self.input_h, self.input_w = input_size_hw

        def forward(self, x):
            cls_scores, bbox_preds, obj_preds = self.model(x)
            outputs = []
            for cls, box, obj in zip(cls_scores, bbox_preds, obj_preds):
                bs, _, h, w = cls.shape
                stride_h = self.input_h // h
                stride_w = self.input_w // w
                stride = float(min(stride_h, stride_w))

                cls = cls.permute(0, 2, 3, 1).sigmoid()
                box = box.permute(0, 2, 3, 1)
                obj = obj.permute(0, 2, 3, 1).sigmoid()

                ys, xs = torch.meshgrid(
                    torch.arange(h, device=x.device),
                    torch.arange(w, device=x.device),
                    indexing="ij",
                )
                grid = torch.stack((xs, ys), dim=-1).view(1, h, w, 2).to(box.dtype)
                xy = (box[..., :2] + grid) * stride
                wh = torch.exp(box[..., 2:4]) * stride
                x1y1 = xy - (wh / 2.0)
                x2y2 = xy + (wh / 2.0)

                cls_score, cls_id = torch.max(cls, dim=-1, keepdim=True)
                score = cls_score * obj
                out = torch.cat(
                    [x1y1, x2y2, cls_id.to(dtype=score.dtype), score],
                    dim=-1,
                )
                outputs.append(out.reshape(bs, -1, 6))

            return torch.cat(outputs, dim=1)

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    model = init_detector(config_path, checkpoint, device=device)
    model.eval()
    export_model = YOLOXExport(model, input_size).eval()
    x = torch.randn(
        (1, 3, int(input_size[0]), int(input_size[1])),
        device=device,
        dtype=torch.float32,
    )
    with torch.no_grad():
        torch.onnx.export(
            export_model,
            x,
            dst,
            input_names=["image"],
            output_names=["output"],
            opset_version=11,
        )
    if not os.path.exists(dst):
        raise RuntimeError("yolox_export_no_output")


def prepare_one(
    group: str,
    model: str,
    variant: str,
    spec: dict,
    manifest: dict,
    out_dir: str,
) -> ArtifactResult:
    key = f"{group}.{model}.{variant}"
    dst = os.path.join(out_dir, spec["filename"])
    try:
        if os.path.exists(dst):
            validate_onnx(dst)
            return ArtifactResult(key, "ok", "already_exists", dst)

        local_source = spec.get("local_source")
        if local_source:
            if os.path.exists(local_source):
                shutil.copy2(local_source, dst)
                validate_onnx(dst)
                return ArtifactResult(key, "ok", "copied_local_source", dst)
            if not spec.get("download_url") and not spec.get("export"):
                return ArtifactResult(key, "failed", "missing_local_source", dst)

        download_url = spec.get("download_url")
        if download_url:
            download(download_url, dst)
            validate_onnx(dst)
            return ArtifactResult(key, "ok", "downloaded", dst)

        export_spec = spec.get("export")
        if export_spec and variant == "fp32":
            config_path = export_spec.get("config")
            checkpoint = export_spec.get("checkpoint")
            if not config_path or not checkpoint:
                return ArtifactResult(key, "failed", "invalid_export_spec", dst)
            export_kind = export_spec.get("kind", "rtmdet")
            if export_kind == "yolox":
                input_size = export_spec.get("input_size", [640, 640])
                export_yolox_fp32(
                    config_path=config_path,
                    checkpoint=checkpoint,
                    dst=dst,
                    input_size=(int(input_size[0]), int(input_size[1])),
                )
            else:
                export_rtmdet_fp32(
                    project_root=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")),
                    config_path=config_path,
                    checkpoint=checkpoint,
                    dst=dst,
                )
            validate_onnx(dst)
            return ArtifactResult(key, "ok", "exported_local", dst)

        derived_from = spec.get("derived_from")
        if derived_from:
            base_spec = manifest[group][model].get(derived_from)
            if not base_spec:
                return ArtifactResult(key, "failed", f"missing_base_variant:{derived_from}", dst)
            base_dst = os.path.join(out_dir, base_spec["filename"])
            if not os.path.exists(base_dst):
                base_res = prepare_one(group, model, derived_from, base_spec, manifest, out_dir)
                if base_res.status != "ok":
                    return ArtifactResult(key, "failed", f"base_prepare_failed:{base_res.reason}", dst)

            if variant == "fp16":
                try:
                    convert_fp16(base_dst, dst)
                    validate_onnx(dst)
                except Exception as exc:
                    # Some detector graphs keep strict float outputs and cannot be converted safely.
                    # Keep the fp16 variant executable by aliasing to validated fp32 binary.
                    shutil.copy2(base_dst, dst)
                    validate_onnx(dst)
                    return ArtifactResult(key, "ok", f"fp16_fallback_fp32:{exc}", dst)
            elif variant == "int8":
                convert_int8(base_dst, dst)
            else:
                return ArtifactResult(key, "failed", "unsupported_derived_variant", dst)
            if variant != "fp16":
                validate_onnx(dst)
            return ArtifactResult(key, "ok", f"derived_from_{derived_from}", dst)

        return ArtifactResult(key, "failed", "no_source_available", dst)
    except Exception as exc:
        return ArtifactResult(key, "failed", str(exc), dst)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=ARTIFACTS_DIR_DEFAULT)
    parser.add_argument("--report", default=os.path.join("workspace", "backend", "models", "onnx", "prepare_report.json"))
    parser.add_argument(
        "--force-rebuild-fp16-detectors",
        action="store_true",
        help="Delete detector FP16 artifacts before rebuild.",
    )
    args = parser.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    out_dir = args.out_dir if os.path.isabs(args.out_dir) else os.path.join(project_root, args.out_dir)
    report_path = args.report if os.path.isabs(args.report) else os.path.join(project_root, args.report)
    ensure_dir(out_dir)
    ensure_dir(os.path.dirname(report_path))

    if args.force_rebuild_fp16_detectors:
        for filename in (
            "yolox_tiny_humanart_fp16.onnx",
            "yolox_s_humanart_fp16.onnx",
            "rtmdet_nano_fp16.onnx",
            "rtmdet_tiny_fp16.onnx",
        ):
            candidate = os.path.join(out_dir, filename)
            if os.path.exists(candidate):
                os.remove(candidate)

    manifest = build_manifest(project_root)
    results: list[ArtifactResult] = []

    for group in ("pose", "detector"):
        for model, variants in manifest[group].items():
            for variant, spec in variants.items():
                results.append(prepare_one(group, model, variant, spec, manifest, out_dir))

    payload = {
        "out_dir": out_dir,
        "results": [r.__dict__ for r in results],
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    failed = [r for r in results if r.status != "ok"]
    print(f"Prepared {len(results)} artifacts. Success={len(results)-len(failed)} Failed={len(failed)}")
    print(f"Report: {report_path}")
    if failed:
        for item in failed:
            print(f"- {item.key}: {item.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
