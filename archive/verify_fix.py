
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
    from mmdet.apis import DetInferencer, inference_detector
    from mmengine.registry import DefaultScope

    # Model configurations
    DET_ALIAS = "rtmdet_m_8xb32-300e_coco"
    POSE_CONFIG = os.path.join(PROJECT_PATH, "configs", "rtmw3d-l_8xb64_cocktail14-384x288.py")
    POSE_CHECKPOINT = os.path.join(PROJ_ROOT, "rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth")

    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {DEVICE}")

    print("Initializing detector via DetInferencer...")
    det_inf = DetInferencer(DET_ALIAS, device=DEVICE)
    detector = det_inf.model
    
    print("Initializing pose estimator...")
    pose_model = init_model(POSE_CONFIG, POSE_CHECKPOINT, device=DEVICE)
    print("✅ Models ready.")

    # 3. Run inference
    img = np.zeros((384, 384, 3), dtype=np.uint8) 
    
    print("Running detector with mmdet scope...")
    # Wrap in scope to avoid PackDetInputs lookup error in mmpose registry
    with DefaultScope.overwrite_default_scope('mmdet'):
        det_results = inference_detector(detector, img)
    
    # Extract bbox
    pred_instances = det_results.pred_instances.cpu().numpy()
    bboxes = pred_instances.bboxes
    scores = pred_instances.scores
    
    # Mock a bbox if none found for the smoke test
    if len(bboxes) == 0:
        print("No detections, using mock bbox.")
        bboxes = np.array([[0, 0, 384, 384]], dtype=np.float32)
    else:
        # Take best scoring one
        bboxes = bboxes[np.argmax(scores)][None]
    
    print(f"Using bbox: {bboxes}")

    print("Running pose estimator...")
    # Top-down inference should work with mmpose scope (likely current)
    pose_results = inference_topdown(pose_model, img, bboxes=bboxes)
    
    if pose_results:
        p0 = pose_results[0]
        kpts = p0.pred_instances.keypoints[0]
        print(f"✅ Success! Detected {len(kpts)} keypoints.")
        print(f"Sample keypoint [0] (3D): {kpts[0]}")
    else:
        print("❌ No pose results.")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
