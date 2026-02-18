from __future__ import annotations

import cv2
import numpy as np

from speedy_learning.backend.inference_rtmw3d import RTMW3DEstimator, _safe_bbox


def main() -> None:
    est = RTMW3DEstimator()
    print("model:", est.model_path)
    print("providers:", est.providers)
    print("warnings:", est.warnings)
    if est.session is None:
        return

    print("inputs:", [(i.name, i.shape, i.type) for i in est.session.get_inputs()])
    print("outputs:", [(o.name, o.shape, o.type) for o in est.session.get_outputs()])

    cap = cv2.VideoCapture("datasets/squat_1.mp4")
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError("failed to read frame")
    bbox = _safe_bbox([86, 56, 279, 639], frame.shape[1], frame.shape[0])
    x, _ = est._preprocess_crop(frame, bbox)
    outs = est.session.run(None, {est.input_name: x})
    print("nouts:", len(outs))
    for i, out in enumerate(outs):
        arr = np.asarray(out)
        print(i, arr.shape, arr.dtype, float(arr.min()), float(arr.max()))


if __name__ == "__main__":
    main()
