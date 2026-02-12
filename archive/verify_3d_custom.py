
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

    from mmpose.apis import init_model, inference_topdown

    POSE_CONFIG = os.path.join(PROJECT_PATH, "configs", "rtmw3d-l_8xb64_cocktail14-384x288.py")
    POSE_CHECKPOINT = os.path.join(PROJ_ROOT, "rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth")

    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {DEVICE}")

    print("Initializing pose estimator...")
    pose_model = init_model(POSE_CONFIG, POSE_CHECKPOINT, device=DEVICE)
    print("✅ Pose model ready.")

    # 3. Run a dummy inference with a mock bbox
    img = np.zeros((384, 384, 3), dtype=np.uint8) # Square image
    bboxes = np.array([[0, 0, 384, 384]], dtype=np.float32)
    
    print("Running pose estimator...")
    pose_results = inference_topdown(pose_model, img, bboxes=bboxes)
    
    if pose_results:
        p0 = pose_results[0]
        # Inspect prediction data
        pred_instances = p0.pred_instances
        kpts = pred_instances.keypoints[0] # (N, 3)
        print(f"✅ Success! Detected {len(kpts)} keypoints.")
        print(f"Sample keypoint [0]: {kpts[0]}")
        if kpts.shape[-1] == 3:
            print("Confirmed: Output has 3 dimensions (X, Y, Z).")
        else:
            print(f"Error: Output dimension is {kpts.shape[-1]}, expected 3.")
            
        # Check Z variations
        z_vals = kpts[:, 2]
        print(f"Z range: [{z_vals.min():.4f}, {z_vals.max():.4f}]")
    else:
        print("❌ No pose results.")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
