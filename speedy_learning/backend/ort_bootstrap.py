from __future__ import annotations

import os
import site
from pathlib import Path
from typing import Dict, List


def _collect_dll_dirs() -> List[Path]:
    roots: List[Path] = []
    dirs: List[Path] = []

    for p in site.getsitepackages():
        roots.append(Path(p))
    user_site = site.getusersitepackages()
    if user_site:
        roots.append(Path(user_site))

    seen = set()
    for root in roots:
        if not root.exists():
            continue
        for cand in (root / "nvidia").glob("*/bin"):
            if cand.is_dir() and str(cand) not in seen:
                seen.add(str(cand))
                dirs.append(cand)
        for extra in (root / "torch" / "lib", root / "onnxruntime" / "capi"):
            if extra.is_dir() and str(extra) not in seen:
                seen.add(str(extra))
                dirs.append(extra)
    return dirs


def bootstrap_onnxruntime() -> Dict[str, object]:
    result: Dict[str, object] = {
        "ok": False,
        "providers": [],
        "dll_dirs": [],
        "warnings": [],
    }

    try:
        import onnxruntime as ort
    except Exception as exc:
        result["warnings"].append(f"onnxruntime import failed: {exc}")
        return result

    # Register DLL dirs on Windows for this process.
    if os.name == "nt":
        for d in _collect_dll_dirs():
            try:
                os.add_dll_directory(str(d))
                result["dll_dirs"].append(str(d))
            except Exception as exc:
                result["warnings"].append(f"add_dll_directory failed {d}: {exc}")

    # Official ORT recommendation for Python package based CUDA/cuDNN loading.
    try:
        ort.preload_dlls(directory="")
    except Exception as exc:
        result["warnings"].append(f"preload_dlls(directory='') failed: {exc}")
        try:
            ort.preload_dlls()
        except Exception as exc2:
            result["warnings"].append(f"preload_dlls() failed: {exc2}")

    try:
        result["providers"] = ort.get_available_providers()
        result["ok"] = True
    except Exception as exc:
        result["warnings"].append(f"get_available_providers failed: {exc}")

    return result

