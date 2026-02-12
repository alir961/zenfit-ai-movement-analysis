
import sys
import os
import numpy as np
import torch
import cv2

# 1. Setup paths for custom modules
PROJ_ROOT = r"d:\epitech\zenfit"
PROJECT_PATH = os.path.join(PROJ_ROOT, "third_party", "mmpose", "projects", "rtmpose3d")
if PROJECT_PATH not in sys.path:
    sys.path.append(PROJECT_PATH)

try:
    # 2. Import custom modules to register them
    import rtmpose3d
    print("✅ Custom rtmpose3d modules registered.")

    from mmpose.apis import MMPoseInferencer

    POSE_CONFIG = os.path.join(PROJECT_PATH, "configs", "rtmw3d-l_8xb64_cocktail14-384x288.py")
    POSE_CHECKPOINT = os.path.join(PROJ_ROOT, "rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth")

    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {DEVICE}")

    print("Initializing MMPoseInferencer with custom config...")
    # Passing pose3d as a path to the config file
    inf = MMPoseInferencer(
        pose3d=POSE_CONFIG,
        pose3d_weights=POSE_CHECKPOINT,
        device=DEVICE
    )
    print("✅ Inferencer ready.")

    # 3. Run a dummy inference 
    img = np.zeros((384, 384, 3), dtype=np.uint8) 
    
    print("Running inference...")
    result_generator = inf(img, return_vis=False)
    result = next(result_generator)
    
    if result:
        pred = result['predictions'][0]
        kpts = pred.get('keypoints')
        kpts3d = pred.get('keypoints_3d')
        print(f"✅ Success! Detected {len(kpts3d) if kpts3d is not None else 0} 3D keypoints.")
        if kpts3d is not None:
             print(f"Sample 3D keypoint [0]: {kpts3d[0]}")
    else:
        print("❌ No results.")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
