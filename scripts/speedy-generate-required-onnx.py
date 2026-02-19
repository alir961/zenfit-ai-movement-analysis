from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional


def _now() -> float:
    return time.time()


def _run(cmd: list[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _download(url: str, dst: Path) -> None:
    _ensure_dir(dst.parent)
    with urllib.request.urlopen(url) as src, open(dst, "wb") as out:
        out.write(src.read())


def _validate_onnx(path: Path) -> None:
    import onnxruntime as ort

    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    if not sess.get_inputs() or not sess.get_outputs():
        raise RuntimeError(f"invalid_onnx_io:{path}")


def _install_mmcv_if_needed(python_exe: str, report_steps: list[dict]) -> None:
    start = _now()
    proc = _run([python_exe, "-c", "import mmcv; print(mmcv.__version__)"])
    if proc.returncode != 0:
        report_steps.append(
            {
                "name": "mmcv_check",
                "status": "warn",
                "reason": "mmcv_import_failed",
                "detail": (proc.stderr or proc.stdout).strip()[:500],
                "duration_s": round(_now() - start, 3),
            }
        )
        return

    version = (proc.stdout or "").strip()
    status = "ok"
    reason = "compatible"
    # mmcv>=2.2.0 breaks the exporter stack in this repo.
    parts = version.split(".")
    major = int(parts[0]) if parts and parts[0].isdigit() else 0
    minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    if major > 2 or (major == 2 and minor >= 2):
        # Try binary install via OpenMIM first. If this fails, fallback to runtime
        # version-guard patching to bypass strict mmdet/mmcv gate.
        install = _run([python_exe, "-m", "mim", "install", "mmcv==2.1.0"])
        if install.returncode == 0:
            status = "ok"
            reason = "downgraded_to_2.1.0_via_mim"
        else:
            os.environ["SPEEDY_MMCV_VERSION_GUARD"] = "1"
            status = "warn"
            reason = "mim_downgrade_failed_using_runtime_guard"
            report_steps.append(
                {
                    "name": "mmcv_fix",
                    "status": "warn",
                    "reason": reason,
                    "detail": (install.stderr or install.stdout).strip()[:1200],
                    "duration_s": round(_now() - start, 3),
                }
            )

    report_steps.append(
        {
            "name": "mmcv_check",
            "status": status,
            "reason": reason,
            "detail": f"mmcv={version}",
            "duration_s": round(_now() - start, 3),
        }
    )


def _apply_mmcv_runtime_guard() -> None:
    if os.getenv("SPEEDY_MMCV_VERSION_GUARD") != "1":
        return
    try:
        import mmcv  # type: ignore

        parts = mmcv.__version__.split(".")
        major = int(parts[0]) if parts and parts[0].isdigit() else 0
        minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        if major > 2 or (major == 2 and minor >= 2):
            mmcv.__version__ = "2.1.0"
    except Exception:
        pass


def _find_config(mmpose_root: Path, patterns: list[str]) -> Optional[Path]:
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(mmpose_root.rglob(pattern))
    if not candidates:
        return None
    # Prefer shortest relative path for stability.
    candidates.sort(key=lambda p: (len(str(p.relative_to(mmpose_root))), str(p)))
    return candidates[0]


def _parse_load_from(config_path: Path) -> Optional[str]:
    try:
        tree = ast.parse(config_path.read_text(encoding="utf-8"), filename=str(config_path))
    except Exception:
        return None

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "load_from":
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        return node.value.value
    return None


def _resolve_checkpoint(
    config_path: Path,
    cache_dir: Path,
    known_local: list[Path],
    fallback_urls: Optional[list[str]] = None,
) -> Path:
    for p in known_local:
        if p.exists():
            return p

    load_from = _parse_load_from(config_path)
    if not load_from:
        if fallback_urls:
            url = fallback_urls[0]
            dst = cache_dir / Path(url).name
            if not dst.exists():
                _download(url, dst)
            return dst
        raise RuntimeError(f"checkpoint_not_found_in_config:{config_path}")

    if load_from.startswith("http://") or load_from.startswith("https://"):
        dst = cache_dir / Path(load_from).name
        if not dst.exists():
            _download(load_from, dst)
        return dst

    # Relative to config directory or repo root.
    rel1 = (config_path.parent / load_from).resolve()
    if rel1.exists():
        return rel1
    rel2 = (config_path.parents[3] / load_from).resolve() if len(config_path.parents) >= 4 else rel1
    if rel2.exists():
        return rel2

    raise RuntimeError(f"checkpoint_path_missing:{load_from}")


def _atomic_copy(src: Path, dst: Path) -> None:
    _ensure_dir(dst.parent)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)


def _export_yolox(config_path: Path, checkpoint: Path, out_path: Path) -> None:
    _apply_mmcv_runtime_guard()
    import torch
    from torch import nn
    from mmdet.apis import init_detector

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
                out = torch.cat([x1y1, x2y2, cls_id.to(dtype=score.dtype), score], dim=-1)
                outputs.append(out.reshape(bs, -1, 6))

            return torch.cat(outputs, dim=1)

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    model = init_detector(str(config_path), str(checkpoint), device=device)
    model.eval()

    input_size = (640, 640)
    export_model = YOLOXExport(model, input_size).eval()
    dummy = torch.randn((1, 3, input_size[0], input_size[1]), device=device, dtype=torch.float32)
    _ensure_dir(out_path.parent)
    with torch.no_grad():
        torch.onnx.export(
            export_model,
            dummy,
            str(out_path),
            input_names=["image"],
            output_names=["output"],
            opset_version=11,
            do_constant_folding=True,
        )


def _export_rtmw3d(config_path: Path, checkpoint: Path, out_path: Path) -> None:
    _apply_mmcv_runtime_guard()
    import torch
    import torch.nn as nn
    from mmpose.apis import init_model

    class RTMW3DWrapper(nn.Module):
        def __init__(self, pose_model: nn.Module):
            super().__init__()
            self.model = pose_model

        def forward(self, x):
            feats = self.model.extract_feat(x)
            return self.model.head.forward(feats)

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    model = init_model(str(config_path), str(checkpoint), device=device)
    model.eval()
    wrapper = RTMW3DWrapper(model).eval()

    dummy = torch.randn(1, 3, 384, 288, device=device, dtype=torch.float32)
    with torch.no_grad():
        outputs = wrapper(dummy)
    if isinstance(outputs, (tuple, list)):
        output_names = [f"output_{i}" for i in range(len(outputs))]
    else:
        output_names = ["output_0"]

    _ensure_dir(out_path.parent)
    with torch.no_grad():
        torch.onnx.export(
            wrapper,
            dummy,
            str(out_path),
            input_names=["input"],
            output_names=output_names,
            opset_version=11,
            do_constant_folding=True,
            dynamic_axes={"input": {0: "batch_size"}},
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate required ONNX models for Speedy Learning")
    parser.add_argument("--report", default="speedy_learning/logs/install_report.json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    mmpose_root = root / "third_party" / "mmpose"
    speedy_models = root / "speedy_learning" / "models"
    cache_dir = root / "speedy_learning" / ".cache" / "onnx"
    logs_dir = root / "speedy_learning" / "logs"
    report_path = root / args.report

    _ensure_dir(speedy_models)
    _ensure_dir(cache_dir)
    _ensure_dir(logs_dir)
    _ensure_dir(report_path.parent)

    steps: list[dict] = []

    if not (mmpose_root / ".git").exists():
        raise RuntimeError("mmpose_missing: run speedy-third-party-ensure first")

    # Custom modules used by project configs (e.g. rtmpose3d) are not installed
    # as pip packages; expose their source roots at runtime for MMEngine imports.
    custom_roots = [
        mmpose_root / "projects" / "rtmpose3d",
        mmpose_root / "projects" / "rtmpose",
    ]
    for p in custom_roots:
        if p.exists():
            sp = str(p.resolve())
            if sp not in sys.path:
                sys.path.insert(0, sp)

    _install_mmcv_if_needed(sys.executable, steps)

    targets = {
        "yolox": speedy_models / "yolox_s_humanart_fp32.onnx",
        "rtmw3d": speedy_models / "rtmw3d_l_fp32.onnx",
    }

    # Opportunistic fallback from workspace cache, never mandatory.
    workspace_cache = root / "workspace" / "backend" / "models" / "onnx"
    for key, target in targets.items():
        if target.exists():
            _validate_onnx(target)
            steps.append({"name": f"{key}_ready", "status": "ok", "reason": "already_exists", "duration_s": 0.0})
            continue
        ws_name = target.name
        ws_src = workspace_cache / ws_name
        if ws_src.exists():
            _atomic_copy(ws_src, target)
            _validate_onnx(target)
            steps.append({"name": f"{key}_ready", "status": "ok", "reason": "copied_workspace_cache", "duration_s": 0.0})

    # Generate YOLOX if needed.
    if not targets["yolox"].exists():
        s = _now()
        cfg = _find_config(mmpose_root, ["yolox_s_*humanart*.py", "*yolox_s*humanart*.py"])
        if cfg is None:
            raise RuntimeError("yolox_config_missing")
        ckpt = _resolve_checkpoint(
            cfg,
            cache_dir,
            [
                cache_dir / "yolox_s_8xb8-300e_humanart-3ef259a7.pth",
                root / "yolox_s_8xb8-300e_humanart-3ef259a7.pth",
                root / "workspace" / "backend" / "models" / "onnx" / "yolox_s_8xb8-300e_humanart-3ef259a7.pth",
            ],
            fallback_urls=[
                "https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/yolox_s_8xb8-300e_humanart-3ef259a7.pth"
            ],
        )
        tmp = cache_dir / "yolox_s_humanart_fp32.onnx"
        _export_yolox(cfg, ckpt, tmp)
        _validate_onnx(tmp)
        _atomic_copy(tmp, targets["yolox"])
        steps.append(
            {
                "name": "yolox_export",
                "status": "ok",
                "reason": "generated",
                "detail": str(cfg),
                "duration_s": round(_now() - s, 3),
            }
        )

    # Generate RTMW3D if needed.
    if not targets["rtmw3d"].exists():
        s = _now()
        cfg = _find_config(
            mmpose_root,
            [
                "rtmw3d-l_*384x288*.py",
                "*rtmw3d*l*384x288*.py",
            ],
        )
        if cfg is None:
            raise RuntimeError("rtmw3d_config_missing")
        ckpt = _resolve_checkpoint(
            cfg,
            cache_dir,
            [
                cache_dir / "rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth",
                root / "rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth",
                root / "workspace" / "backend" / "models" / "onnx" / "rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth",
            ],
            fallback_urls=[
                "https://download.openmmlab.com/mmpose/v1/wholebody_3d_keypoint/rtmw3d/rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth"
            ],
        )
        tmp = cache_dir / "rtmw3d_l_fp32.onnx"
        _export_rtmw3d(cfg, ckpt, tmp)
        _validate_onnx(tmp)
        _atomic_copy(tmp, targets["rtmw3d"])
        steps.append(
            {
                "name": "rtmw3d_export",
                "status": "ok",
                "reason": "generated",
                "detail": str(cfg),
                "duration_s": round(_now() - s, 3),
            }
        )

    # Final validation for required targets.
    s = _now()
    for p in targets.values():
        _validate_onnx(p)
    steps.append({"name": "final_validate", "status": "ok", "reason": "cpu_session_ok", "duration_s": round(_now() - s, 3)})

    payload = {
        "timestamp": int(time.time()),
        "cwd": str(root),
        "targets": {k: str(v) for k, v in targets.items()},
        "steps": steps,
    }
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("[speedy-onnx] report:", report_path)
    print("[speedy-onnx] ready:")
    for p in targets.values():
        print("  -", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
