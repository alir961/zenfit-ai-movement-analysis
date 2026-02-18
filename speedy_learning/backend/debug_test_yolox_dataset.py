from __future__ import annotations

import random
from pathlib import Path

import cv2

from speedy_learning.backend.inference_yolox import YOLOXDetector


def main() -> None:
    dataset_dir = Path("datasets")
    videos = sorted(dataset_dir.glob("*.mp4"))
    if not videos:
        raise RuntimeError("No .mp4 files found in datasets/")

    video_path = random.choice(videos)
    cap = cv2.VideoCapture(str(video_path))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    target = random.randint(0, max(frame_count - 1, 0))
    cap.set(cv2.CAP_PROP_POS_FRAMES, target)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"Cannot read frame {target} from {video_path}")

    detector = YOLOXDetector()
    result = detector.detect(frame)

    out = frame.copy()
    x1, y1, x2, y2 = [int(v) for v in result["bbox_xyxy"]]
    color = (0, 255, 0) if result.get("source") == "onnx" else (0, 165, 255)
    cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
    cv2.putText(
        out,
        f"src={result.get('source')} score={result.get('score', 0.0):.3f}",
        (12, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    out_dir = Path("speedy_learning/logs/debug_frames")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "yolox_dataset_test.jpg"
    cv2.imwrite(str(out_path), out)

    print("video:", video_path)
    print("frame:", target)
    print("model:", detector.model_path)
    print("providers:", detector.providers)
    print("result:", result)
    print("saved:", out_path)


if __name__ == "__main__":
    main()
