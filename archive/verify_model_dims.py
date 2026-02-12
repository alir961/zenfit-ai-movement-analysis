
from mmpose.apis import MMPoseInferencer
import numpy as np
import sys

try:
    model_alias = 'rtmw-l_8xb320-270e_cocktail14-384x288'
    print(f"Inspecting keypoints for: {model_alias}")
    inf = MMPoseInferencer(pose2d=model_alias)

    # Create a blank image
    img = np.zeros((384, 288, 3), dtype=np.uint8)
    
    # Run inference
    result_generator = inf(img, return_vis=False)
    result = next(result_generator)
    
    predictions = result.get('predictions', [])
    if predictions and isinstance(predictions, list):
        p0 = predictions[0]
        if isinstance(p0, list): p0 = p0[0]
        
        kpts = np.asarray(p0.get('keypoints', []))
        print(f"Keypoints shape: {kpts.shape}")
        if kpts.ndim == 2:
            print(f"Keypoints per point: {kpts.shape[1]}")
            if kpts.shape[1] >= 3:
                print(f"Sample point (0): {kpts[0]}")
            else:
                print("Points are 2D only.")
        
        kpts_3d = np.asarray(p0.get('keypoints_3d', []))
        if kpts_3d.size > 0:
            print(f"Keypoints 3D shape: {kpts_3d.shape}")
        else:
            print("No 'keypoints_3d' array in prediction.")
            
    else:
        print("No predictions found.")

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
