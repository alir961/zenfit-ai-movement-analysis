
import sys
import os
import numpy as np
import torch

# 1. Setup paths for custom modules
PROJ_ROOT = r"d:\epitech\zenfit"
PROJECT_PATH = os.path.join(PROJ_ROOT, "third_party", "mmpose", "projects", "rtmpose3d")
if PROJECT_PATH not in sys.path:
    sys.path.append(PROJECT_PATH)

try:
    import rtmpose3d
    from mmpose.apis import init_model, inference_topdown
    from mmdet.apis import DetInferencer, inference_detector
    from mmengine.registry import DefaultScope

    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    POSE_CONFIG = os.path.join(PROJECT_PATH, "configs", "rtmw3d-l_8xb64_cocktail14-384x288.py")
    POSE_CHECKPOINT = os.path.join(PROJ_ROOT, "rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth")

    det_inf = DetInferencer("rtmdet_m_8xb32-300e_coco", device=DEVICE)
    pose_model = init_model(POSE_CONFIG, POSE_CHECKPOINT, device=DEVICE)

    img = np.zeros((384, 384, 3), dtype=np.uint8) 
    
    with DefaultScope.overwrite_default_scope('mmdet'):
        det_results = inference_detector(det_inf.model, img)
    
    bboxes = np.array([[0, 0, 384, 384]], dtype=np.float32)
    pose_results = inference_topdown(pose_model, img, bboxes=bboxes)
    
    if pose_results:
        p0 = pose_results[0]
        inst = p0.pred_instances
        print(f"Prediction keys: {inst.keys()}")
        print(f"Keypoints shape: {inst.keypoints.shape}")
        if 'keypoints_3d' in inst:
            print(f"Keypoints 3D shape: {inst.keypoints_3d.shape}")
        
except Exception as e:
    print(f"Error: {e}")
